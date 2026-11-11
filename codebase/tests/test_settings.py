#!/usr/bin/env python3
"""Tests for kitlib.settings: refused folders, path checks, temp folder, dry run, confirmation.

Run from the repo root:
    python3 -m unittest discover -s codebase/tests -t codebase
"""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kitlib import common, settings
from tests.kit_isolation import IsolatedHome, assert_dies, captured_stderr

MODULE_DEFAULT_TMP = settings.DEFAULT_TMP  # before IsolatedHome patches it


class RefusedFolders(IsolatedHome):
    def test_system_roots_refused(self):
        for path in ("/", "/home", "/Users", "/tmp", "/private/tmp", "/mnt", "/media", "/opt",
                     "/srv", "/run", "/lib64", "/Library", "/System", "/Applications", "/Volumes", "/etc"):
            with self.subTest(path=path):
                assert_dies(self, settings.normalise_dir, path, "extra_dirs")

    def test_home_and_its_parents_refused(self):
        for value in (str(self.home), "~", "~/..", str(self.home.parent), str(self.root)):
            with self.subTest(value=value):
                assert_dies(self, settings.normalise_dir, value, "extra_dirs", contains="home folder")

    def test_credential_folders_and_their_parents_refused(self):
        for rel in (".config", ".local", ".local/share", ".local/share/opencode", ".ssh", ".ssh/keys",
                    ".config/opencode", ".aws", ".gnupg"):
            (self.home / rel).mkdir(parents=True, exist_ok=True)
            with self.subTest(rel=rel):
                assert_dies(self, settings.normalise_dir, f"~/{rel}", "extra_dirs")

    def test_prefix_lookalike_is_not_a_credential_folder(self):
        # '~/.sshfoo' starts with '~/.ssh' as text but is a different folder
        (self.home / ".sshfoo").mkdir()
        self.assertEqual(settings.normalise_dir("~/.sshfoo", "extra_dirs"), str(self.home / ".sshfoo"))

    def test_symlink_to_home_refused(self):
        link = self.root / "innocent"
        os.symlink(str(self.home), str(link))
        assert_dies(self, settings.normalise_dir, str(link), "extra_dirs", contains="home folder")

    def test_deeper_folders_allowed(self):
        # pure check (no existence needed): /mnt itself is refused, /mnt/disk is not.
        # A fixed home, because the test's temp HOME may itself lie below /mnt/disk.
        with mock.patch.object(settings, "_homes", lambda: {"/home/tester"}), \
                mock.patch.object(common, "OC_CONFIG_DIR", Path("/home/tester/.config/opencode")), \
                mock.patch.object(common, "OC_DATA_DIR", Path("/home/tester/.local/share/opencode")):
            for path in ("/mnt/disk", "/mnt/disk/claude", "/tmp/opencode-user", "/tmp/opencode", "/opt/conda"):
                with self.subTest(path=path):
                    self.assertIsNone(settings._too_broad(path))
            self.assertIsNotNone(settings._too_broad("/mnt"))
            self.assertIsNotNone(settings._too_broad("/home/tester/.config"))
        data = self.root / "data" / "scratch"
        data.mkdir(parents=True)
        self.assertEqual(settings.normalise_dir(str(data), "scratch_dir"), str(data))

    def test_glob_characters_refused(self):
        for name in ("sc*atch", "a?b", "x[1]", "y{a,b}"):
            folder = self.root / name
            folder.mkdir()
            with self.subTest(name=name):
                assert_dies(self, settings.normalise_dir, str(folder), "extra_dirs", contains="wildcard")

    def test_missing_folder_refused(self):
        assert_dies(self, settings.normalise_dir, str(self.root / "nope"), "envs_dir", contains="does not exist")

    def test_symlink_kept_as_written(self):
        target = self.root / "real"
        target.mkdir()
        link = self.root / "link"
        os.symlink(str(target), str(link))
        self.assertEqual(settings.normalise_dir(str(link), "envs_dir"), str(link))


class ScratchBelowMount(IsolatedHome):
    def test_sibling_with_common_prefix_refused(self):
        (self.root / "mnt").mkdir()
        (self.root / "mnt2" / "x").mkdir(parents=True)
        raw = {"scratch_mount": str(self.root / "mnt"), "scratch_dir": str(self.root / "mnt2" / "x")}
        assert_dies(self, settings.finalise, raw, "kiconnect", contains="not below scratch_mount")

    def test_folder_below_mount_allowed(self):
        (self.root / "mnt" / "claude").mkdir(parents=True)
        raw = {"scratch_mount": str(self.root / "mnt"), "scratch_dir": str(self.root / "mnt" / "claude")}
        out = settings.finalise(raw, "kiconnect")
        self.assertEqual(out["scratch_dir"], str(self.root / "mnt" / "claude"))


