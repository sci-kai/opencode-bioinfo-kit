#!/usr/bin/env python3
"""Tests for kitlib.skills: manifest safety, backups, atomic install, upstream tolerance.

A fake skills/ tree (own groups + fake BioNeMo submodule) is built in a temp folder;
the target is the fake ~/.config/opencode/skills of IsolatedHome.
Run from the repo root:
    python3 -m unittest discover -s codebase/tests -t codebase
"""

import json
import unittest
from unittest import mock

from kitlib import skills
from tests.kit_isolation import IsolatedHome, assert_dies, captured_stderr


def skill_md(folder, name=None, description="does a thing", raw=None):
    """Write folder/SKILL.md (raw text, or a valid frontmatter)."""
    folder.mkdir(parents=True, exist_ok=True)
    text = raw if raw is not None else f"---\nname: {name or folder.name}\ndescription: {description}\n---\nbody\n"
    (folder / "SKILL.md").write_text(text, encoding="utf-8")


class FakeSkills(IsolatedHome):
    def setUp(self):
        super().setUp()
        self.src = self.root / "repo-skills"
        self.bionemo = self.src / "bionemo-agent-toolkit"
        (self.bionemo / ".git").mkdir(parents=True)
        skill_md(self.src / "nf-core" / "nf-core-lint")
        skill_md(self.src / "cubi-dev" / "data-format-choose")
        skill_md(self.bionemo / "nim-skills" / "evo2-nim")
        for p in (mock.patch.object(skills, "SKILLS", self.src), mock.patch.object(skills, "BIONEMO", self.bionemo)):
            p.start()
            self.addCleanup(p.stop)

    def install(self, spec, dry_run=False):
        with captured_stderr() as err:
            skills.install(spec, skills.catalog(), target=self.oc_skills, dry_run=dry_run)
        return err.getvalue()

    def manifest(self, installed, selection="nf-core"):
        self.oc_skills.mkdir(parents=True, exist_ok=True)
        (self.oc_skills / skills.MANIFEST).write_text(json.dumps({"selection": selection, "installed": installed}))


class ManifestSafety(FakeSkills):
    def test_traversal_entries_skipped_nothing_deleted(self):
        victim = self.root / "victim"
        skill_md(victim)
        self.manifest({"..": ["victim"], "nf-core": ["../../../victim", "..", ""], "a/b": ["c"]})
        err = self.install("none")
        self.assertTrue((victim / "SKILL.md").is_file(), "a manifest entry deleted a folder outside the skills dir")
        self.assertIn("not a plain skill name", err)

    def test_symlink_outside_not_followed(self):
        outside = self.root / "outside"
        skill_md(outside)
        (self.oc_skills / "nf-core").mkdir(parents=True)
        (self.oc_skills / "nf-core" / "evil").symlink_to(outside)
        self.manifest({"nf-core": ["evil"]})
        err = self.install("none")
        self.assertTrue((outside / "SKILL.md").is_file())
        self.assertIn("points outside", err)

    def test_folder_without_skill_md_not_removed(self):
        folder = self.oc_skills / "nf-core" / "old-skill"
        folder.mkdir(parents=True)
        (folder / "notes.txt").write_text("mine")
        self.manifest({"nf-core": ["old-skill"]})
        err = self.install("none")
        self.assertTrue((folder / "notes.txt").is_file())
        self.assertIn("has no SKILL.md", err)

    def test_deselected_kit_skill_removed(self):
        self.install("nf-core")
        self.install("none")
        self.assertFalse((self.oc_skills / "nf-core" / "nf-core-lint").exists())

    def test_corrupt_manifest_dies(self):
        self.oc_skills.mkdir(parents=True)
        (self.oc_skills / skills.MANIFEST).write_text("{broken")
        assert_dies(self, skills.read_manifest, self.oc_skills, contains="delete it")

    def test_manifest_wrong_shape_dies(self):
        self.manifest({"nf-core": "nf-core-lint"})
        assert_dies(self, skills.read_manifest, self.oc_skills, contains="'installed'")


