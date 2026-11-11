#!/usr/bin/env python3
"""Tests for kitlib.lmstudio: model sets, server selection, build integration.

Uses a fake LM Studio server that serves a real /api/v0/models answer (data/) and the
shipped example model set (configs/backends/local/lmstudio-models.example.json), which is
a real working setup. Run from the repo root:
    python3 -m unittest discover -s codebase/tests -t codebase
"""

import contextlib
import copy
import http.server
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from kitlib import build, lmstudio
from kitlib.common import REPO

DATA = Path(__file__).resolve().parent / "data"
SERVER_MODELS = json.loads((DATA / "lmstudio-api-v0-models_20260919.json").read_text(encoding="utf-8"))
EXAMPLE = REPO / "configs" / "backends" / "local" / "lmstudio-models.example.json"
TIERS = ["light", "main", "codegen", "careful", "writing"]
ROLES = {"light": "fast", "main": "fast", "writing": "fast", "codegen": "heavy", "careful": "heavy"}
HEAVY, FAST = "qwen/qwen3.8-27b", "qwen/qwen3.5-9b"


class FakeLMStudio(http.server.BaseHTTPRequestHandler):
    """/api/v0/models and /v1/models; behaviour set per server via class attributes."""

    mode = "rest"  # rest | openai-only | auth | junk
    payload = SERVER_MODELS

    def do_GET(self):  # noqa: N802 (http.server naming)
        if self.mode == "auth":
            self.send_response(401)
            self.end_headers()
            return
        if self.mode == "junk":
            body = b"<html>not lm studio</html>"
        elif self.path == "/api/v0/models" and self.mode == "rest":
            body = json.dumps(self.payload).encode()
        elif self.path == "/v1/models":
            body = json.dumps({"data": [{"id": m["id"]} for m in self.payload["data"]]}).encode()
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@contextlib.contextmanager
def fake_server(mode="rest", payload=None):
    handler = type("H", (FakeLMStudio,), {"mode": mode, "payload": payload or SERVER_MODELS})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    finally:
        srv.shutdown()
        srv.server_close()


def quiet(fn, *args, **kwargs):
    """Call fn with stderr captured; returns (result, stderr text)."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        result = fn(*args, **kwargs)
    return result, err.getvalue()


def example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class ExampleSetTest(unittest.TestCase):
    """The shipped example is the maintainer's real setup and must stay valid."""

    def test_example_validates_with_expected_tiers(self):
        cfg = lmstudio.validate(example(), TIERS, "example")
        self.assertEqual(cfg["tiers"], {"light": FAST, "main": FAST, "codegen": HEAVY, "careful": HEAVY, "writing": FAST})
        self.assertEqual(len(cfg["models"]), 7)
        self.assertEqual(cfg["models"][HEAVY]["context"], 65536)
        self.assertEqual(cfg["models"][FAST]["context"], 131072)

    def test_example_fits_the_server_it_was_written_for(self):
        server = [{"id": m["id"], "tools": True, "max_context": m.get("max_context_length")}
                  for m in SERVER_MODELS["data"] if m["type"] != "embeddings"]
        quiet(lmstudio.check_against_server, lmstudio.validate(example(), TIERS, "example"), server, "fake")

    def test_build_uses_example_until_user_chose(self):
        backend = lmstudio.local_backend()
        _, err = quiet(lmstudio.apply_to_backend, backend, None)
        self.assertIn("example", err)
        models = backend["providers"]["lmstudio"]["models"]
        self.assertEqual(set(models), set(example()["models"]))
        self.assertEqual(backend["tiers"]["codegen"]["model"], f"lmstudio/{HEAVY}")
        self.assertEqual(backend["tiers"]["main"]["model"], f"lmstudio/{FAST}")
        # per-model sampling: Gemma 26B runs no tier but is selectable with its own variant
        self.assertEqual(models["google/gemma-4-26b-a4b-qat"]["variants"][0]["id"], "t1.0-p0.95")

    def test_full_config_for_local_backend(self):
        settings = {"lmstudio_url": "http://localhost:1234/v1", "lmstudio_models": example()}
        with tempfile.TemporaryDirectory() as tmp:
            configs, _ = quiet(build.build_all, REPO, ["local"], settings=settings,
                               prompt_dir=Path(tmp) / "p", instr_dir=Path(tmp) / "i")
        cfg = configs["local"]
        self.assertEqual(cfg["model"], f"lmstudio/{FAST}#t0.6-p0.95")
        self.assertEqual(cfg["agents"]["nextflow"]["model"], f"lmstudio/{HEAVY}#t0.6-p0.95")
        self.assertEqual(cfg["agents"]["title"]["model"], f"lmstudio/{FAST}#t0.6-p0.95")
        self.assertEqual(cfg["providers"]["lmstudio"]["settings"]["baseURL"], "http://localhost:1234/v1")

    def test_tier_on_model_with_own_sampling_uses_it(self):
        cfg = example()
        cfg["tiers"]["careful"] = "google/gemma-4-26b-a4b-qat"
        backend = lmstudio.apply_to_backend(lmstudio.local_backend(), cfg)
        self.assertEqual(backend["tiers"]["careful"]["temperature"], 1.0)
        self.assertEqual(backend["tiers"]["codegen"]["temperature"], 0.6)


