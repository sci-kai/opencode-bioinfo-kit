#!/usr/bin/env python3
"""Tests for deploy/common/install/kb/opencode-kit.py failure paths (no opencode needed).

Run from the repo root:
    python3 -m unittest discover -s codebase/tests -t codebase
"""

import http.server
import importlib.util
import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

from kitlib import common, deploy, install, kb, skills
from kitlib.common import REPO
from tests.kit_isolation import IsolatedHome, assert_dies, captured_stderr


class WriteConfig(IsolatedHome):
    def test_backups_do_not_collide_and_extra_keys_warn(self):
        target = self.oc / "opencode.json"
        target.write_text(json.dumps({"$schema": "x", "mcp": {"mine": 1}, "theme": "dark"}))
        with mock.patch.object(deploy.datetime, "datetime") as dt:
            dt.now.return_value.strftime.return_value = "20261111-120000"
            with captured_stderr() as err:
                deploy.write_config({"$schema": "x", "a": 1}, dry_run=False)
                deploy.write_config({"$schema": "x", "a": 2}, dry_run=False)
        backups = sorted(p.name for p in (self.oc / "backups").iterdir())
        self.assertEqual(backups, ["opencode_20261111-120000-2.json", "opencode_20261111-120000.json"])
        self.assertIn("mcp, theme", err.getvalue())
        self.assertIn("opencode_20261111-120000.json", err.getvalue())
        self.assertEqual(json.loads(target.read_text()), {"$schema": "x", "a": 2})

    def test_dry_run_writes_nothing(self):
        with captured_stderr():
            deploy.write_config({"a": 1}, dry_run=True)
        self.assertFalse((self.oc / "opencode.json").exists())


class Manifests(IsolatedHome):
    def test_corrupt_deploy_manifest_dies(self):
        deploy.DEPLOY_MANIFEST.write_text("{")
        assert_dies(self, deploy.read_deploy_manifest, contains=".opencode-kit-deploy.json")

    def test_unknown_saved_agent_package_dies(self):
        deploy.DEPLOY_MANIFEST.write_text(json.dumps({"agent_packages": "core,vanished"}))
        text = assert_dies(self, deploy.choose_agent_packages, None, False, contains="vanished")
        self.assertIn("--agents", text)


class TestDeployment(IsolatedHome):
    def test_first_line_missing_file_is_none(self):
        self.assertIsNone(deploy._first_line(self.root / "missing.md"))

    def test_capture_session_with_broken_binary_returns_none(self):
        with captured_stderr():
            self.assertIsNone(deploy.capture_session(str(self.root / "no-opencode"), {"providers": {}}))


class Common(IsolatedHome):
    def test_write_atomic_replaces_without_leftovers(self):
        path = self.root / "f.json"
        common.write_atomic(path, "one")
        common.write_atomic(path, "two")
        self.assertEqual(path.read_text(), "two")
        self.assertEqual(sorted(p.name for p in self.root.iterdir() if p.is_file()), ["f.json"])

    def test_is_within_is_separator_aware(self):
        self.assertTrue(common.is_within("/a/b/c", "/a/b"))
        self.assertTrue(common.is_within("/a/b", "/a/b"))
        self.assertFalse(common.is_within("/a/bc", "/a/b"))

    def test_load_json_type_check(self):
        path = self.root / "x.json"
        path.write_text("[]")
        assert_dies(self, common.load_json, path, expect=dict, contains="expected a JSON object")

    def test_retry_budget_capped(self):
        calls = []

        def fake_run(*a, **k):
            calls.append(k.get("timeout"))
            return subprocess.CompletedProcess(a, 1, "", "fail")

        with mock.patch.object(common.subprocess, "run", fake_run), mock.patch.object(common.time, "sleep"):
            with captured_stderr() as err:
                self.assertIsNone(common.opencode_json("opencode", ["debug", "agents"], retries=8))
        self.assertEqual(calls, [60, 60, 60])
        self.assertEqual(err.getvalue().count("INFO: retrying"), 2)

    def test_run_opencode_survives_timeout_and_oserror(self):
        def fake_run(*a, **k):
            raise subprocess.TimeoutExpired("x", 1)

        with mock.patch.object(common.subprocess, "run", fake_run), mock.patch.object(common.time, "sleep"):
            with captured_stderr():
                self.assertIsNone(common.run_opencode("opencode", ["auth", "list"], retries=5))


class _Junk(http.server.BaseHTTPRequestHandler):
    body = b"not json"

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *a):
        pass


