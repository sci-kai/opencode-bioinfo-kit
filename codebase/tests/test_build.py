#!/usr/bin/env python3
"""Tests for kitlib.build: token substitution, symlinked folders, leftover markers.

Run from the repo root:
    python3 -m unittest discover -s codebase/tests -t codebase
"""

import json
import os
import unittest

from kitlib import build
from kitlib.common import REPO
from tests.kit_isolation import IsolatedHome, assert_dies


class TokenSubstitution(unittest.TestCase):
    def test_url_with_quote_and_backslash_keeps_json_valid(self):
        url = 'http://host:1234/v1?x="a"\\b'
        config = {"providers": {"lmstudio": {"settings": {"baseURL": "{LMSTUDIO_URL}"}}}, "n": [1, "{LMSTUDIO_URL}/x"]}
        self.assertTrue(build.contains_token(config, "{LMSTUDIO_URL}"))
        out = build.substitute(config, url, "{LMSTUDIO_URL}")
        self.assertEqual(out["providers"]["lmstudio"]["settings"]["baseURL"], url)
        self.assertEqual(out["n"], [1, url + "/x"])
        self.assertEqual(json.loads(json.dumps(out)), out)
        self.assertFalse(build.contains_token(out, "{LMSTUDIO_URL}"))

    def test_repo_default_token_unchanged(self):
        self.assertEqual(build.substitute({"a": "{REPO}/x"}, "/r"), {"a": "/r/x"})


class SymlinkedFolders(IsolatedHome):
    def test_rules_for_written_and_resolved_path(self):
        target = self.root / "real-scratch"
        target.mkdir()
        link = self.root / "scratch-link"
        os.symlink(str(target), str(link))
        rules = build.user_permission_rules({"scratch_dir": str(link)})
        resources = {r["resource"] for r in rules}
        self.assertEqual(resources, {str(link), f"{link}/*", str(target), f"{target}/*"})

    def test_plain_folder_gets_two_rules(self):
        folder = self.root / "plain"
        folder.mkdir()
        self.assertEqual(len(build.user_permission_rules({"tmp_dir": str(folder)})), 2)


class Markers(unittest.TestCase):
    def test_if_setting_blocks_follow_settings(self):
        text = "a\n<!-- opencode-kit:if-setting scratch_dir -->\nS\n<!-- opencode-kit:end -->\n" \
               "<!-- opencode-kit:if-no-setting scratch_dir -->\nN\n<!-- opencode-kit:end -->\n"
        self.assertEqual(build._keep_package_blocks(text, set(), {"scratch_dir": "/x"}), "a\nS\n")
        self.assertEqual(build._keep_package_blocks(text, set(), {}), "a\nN\n")

    def test_unclosed_block_left_over_dies_naming_file(self):
        text = build._keep_package_blocks("<!-- opencode-kit:if-setting x -->\nno end\n", set(), {})
        assert_dies(self, build.check_no_markers, text, "configs/agents/x/prompt.md", contains="configs/agents/x/prompt.md")

    def test_unknown_marker_dies(self):
        assert_dies(self, build.check_no_markers, "<!-- opencode-kit:typo -->\n", "f.md", contains="typo")

    def test_real_prompts_and_instructions_render_clean(self):
        selected, _ = build.select_agents(REPO, "all")
        prompts = build.render_prompts(REPO, selected, {"tmp_dir": "/t"})
        self.assertTrue(prompts)
        for name, text in prompts.items():
            self.assertNotIn(build.MARKER_PREFIX, text, name)
        base = json.loads((REPO / "configs" / "shared" / "base.json").read_text())
        rendered, _ = build.render_instructions(REPO, REPO, base, {"tmp_dir": "/t"}, "/out")
        for name, text in rendered.items():
            self.assertNotIn(build.MARKER_PREFIX, text, name)


if __name__ == "__main__":
    unittest.main()