class ValidateTest(unittest.TestCase):
    def assertInvalid(self, cfg, fragment):
        with self.assertRaises(lmstudio.ModelSetError) as ctx:
            lmstudio.validate(cfg, TIERS, "test", ROLES)
        self.assertIn(fragment, str(ctx.exception))

    def test_minimal_set_gets_defaults(self):
        cfg = lmstudio.validate({"models": {"a/b-9b": {"context": 32768}}, "tiers": {t: "a/b-9b" for t in TIERS}},
                                TIERS, "t")
        self.assertEqual(cfg["models"]["a/b-9b"]["output"], 8192)
        self.assertTrue(cfg["models"]["a/b-9b"]["tools"])

    def test_v1_layout_is_migrated(self):
        old = {"heavy": {"id": HEAVY, "context": 65536, "output": 16384, "tools": True, "reasoning": True},
               "fast": {"id": FAST, "context": 131072, "output": 32768, "tools": True, "reasoning": True}}
        cfg = lmstudio.validate(old, TIERS, "old", ROLES)
        self.assertEqual(cfg["tiers"]["careful"], HEAVY)
        self.assertEqual(cfg["tiers"]["light"], FAST)

    def test_failures(self):
        good = example()
        cases = []
        c = copy.deepcopy(good); del c["tiers"]["writing"]; cases.append((c, "missing ['writing']"))
        c = copy.deepcopy(good); c["tiers"]["fancy"] = FAST; cases.append((c, "unknown ['fancy']"))
        c = copy.deepcopy(good); c["tiers"]["main"] = "not/declared"; cases.append((c, "not declared"))
        c = copy.deepcopy(good); c["models"][FAST]["context"] = 1000; cases.append((c, "'context' must be"))
        c = copy.deepcopy(good); c["models"][FAST]["context"] = True; cases.append((c, "'context' must be"))
        c = copy.deepcopy(good); c["models"][FAST]["output"] = 131072; cases.append((c, "'output' must be"))
        c = copy.deepcopy(good); c["models"][FAST]["temperature"] = 0.7; cases.append((c, "together"))
        c = copy.deepcopy(good); c["models"][FAST].update(temperature=3, top_p=0.9); cases.append((c, "from 0 to 2"))
        c = copy.deepcopy(good); c["models"][FAST]["ctx"] = 1; cases.append((c, "unknown keys ['ctx']"))
        c = copy.deepcopy(good); c["models"]["bad id"] = {"context": 8192}; cases.append((c, "without spaces"))
        c = copy.deepcopy(good); c["format"] = 3; cases.append((c, "format 3"))
        c = copy.deepcopy(good); c["models"] = {}; cases.append((c, "non-empty"))
        cases.append(([], "JSON object"))
        for cfg, fragment in cases:
            with self.subTest(fragment=fragment):
                self.assertInvalid(cfg, fragment)

    def test_apply_stops_on_invalid_set(self):
        bad = example()
        bad["tiers"]["main"] = "gone/model"
        with self.assertRaises(SystemExit):
            quiet(lmstudio.apply_to_backend, lmstudio.local_backend(), bad)


class UrlTest(unittest.TestCase):
    def test_forms(self):
        for given, want in [
            ("localhost:1234", "http://localhost:1234/v1"),
            ("http://10.0.0.5:1234", "http://10.0.0.5:1234/v1"),
            ("http://10.0.0.5:1234/v1/", "http://10.0.0.5:1234/v1"),
            ("https://lm.example.org/v1", "https://lm.example.org/v1"),
        ]:
            self.assertEqual(lmstudio.normalise_url(given), want)
        self.assertIsNone(lmstudio.normalise_url(""))

    def test_junk_is_refused(self):
        for bad in ("ftp://host/v1", "http://", "http://host:1234/v1?x=1"):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                quiet(lmstudio.normalise_url, bad)


class ServerTest(unittest.TestCase):
    def test_list_and_suggest(self):
        with fake_server() as url:
            models = lmstudio.list_models(url)
        ids = [m["id"] for m in models]
        self.assertNotIn("text-embedding-nomic-embed-text-v1.5", ids)
        heavy, fast = lmstudio.suggest(models)
        # bonsai-27b is Q1 and skipped; the suggestion equals the example setup
        self.assertEqual((heavy["id"], fast["id"]), (HEAVY, FAST))

    def test_old_lmstudio_without_rest_api(self):
        with fake_server("openai-only") as url:
            models, err = quiet(lmstudio.list_models, url)
        self.assertIn("older LM Studio", err)
        self.assertTrue(all(m["tools"] is None for m in models))

    def test_auth_error_names_the_env_var(self):
        with fake_server("auth") as url, self.assertRaises(lmstudio.ServerError) as ctx:
            lmstudio.list_models(url)
        self.assertIn(lmstudio.API_KEY_ENV, str(ctx.exception))

    def test_non_json_server(self):
        with fake_server("junk") as url, self.assertRaises(lmstudio.ServerError) as ctx:
            lmstudio.list_models(url)
        self.assertIn("not JSON", str(ctx.exception))

    def test_unreachable_server_returns_none(self):
        with fake_server() as url:
            pass  # closed again: nothing listens on the port any more
        result, err = quiet(lmstudio.choose, url, interactive=False)
        self.assertIsNone(result)
        self.assertIn("not reachable", err)