class CheckKey(unittest.TestCase):
    def serve(self, body):
        handler = type("H", (_Junk,), {"body": body})
        server = http.server.HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}/v1"

    def test_non_json_answer_dies_naming_url(self):
        url = self.serve(b"<html>login</html>")
        assert_dies(self, install.check_key, url, "k", set(), contains=f"{url}/models")

    def test_non_object_answer_dies(self):
        url = self.serve(b"[1, 2]")
        assert_dies(self, install.check_key, url, "k", set(), contains="expected a JSON object")

    def test_unreachable_dies(self):
        assert_dies(self, install.check_key, "http://127.0.0.1:9/v1", "k", set(), contains="127.0.0.1:9")

    def test_lmstudio_without_tty_does_not_die(self):
        config = {"providers": {"lmstudio": {"name": "LM Studio", "settings": {"baseURL": "http://127.0.0.1:9/v1"}}},
                  "agents": {}, "model": "lmstudio/m"}
        with mock.patch.object(install.sys.stdin, "isatty", lambda: False):
            with captured_stderr():
                install.handle_key(None, config)


class KbDrift(unittest.TestCase):
    def test_missing_commit_without_fetch_warns(self):
        with mock.patch.object(kb, "read_source", lambda: {"derived_from_commit": "a" * 40}), \
                mock.patch.object(kb, "kb_head", lambda: ("b" * 40, "2026-01-01")), \
                mock.patch.object(kb, "_has_commit", lambda c: False), \
                mock.patch.object(kb, "git", side_effect=AssertionError("network/git used")):
            with captured_stderr() as err:
                old, new, changed = kb.drift(fetch=False)
        self.assertIsNone(changed)
        self.assertIn("cannot compare", err.getvalue())


class DeployValidatesBeforeWriting(IsolatedHome):
    def setUp(self):
        super().setUp()
        src = self.root / "repo-skills"
        (src / "bionemo-agent-toolkit" / ".git").mkdir(parents=True)
        (src / "nf-core" / "nf-core-lint").mkdir(parents=True)
        (src / "nf-core" / "nf-core-lint" / "SKILL.md").write_text("---\nname: nf-core-lint\ndescription: d\n---\n")
        for p in (
            mock.patch.object(skills, "SKILLS", src),
            mock.patch.object(skills, "BIONEMO", src / "bionemo-agent-toolkit"),
            mock.patch.object(deploy, "ensure_submodules", lambda *a, **k: None),
            mock.patch.object(deploy, "find_opencode", lambda: None),
            mock.patch.object(kb, "render_concat", lambda: {"rules-kb-agents-instructions.md": "x"}),
            mock.patch.object(kb, "drift", lambda fetch=True: ("a", "a", [])),
            mock.patch.object(deploy.sys.stdin, "isatty", lambda: False),
        ):
            p.start()
            self.addCleanup(p.stop)

    def test_dry_run_writes_nothing(self):
        before = self.files_under(self.home)
        with captured_stderr():
            deploy.deploy("kiconnect", "nf-core", dry_run=True, run_tests=False, agent_spec="all")
        self.assertEqual(self.files_under(self.home), before)

    def test_bad_skill_selection_stops_before_any_write(self):
        with mock.patch.object(deploy, "require_v2", lambda exe: "opencode"), \
                mock.patch.object(deploy, "opencode_version", lambda exe: "2.2.6"):
            assert_dies(self, deploy.deploy, "kiconnect", "no-such-skill", dry_run=False, run_tests=False,
                        agent_spec="all", contains="no-such-skill")
        self.assertEqual(self.files_under(self.oc), [])
        self.assertFalse(Path(deploy.user_settings.DEFAULT_TMP).exists())


class MainEntry(unittest.TestCase):
    def test_keyboard_interrupt_exits_130(self):
        spec = importlib.util.spec_from_file_location("opencode_kit_main", str(REPO / "codebase" / "opencode-kit.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        def interrupted():
            raise KeyboardInterrupt

        with mock.patch.object(module, "list_agents", interrupted), \
                mock.patch.object(sys, "argv", ["opencode-kit.py", "list-agents"]):
            with captured_stderr() as err:
                with self.assertRaises(SystemExit) as ctx:
                    module.main()
        self.assertEqual(ctx.exception.code, 130)
        self.assertIn("ERROR: aborted by user", err.getvalue())


if __name__ == "__main__":
    unittest.main()