class TempFolder(IsolatedHome):
    def test_default_tmp_is_per_user_and_private(self):
        out = settings.finalise({}, "kiconnect")
        self.assertEqual(out["tmp_dir"], settings.DEFAULT_TMP)
        mode = stat.S_IMODE(os.stat(out["tmp_dir"]).st_mode)
        self.assertEqual(mode & 0o077, 0, f"temp folder mode {oct(mode)} is readable by others")

    def test_module_default_names_the_user(self):
        self.assertEqual(os.path.dirname(MODULE_DEFAULT_TMP), tempfile.gettempdir())
        self.assertEqual(os.path.basename(MODULE_DEFAULT_TMP), f"opencode-{settings._user_name()}")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can write anywhere")
    def test_uncreatable_tmp_dir_dies_with_fix(self):
        locked = self.root / "locked"
        locked.mkdir()
        os.chmod(str(locked), 0o500)
        self.addCleanup(os.chmod, str(locked), 0o700)
        assert_dies(self, settings.finalise, {"tmp_dir": str(locked / "tmp")}, "kiconnect", contains="cannot create")

    def test_saved_old_tmp_value_kept(self):
        old = self.root / "tmp-opencode-old"
        old.mkdir()
        settings.SETTINGS_FILE.write_text(json.dumps({"tmp_dir": str(old), "directories_confirmed": True}))
        with captured_stderr():
            out = settings.ensure("kiconnect", interactive=False)
        self.assertEqual(out["tmp_dir"], str(old))


class DryRun(IsolatedHome):
    def test_dry_run_writes_nothing(self):
        before = self.files_under(self.home)
        with captured_stderr() as err:
            out = settings.ensure("kiconnect", interactive=False, dry_run=True)
        self.assertEqual(self.files_under(self.home), before)
        self.assertFalse(settings.SETTINGS_FILE.exists())
        self.assertFalse(os.path.exists(out["tmp_dir"]), "dry run created the temp folder")
        self.assertIn("[dry-run] would save", err.getvalue())


class NonInteractiveFirstRun(IsolatedHome):
    def setUp(self):
        super().setUp()
        self.conda = self.root / "conda"
        self.conda.mkdir()
        p = mock.patch.object(settings, "detect_conda_base", lambda: str(self.conda))
        p.start()
        self.addCleanup(p.stop)

    def test_detected_conda_not_granted(self):
        with captured_stderr() as err:
            out = settings.ensure("kiconnect", interactive=False)
        self.assertIsNone(out["conda_base"])
        self.assertFalse(out["directories_confirmed"])
        self.assertEqual(settings.allowed_dirs(out), [out["tmp_dir"]])
        self.assertIn(str(self.conda), err.getvalue())  # still shown as a suggestion

    def test_one_flag_does_not_confirm_detected_values(self):
        envs = self.root / "envs"
        envs.mkdir()
        with captured_stderr():
            out = settings.ensure("kiconnect", interactive=False, overrides={"envs_dir": str(envs)})
        self.assertEqual(out["envs_dir"], str(envs))
        self.assertIsNone(out["conda_base"])
        self.assertEqual(sorted(settings.allowed_dirs(out)), sorted([str(envs), out["tmp_dir"]]))

    def test_conda_granted_when_given_as_flag(self):
        with captured_stderr():
            out = settings.ensure("kiconnect", interactive=False, overrides={"conda_base": str(self.conda)})
        self.assertEqual(out["conda_base"], str(self.conda))


class StrictLoading(IsolatedHome):
    def test_corrupt_settings_json_dies(self):
        settings.SETTINGS_FILE.write_text("{not json")
        assert_dies(self, settings.load, contains=str(settings.SETTINGS_FILE))

    def test_settings_not_an_object_dies(self):
        settings.SETTINGS_FILE.write_text("[1, 2]")
        assert_dies(self, settings.load, contains="expected a JSON object")

    def test_settings_not_utf8_dies(self):
        settings.SETTINGS_FILE.write_bytes(b'{"tmp_dir": "\xff\xfe"}')
        assert_dies(self, settings.load, contains="not UTF-8")

    def test_load_json_unreadable_dies(self):
        assert_dies(self, common.load_json, self.root, contains="cannot read")


if __name__ == "__main__":
    unittest.main()
