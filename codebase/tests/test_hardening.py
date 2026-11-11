#!/usr/bin/env python3
"""Failure-path tests for the pre-release hardening: sandbox rules, XDG folders, temp folder
ownership, refused folders, LM Studio model-set checks, deploy backups, dry runs.

Run from the repo root:
    python3 -m unittest discover -s codebase/tests -t codebase
"""

import copy
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kitlib import build, common, deploy, lmstudio, settings
from kitlib.common import REPO
from tests.kit_isolation import IsolatedHome, assert_dies, captured_stderr
from tests.test_lmstudio import FAST, SERVER_MODELS, TIERS, example, fake_server, quiet

HAS_UIDS = hasattr(os, "getuid")


def _load_cli():
    spec = importlib.util.spec_from_file_location("opencode_kit_cli", str(REPO / "codebase" / "opencode-kit.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rules(config, action, effect):
    return {r["resource"] for r in config["permissions"] if r["action"] == action and r["effect"] == effect}


class SandboxRules(IsolatedHome):
    """Item 1: what agents may not edit, with opencode's real (XDG) folders."""

    def build(self):
        with captured_stderr():
            return build.build_all(REPO, ["kiconnect"], settings={"tmp_dir": str(self.root)},
                                   prompt_dir=self.root / "p", instr_dir=self.root / "i")["kiconnect"]

    def test_config_dir_repo_sources_and_project_config_not_editable(self):
        denied = _rules(self.build(), "edit", "deny")
        for resource in (str(self.oc), f"{self.oc}/*", f"{REPO}/configs", f"{REPO}/configs/*",
                         f"{REPO}/codebase", f"{REPO}/codebase/*", "*/.opencode/*", "*/opencode.json",
                         "*/opencode.jsonc"):
            with self.subTest(resource=resource):
                self.assertIn(resource, denied)
        self.assertFalse(any(r.startswith(f"{REPO}/cubi-rules") for r in denied), "digest must stay editable")

    def test_rules_follow_xdg_dirs_and_no_token_is_left(self):
        xdg_cfg, xdg_data = self.root / "xdgc" / "opencode", self.root / "xdgd" / "opencode"
        with mock.patch.object(common, "OC_CONFIG_DIR", xdg_cfg), mock.patch.object(common, "OC_DATA_DIR", xdg_data):
            config = self.build()
        text = json.dumps(config)
        for token in ("{OC_CONFIG}", "{OC_DATA}", "{REPO}", "~/.config/opencode", "~/.local/share/opencode"):
            self.assertNotIn(token, text)
        self.assertIn(f"{xdg_data}/auth.json", _rules(config, "read", "deny"))
        self.assertIn(f"{xdg_cfg}/*", _rules(config, "edit", "deny"))
        self.assertIn(str(xdg_cfg), _rules(config, "external_directory", "allow"))

    def test_no_stray_shell_allow(self):
        self.assertEqual(_rules(self.build(), "shell", "allow"), set())

    def test_agent_definition_dirs_are_reported(self):
        self.assertEqual(deploy.agent_definition_dirs(), [])
        (self.oc / "agents").mkdir()
        (self.oc / "mode").mkdir()
        self.assertEqual(deploy.agent_definition_dirs(), [self.oc / "agents", self.oc / "mode"])


class XdgDirs(IsolatedHome):
    """Item 3: opencode's folders follow XDG_CONFIG_HOME / XDG_DATA_HOME (absolute only)."""

    def test_config_and_data_dir(self):
        env = {"XDG_CONFIG_HOME": "/x/cfg", "XDG_DATA_HOME": "/x/data"}
        self.assertEqual(common.config_dir(env), Path("/x/cfg/opencode"))
        self.assertEqual(common.data_dir(env), Path("/x/data/opencode"))
        rel = {"XDG_CONFIG_HOME": "rel/cfg", "XDG_DATA_HOME": ""}
        self.assertEqual(common.config_dir(rel), self.home / ".config" / "opencode")
        self.assertEqual(common.data_dir(rel), self.home / ".local" / "share" / "opencode")

    def test_real_xdg_locations_and_parents_refused(self):
        xdg = self.root / "xdg"
        (xdg / "opencode").mkdir(parents=True)
        (self.root / "xdgdata" / "opencode").mkdir(parents=True)
        with mock.patch.object(common, "OC_CONFIG_DIR", xdg / "opencode"), \
                mock.patch.object(common, "OC_DATA_DIR", self.root / "xdgdata" / "opencode"):
            for value in (xdg / "opencode", xdg, self.root / "xdgdata" / "opencode"):
                with self.subTest(value=value):
                    assert_dies(self, settings.normalise_dir, str(value), "extra_dirs", contains="opencode")


class TempFolderOwnership(IsolatedHome):
    """Item 2: the temp folder is a private real folder of this user."""

    @unittest.skipUnless(HAS_UIDS, "no user IDs on this platform")
    def test_symlink_refused(self):
        target = self.root / "real-tmp"
        target.mkdir(mode=0o700)
        link = self.root / "tmp-link"
        os.symlink(str(target), str(link))
        assert_dies(self, settings.normalise_dir, str(link), "tmp_dir", contains="symlink")

    @unittest.skipUnless(HAS_UIDS, "no user IDs on this platform")
    def test_too_open_own_folder_is_tightened(self):
        folder = self.root / "open-tmp"
        folder.mkdir()
        os.chmod(str(folder), 0o755)
        with captured_stderr() as err:
            settings.normalise_dir(str(folder), "tmp_dir")
        self.assertEqual(stat.S_IMODE(os.stat(str(folder)).st_mode), 0o700)
        self.assertIn("INFO:", err.getvalue())

    @unittest.skipUnless(HAS_UIDS, "no user IDs on this platform")
    def test_foreign_folder_refused_and_rechecked_on_resolve(self):
        folder = self.root / "foreign-tmp"
        folder.mkdir(mode=0o700)
        settings.SETTINGS_FILE.write_text(json.dumps({"tmp_dir": str(folder), "directories_confirmed": True}))
        with mock.patch.object(os, "getuid", lambda: os.stat(str(folder)).st_uid + 1):
            text = assert_dies(self, settings.resolve, "kiconnect", False, contains="owned by uid")
        self.assertIn("--tmp-dir", text)


class RefusedFolders(IsolatedHome):
    """Items 4 and 13: wildcard targets, system trees, credential folders, shared folders."""

    def test_glob_in_symlink_target_refused(self):
        target = self.root / "we*ird"
        target.mkdir()
        link = self.root / "plain"
        os.symlink(str(target), str(link))
        assert_dies(self, settings.normalise_dir, str(link), "envs_dir", contains="wildcard")
        # defensive check at build time (the symlink may have moved after saving)
        assert_dies(self, build.user_permission_rules, {"envs_dir": str(link)}, contains="wildcard")

    def test_system_trees_and_temp_roots(self):
        for path in ("/var/tmp", "/dev/shm", "/var/lib", "/etc/ssl", "/proc/1", "/sys/kernel", "/dev/x", "/boot/efi"):
            with self.subTest(path=path):
                self.assertIsNotNone(settings._too_broad(path))
        self.assertIsNone(settings._too_broad("/var/tmp/mine"))

    def test_more_credential_folders(self):
        for rel in (".claude", ".config/gh", ".kube", ".docker", ".password-store"):
            (self.home / rel).mkdir(parents=True)
            with self.subTest(rel=rel):
                assert_dies(self, settings.normalise_dir, f"~/{rel}", "extra_dirs")
        for rel in (".netrc", ".git-credentials"):
            with self.subTest(rel=rel):
                self.assertIsNotNone(settings._too_broad(str(self.home / rel)))

    def test_case_insensitive_on_macos(self):
        with mock.patch.object(settings, "CASE_INSENSITIVE", True):
            self.assertIsNotNone(settings._too_broad("/ETC/x"))
            self.assertIsNotNone(settings._too_broad("/Tmp"))
            self.assertIsNotNone(settings._too_broad(str(self.home / ".SSH")))
        with mock.patch.object(settings, "CASE_INSENSITIVE", False):
            self.assertIsNone(settings._too_broad("/Tmp"))

    @unittest.skipUnless(HAS_UIDS, "no user IDs on this platform")
    def test_world_writable_foreign_folder_refused(self):
        shared = self.root / "shared"
        shared.mkdir()
        os.chmod(str(shared), 0o777)
        self.assertEqual(settings.normalise_dir(str(shared), "envs_dir"), str(shared))  # own folder: fine
        with mock.patch.object(os, "getuid", lambda: os.stat(str(shared)).st_uid + 1):
            assert_dies(self, settings.normalise_dir, str(shared), "envs_dir", contains="writable by every user")


class BadTypes(IsolatedHome):
    """Item 8: hand-edited settings stop with ERROR, not a traceback."""

    def test_url_type_and_syntax(self):
        for bad in (123, ["http://x"], "http://[::1", "http://host:99999/v1"):
            with self.subTest(bad=bad):
                assert_dies(self, lmstudio.normalise_url, bad)

    def test_extra_dirs_and_dir_values(self):
        for raw, fragment in (({"extra_dirs": 5}, "extra_dirs"), ({"extra_dirs": [1]}, "extra_dirs"),
                              ({"extra_dirs": {"a": 1}}, "extra_dirs"), ({"envs_dir": 5}, "envs_dir"),
                              ({"envs_dir": ["x"]}, "envs_dir")):
            with self.subTest(raw=raw):
                assert_dies(self, settings.finalise, raw, "kiconnect", contains=fragment)

    def test_describe_survives_bad_types(self):
        text = settings.describe({"extra_dirs": [1, None], "envs_dir": 5, "lmstudio_models": ["x"]})
        self.assertIn("INVALID", text)

    def test_tier_value_must_be_text(self):
        cfg = example()
        cfg["tiers"]["main"] = [FAST]
        with self.assertRaises(lmstudio.ModelSetError):
            lmstudio.validate(cfg, TIERS, "t")


class ModelSetChecks(unittest.TestCase):
    """Items 5 and 9: model IDs, booleans, context limits and warnings."""

    def assertInvalid(self, cfg, fragment):
        with self.assertRaises(lmstudio.ModelSetError) as ctx:
            lmstudio.validate(cfg, TIERS, "t")
        self.assertIn(fragment, str(ctx.exception))

    def test_hash_and_non_bool_flags(self):
        c = example(); c["models"]["a/b#x"] = {"context": 8192}; self.assertInvalid(c, "'#'")
        c = example(); c["models"][FAST]["tools"] = 1; self.assertInvalid(c, "'tools'")
        c = example(); c["models"][FAST]["tools"] = 0; self.assertInvalid(c, "'tools'")
        c = example(); c["models"][FAST]["reasoning"] = 1; self.assertInvalid(c, "'reasoning'")

    def test_small_context_from_file_warns(self):
        cfg = example()
        cfg["models"][FAST]["context"] = 8192
        cfg["models"][FAST].pop("output", None)
        path = Path(self.tmp()) / "set.json"
        path.write_text(json.dumps(cfg), encoding="utf-8")
        _, err = quiet(lmstudio.load_models_file, path)
        self.assertIn(f"model '{FAST}' has context 8192", err)
        self.assertIn("Context Length", err)

    def tmp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return d.name

    def test_context_flags_checked(self):
        with fake_server() as url:
            for contexts in ({"*": 0}, {"*": 100}, {FAST: lmstudio.MIN_CONTEXT - 1}):
                with self.subTest(contexts=contexts), self.assertRaises(SystemExit):
                    quiet(lmstudio.choose, url, interactive=False, contexts=contexts)
            # a small but valid context is warned about, not refused
            cfg, err = quiet(lmstudio.choose, url, interactive=False, contexts={"*": 16384})
        self.assertEqual(cfg["models"][FAST]["context"], 16384)
        self.assertIn("WARNING:", err)

    def test_context_flag_for_model_outside_set_names_it(self):
        with fake_server() as url, self.assertRaises(SystemExit):
            with captured_stderr() as err:
                lmstudio.choose(url, interactive=False, contexts={"google/gemma-4-e4b": 32768})
        self.assertIn("google/gemma-4-e4b", err.getvalue())
        self.assertIn("not part of the chosen set", err.getvalue())

    def test_small_loaded_context_warns_in_server_path(self):
        payload = copy.deepcopy(SERVER_MODELS)
        for m in payload["data"]:
            if m["id"] == FAST:
                m.update(state="loaded", loaded_context_length=8192)
        with fake_server(payload=payload) as url:
            cfg, err = quiet(lmstudio.choose, url, interactive=False)
        self.assertEqual(cfg["models"][FAST]["context"], 8192)
        self.assertIn(f"model '{FAST}' has context 8192", err)

    def test_interactive_caps_saved_context_at_server_maximum(self):
        current = example()
        current["models"][FAST]["context"] = 300000  # server maximum is 262144
        current["models"][FAST].pop("output", None)
        answers = iter(["", "", "", "-", "", ""])  # mode, heavy, fast, extras, two contexts
        with fake_server() as url, mock.patch("builtins.input", lambda prompt="": next(answers)):
            cfg, err = quiet(lmstudio.choose, url, interactive=True, current=current)
        self.assertEqual(cfg["models"][FAST]["context"], 262144)
        self.assertIn("exceeds the server's maximum 262144", err)

    def test_cli_context_parser(self):
        cli = _load_cli()
        for bad in (["0"], ["100"], [f"{FAST}=0"], ["=40000"]):
            with self.subTest(bad=bad):
                assert_dies(self, cli._contexts, bad)
        self.assertEqual(cli._contexts(["65536", f"{FAST}=131072"]), {"*": 65536, FAST: 131072})


class LocalModelSetResolve(IsolatedHome):
    """Items 6, 7 and 12: model set on first deploy, URL changes, the unconfirmed warning."""

    DEAD = "http://127.0.0.1:9/v1"

    def save(self, **values):
        settings.SETTINGS_FILE.write_text(json.dumps({"directories_confirmed": True, **values}))

    def test_first_real_deploy_without_server_stops(self):
        text = assert_dies(self, settings.resolve, "local", False, {"lmstudio_url": self.DEAD},
                           allow_example=False, contains="--models-file")
        self.assertIn("lmstudio-models.example.json", text)

    def test_dry_run_falls_back_to_example(self):
        with captured_stderr() as err:
            out, _ = settings.resolve("local", False, {"lmstudio_url": self.DEAD}, allow_example=True)
        self.assertIsNone(out["lmstudio_models"])
        self.assertIn("example model set", err.getvalue())

    def test_changed_url_unreachable_keeps_set_with_warning(self):
        self.save(lmstudio_url="http://10.9.9.9:1234/v1", lmstudio_models=example())
        with captured_stderr() as err:
            out, _ = settings.resolve("local", False, {"lmstudio_url": self.DEAD}, allow_example=False)
        self.assertEqual(out["lmstudio_models"], example())
        self.assertIn("previous server http://10.9.9.9:1234/v1", err.getvalue())

    def test_changed_url_reachable_chooses_again(self):
        old = example()
        old["models"]["gone/model-9b"] = {"context": 32768}  # only on the previous server
        self.save(lmstudio_url="http://10.9.9.9:1234/v1", lmstudio_models=old)
        with fake_server() as url:
            with captured_stderr():
                out, changed = settings.resolve("local", False, {"lmstudio_url": url}, allow_example=False)
        self.assertTrue(changed)
        self.assertNotIn("gone/model-9b", out["lmstudio_models"]["models"])  # chosen from the new server
        self.assertEqual(out["lmstudio_models"]["tiers"], example()["tiers"])  # saved choice kept as default

    def test_url_changed_by_answer_also_chooses_again(self):
        self.save(lmstudio_url="http://10.9.9.9:1234/v1", lmstudio_models=example())
        calls = []

        def fake_choose(url, **kw):
            calls.append(url)
            return None

        with mock.patch.object(lmstudio, "choose", fake_choose), \
                mock.patch.object(settings, "ask", lambda current: {"lmstudio_url": self.DEAD}):
            with captured_stderr():
                settings.resolve("local", True, reconfigure=True, allow_example=False)
        self.assertEqual(calls, [self.DEAD])

    def test_non_local_backend_keeps_set_without_asking_server(self):
        self.save(lmstudio_url="http://10.9.9.9:1234/v1", lmstudio_models=example())
        with mock.patch.object(lmstudio, "choose", side_effect=AssertionError("server asked")):
            with captured_stderr():
                out, _ = settings.resolve("kiconnect", False, {"lmstudio_url": self.DEAD})
        self.assertEqual(out["lmstudio_models"], example())
        self.assertEqual(out["lmstudio_url"], self.DEAD)

    def test_unconfirmed_warning_does_not_claim_missing_terminal(self):
        with captured_stderr() as err:
            settings.resolve("kiconnect", False)
        self.assertIn("directories not confirmed yet", err.getvalue())
        self.assertIn("configure-directories", err.getvalue())
        self.assertNotIn("no terminal", err.getvalue())


class DeployWrites(IsolatedHome):
    """Item 10: the user's own prompt/instruction files are backed up; symlinks are kept."""

    def test_foreign_prompt_moved_to_backups(self):
        prompts = self.oc / "prompts"
        prompts.mkdir()
        (prompts / "build.md").write_text("my own prompt")
        with captured_stderr() as err:
            deploy.write_prompts({"build": "kit prompt"}, prompts, dry_run=False, known=deploy.kit_written_files())
        self.assertEqual((prompts / "build.md").read_text(), "kit prompt")
        backups = list((self.oc / "backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "my own prompt")
        self.assertIn("WARNING:", err.getvalue())

    def test_kit_file_from_manifest_overwritten_without_backup(self):
        deploy.DEPLOY_MANIFEST.write_text(json.dumps({"files": ["instructions/rules.md"]}))
        instr = self.oc / "instructions"
        instr.mkdir()
        (instr / "rules.md").write_text("old kit text")
        with captured_stderr():
            deploy.write_instructions({"rules.md": "new"}, instr, dry_run=False, known=deploy.kit_written_files())
        self.assertEqual((instr / "rules.md").read_text(), "new")
        self.assertFalse((self.oc / "backups").exists())

    def test_old_manifest_without_files_trusts_kit_names(self):
        deploy.DEPLOY_MANIFEST.write_text(json.dumps({"backend": "kiconnect"}))
        self.assertIsNone(deploy.kit_written_files())

    def test_bad_files_record_dies(self):
        deploy.DEPLOY_MANIFEST.write_text(json.dumps({"files": "prompts/build.md"}))
        assert_dies(self, deploy.kit_written_files, contains="'files'")

    def test_write_atomic_writes_through_symlink(self):
        target = self.root / "dotfiles" / "opencode.json"
        target.parent.mkdir()
        target.write_text("old")
        link = self.oc / "opencode.json"
        os.symlink(str(target), str(link))
        with captured_stderr() as err:
            common.write_atomic(link, "new")
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.read_text(), "new")
        self.assertIn("symlink", err.getvalue())


class DryRunSubmodules(IsolatedHome):
    """Item 11: a dry run never runs 'git submodule update --init'."""

    def test_missing_submodule_stops_without_git(self):
        missing = {"kb": self.root / "kb", "bionemo": self.root / "bn"}
        with mock.patch.dict(common.SUBMODULES, missing), \
                mock.patch.object(common, "git", side_effect=AssertionError("git was run")), \
                mock.patch.object(common, "REPO", self.root):
            assert_dies(self, common.ensure_submodules, dry_run=True, contains="submodule update --init")


if __name__ == "__main__":
    unittest.main()