class Install(FakeSkills):
    def test_users_own_skill_moved_to_backups(self):
        own = self.oc_skills / "nf-core" / "nf-core-lint"
        skill_md(own, description="my own version")
        err = self.install("nf-core")
        backups = list((self.oc / "backups").glob("skills-*-1/nf-core/nf-core-lint/SKILL.md"))
        self.assertEqual(len(backups), 1, err)
        self.assertIn("my own version", backups[0].read_text())
        self.assertIn("does a thing", (own / "SKILL.md").read_text())
        self.assertIn("WARNING:", err)

    def test_kit_copy_replaced_completely(self):
        self.install("nf-core")
        stale = self.oc_skills / "nf-core" / "nf-core-lint" / "stale.txt"
        stale.write_text("x")
        self.install("nf-core")
        self.assertFalse(stale.exists())
        self.assertFalse((self.oc / "backups").exists(), "kit-managed copy was backed up as foreign")
        leftovers = [p.name for p in (self.oc_skills / "nf-core").iterdir() if p.name.startswith(".")]
        self.assertEqual(leftovers, [])

    def test_dry_run_writes_nothing(self):
        own = self.oc_skills / "nf-core" / "nf-core-lint"
        skill_md(own, description="mine")
        before = self.files_under(self.home)
        self.install("all", dry_run=True)
        self.assertEqual(self.files_under(self.home), before)

    def test_unknown_saved_selection_dies(self):
        self.manifest({}, selection="nf-core,gone-group")
        assert_dies(self, skills.default_selection, skills.catalog(), False, contains="--skills")


class UpstreamTolerance(FakeSkills):
    def test_broken_upstream_skill_dropped_with_warning(self):
        skill_md(self.bionemo / "nim-skills" / "broken-nim", raw="---\nname: broken-nim\nno closing line\n")
        skill_md(self.bionemo / "nim-skills" / "nodesc-nim", raw="---\nname: nodesc-nim\n---\n")
        err = self.install("all")
        self.assertIn("WARNING:", err)
        self.assertTrue((self.oc_skills / "bionemo" / "evo2-nim").is_dir())
        self.assertFalse((self.oc_skills / "bionemo" / "broken-nim").exists())
        self.assertFalse((self.oc_skills / "bionemo" / "nodesc-nim").exists())

    def test_broken_upstream_skill_selected_by_name_dies(self):
        skill_md(self.bionemo / "nim-skills" / "broken-nim", raw="---\nname: broken-nim\n")
        with captured_stderr():
            catalog = skills.catalog()
        assert_dies(self, skills.install, "broken-nim", catalog, target=self.oc_skills, contains="selected by name")
        self.assertFalse(self.oc_skills.exists(), "something was installed although validation failed")

    def test_upstream_duplicate_of_own_id_dies_naming_both(self):
        skill_md(self.bionemo / "nim-skills" / "nf-core-lint")
        text = assert_dies(self, skills.catalog, contains="duplicate skill id 'nf-core-lint'")
        self.assertIn(str(self.src / "nf-core" / "nf-core-lint"), text)
        self.assertIn(str(self.bionemo / "nim-skills" / "nf-core-lint"), text)

    def test_upstream_duplicate_of_upstream_warns(self):
        skill_md(self.bionemo / "library-skills" / "evo2-nim")
        with captured_stderr() as err:
            cat = skills.catalog()
        self.assertIn("duplicate id 'evo2-nim'", err.getvalue())
        self.assertIn("evo2-nim", cat)

    def test_own_skill_without_frontmatter_dies(self):
        skill_md(self.src / "nf-core" / "nf-core-bad", raw="# no frontmatter\n")
        assert_dies(self, skills.catalog, contains="no frontmatter")

    def test_own_skill_unterminated_frontmatter_dies(self):
        skill_md(self.src / "cubi-dev" / "data-bad", raw="---\nname: data-bad\n")
        assert_dies(self, skills.catalog, contains="no closing")


if __name__ == "__main__":
    unittest.main()