class ChooseTest(unittest.TestCase):
    def test_defaults_reproduce_example_tiers(self):
        with fake_server() as url:
            cfg, _ = quiet(lmstudio.choose, url, interactive=False)
        self.assertEqual(cfg["tiers"], lmstudio.validate(example(), TIERS, "e")["tiers"])
        self.assertEqual(set(cfg["models"]), {HEAVY, FAST})
        self.assertEqual(cfg["models"][HEAVY]["context"], 65536)  # capped default when not loaded

    def test_flags(self):
        with fake_server() as url:
            cfg, _ = quiet(lmstudio.choose, url, interactive=False, heavy="google/gemma-4-26b-a4b-qat",
                           tier_models={"writing": "google/gemma-4-12b-qat"}, extras=["nvidia/nemotron-3-nano-4b"],
                           contexts={"*": 32768, FAST: 131072})
        self.assertEqual(cfg["tiers"]["codegen"], "google/gemma-4-26b-a4b-qat")
        self.assertEqual(cfg["tiers"]["writing"], "google/gemma-4-12b-qat")
        self.assertEqual(cfg["tiers"]["main"], FAST)
        self.assertIn("nvidia/nemotron-3-nano-4b", cfg["models"])
        self.assertEqual(cfg["models"][FAST]["context"], 131072)
        self.assertEqual(cfg["models"]["google/gemma-4-12b-qat"]["context"], 32768)

    def test_previous_set_is_the_default(self):
        with fake_server() as url:
            cfg, _ = quiet(lmstudio.choose, url, interactive=False, current=example())
        self.assertEqual(cfg["models"], lmstudio.validate(example(), TIERS, "e")["models"])

    def test_unknown_model_or_tier_or_too_long_context(self):
        with fake_server() as url:
            for kwargs in ({"heavy": "nope/model"}, {"tier_models": {"huge": FAST}},
                           {"contexts": {"google/gemma-4-e4b": 262144}, "extras": ["google/gemma-4-e4b"]}):
                with self.subTest(kwargs=kwargs), self.assertRaises(SystemExit):
                    quiet(lmstudio.choose, url, interactive=False, **kwargs)

    def test_interactive_per_tier_with_typo_and_extras(self):
        with fake_server() as url:
            models = lmstudio.list_models(url)
            num = {m["id"]: str(i) for i, m in enumerate(models, 1)}
            answers = iter([
                "2",                      # one model per tier
                "", "",                   # light, main: keep suggestion (fast)
                "typo", num[HEAVY],       # codegen: typo is asked again
                "", "",                   # careful (heavy), writing (fast)
                num["google/gemma-4-e4b"],  # extra model
                "", "", "49152",          # contexts: fast, heavy defaults; e4b 49152
            ])
            with mock.patch("builtins.input", lambda prompt="": next(answers)):
                cfg, err = quiet(lmstudio.choose, url, interactive=True)
        self.assertIn("try again", err)
        self.assertEqual(cfg["tiers"]["codegen"], HEAVY)
        self.assertEqual(cfg["models"]["google/gemma-4-e4b"]["context"], 49152)
        self.assertEqual(cfg["models"]["google/gemma-4-e4b"]["output"], 12288)

    def test_interactive_eof_aborts_cleanly(self):
        def eof(prompt=""):
            raise EOFError

        with fake_server() as url, mock.patch("builtins.input", eof), self.assertRaises(SystemExit):
            quiet(lmstudio.choose, url, interactive=True)


class FileTest(unittest.TestCase):
    def test_export_and_reimport(self):
        cfg = lmstudio.validate(example(), TIERS, "e")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "my-models.json"
            quiet(lmstudio.export, cfg, path)
            self.assertEqual(lmstudio.load_models_file(path), cfg)
            with self.assertRaises(SystemExit):
                quiet(lmstudio.export, cfg, path)  # never overwrites

    def test_missing_and_invalid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                quiet(lmstudio.load_models_file, Path(tmp) / "none.json")
            bad = Path(tmp) / "bad.json"
            bad.write_text('{"models": {}, "tiers": {}}', encoding="utf-8")
            with self.assertRaises(SystemExit):
                quiet(lmstudio.load_models_file, bad)


if __name__ == "__main__":
    unittest.main()
