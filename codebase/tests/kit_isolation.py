#!/usr/bin/env python3
"""Test helper: run kitlib against a throwaway HOME instead of the real ~/.config/opencode.

Every module-level path constant that points into ~/.config/opencode is patched to a
temporary folder, and HOME is set to a fake home inside it, so no test can touch the
user's real configuration.
"""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kitlib import common, deploy, kb, settings, skills


class IsolatedHome(unittest.TestCase):
    """Base class: self.root (temp root), self.home (fake HOME), self.oc (fake ~/.config/opencode)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="opencode-kit-test-")
        self.addCleanup(tmp.cleanup)
        # realpath: on macOS the temp folder is a symlink (/var -> /private/var)
        self.root = Path(os.path.realpath(tmp.name))
        self.home = self.root / "home"
        self.oc = self.home / ".config" / "opencode"
        self.oc.mkdir(parents=True)
        self.oc_skills = self.oc / "skills"
        self.oc_data = self.home / ".local" / "share" / "opencode"
        env = {k: v for k, v in os.environ.items() if k not in ("XDG_CONFIG_HOME", "XDG_DATA_HOME")}
        patches = [
            mock.patch.dict(os.environ, {**env, "HOME": str(self.home)}, clear=True),
            mock.patch.object(common, "OC_CONFIG_DIR", self.oc),
            mock.patch.object(common, "OC_DATA_DIR", self.oc_data),
            mock.patch.object(common, "OC_SKILLS_DIR", self.oc_skills),
            mock.patch.object(common, "OC_KB_DIR", self.oc / "cubi-kb"),
            mock.patch.object(settings, "SETTINGS_FILE", self.oc / "opencode-kit-settings.json"),
            mock.patch.object(settings, "DEFAULT_TMP", str(self.root / "systmp" / "opencode-tester")),
            mock.patch.object(settings, "detect_conda_base", lambda: None),
            mock.patch.object(skills, "OC_SKILLS_DIR", self.oc_skills),
            mock.patch.object(deploy, "OC_CONFIG_DIR", self.oc),
            mock.patch.object(deploy, "OC_SKILLS_DIR", self.oc_skills),
            mock.patch.object(deploy, "OC_KB_DIR", self.oc / "cubi-kb"),
            mock.patch.object(deploy, "DEPLOY_MANIFEST", self.oc / ".opencode-kit-deploy.json"),
            mock.patch.object(deploy, "PROMPT_DIR", self.oc / "prompts"),
            mock.patch.object(deploy, "INSTR_DIR", self.oc / "instructions"),
            mock.patch.object(kb, "KB_SOURCE", self.root / "kb-source.json"),
            mock.patch.object(Path, "home", classmethod(lambda cls: self.home)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def files_under(self, folder):
        """Sorted relative paths of all files below folder (empty if missing)."""
        folder = Path(folder)
        if not folder.exists():
            return []
        return sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())


@contextlib.contextmanager
def captured_stderr():
    """Collect stderr (kit messages) into a StringIO."""
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        yield buf


def assert_dies(test, func, *args, contains=None, **kwargs):
    """func(...) must stop with SystemExit and an ERROR: message (optionally containing text)."""
    with captured_stderr() as err:
        with test.assertRaises(SystemExit) as ctx:
            func(*args, **kwargs)
    test.assertNotEqual(ctx.exception.code, 0)
    text = err.getvalue()
    test.assertIn("ERROR:", text)
    if contains:
        test.assertIn(contains, text)
    return text
