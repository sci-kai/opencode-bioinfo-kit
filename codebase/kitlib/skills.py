#!/usr/bin/env python3
"""Skill catalog, selection and installation (library module of opencode-kit).

Sources:
    skills/<group>/<id>/SKILL.md                    self-made skills; every folder under skills/
                                                    except the BioNeMo submodule is a group
                                                    (nf-core, cubi-dev, ...)
    skills/bionemo-agent-toolkit/<category>/**/SKILL.md
                                                    NVIDIA BioNeMo skills (submodule);
                                                    plugins/ only repeats them and is skipped
Target (opencode 2 global skill folder, grouping dirs are allowed):
    ~/.config/opencode/skills/<group>/<id>/
    ~/.config/opencode/skills/.opencode-kit.json   manifest of what the kit installed

Only skills listed in the manifest are ever removed; other skills in the
target folder are left alone, or moved to ~/.config/opencode/backups/ when a
selected skill needs their folder.

Run codebase/opencode-kit.py instead of this file.
"""

import datetime
import os
import re
import shutil
import sys
from pathlib import Path

from .common import (
    OC_SKILLS_DIR,
    SKILLS,
    die,
    ensure_submodules,
    info,
    is_within,
    load_json,
    render,
    warn,
    write_atomic,
)

SKILL_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# names read back from the manifest: upstream skill ids are not always SKILL_ID_RE-clean
# (e.g. underscores), so this only excludes what could leave the folder ('/', '..', empty)
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
BIONEMO = SKILLS / "bionemo-agent-toolkit"
# bionemo top-level folder -> selectable sub-group name
BIONEMO_CATEGORIES = {
    "nim-skills": "bionemo-nim",
    "library-skills": "bionemo-library",
    "open-models-skills": "bionemo-open-models",
    "workflows": "bionemo-workflows",
}
MANIFEST = ".opencode-kit.json"
DEFAULT_SELECTION = "nf-core,cubi-dev"


def own_groups():
    """Self-made skill groups: every visible folder under skills/ except the submodule."""
    return sorted(
        d.name for d in SKILLS.iterdir() if d.is_dir() and not d.name.startswith(".") and d != BIONEMO
    )


class FrontmatterError(ValueError):
    """A SKILL.md that can't be read or whose frontmatter is not closed."""


def read_frontmatter(skill_md):
    """Parse the flat YAML frontmatter of a SKILL.md (incl. > and | block scalars).

    Returns a dict, or None when the file has no frontmatter (then it is an
    index page, not a skill). Raises FrontmatterError when the file can't be read
    or the frontmatter has no closing '---'.
    """
    try:
        lines = skill_md.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as err:
        raise FrontmatterError(f"{skill_md}: cannot read ({err})")
    if not lines or lines[0].strip() != "---":
        return None
    fields, key, block = {}, None, []
    for line in lines[1:]:
        if line.strip() == "---":
            if key is not None:
                fields[key] = " ".join(block).strip()
            return fields
        match = re.match(r"^([A-Za-z_][\w/-]*):\s*(.*)$", line)
        if match and not line.startswith((" ", "\t")):
            # a new top-level key ends the previous block scalar
            if key is not None:
                fields[key] = " ".join(block).strip()
                key, block = None, []
            name, value = match.group(1), match.group(2).strip()
            if value in (">", "|", ">-", "|-", ">+", "|+"):
                key, block = name, []
            else:
                fields[name] = value.strip("'\"")
        elif key is not None:
            block.append(line.strip())
    raise FrontmatterError(f"{skill_md}: frontmatter starts with '---' but has no closing '---'")


def catalog():
    """All installable skills: {id: {id, group, subgroup, src, description, name, problems}}.

    Own skills (skills/<group>/) are strict: unreadable or missing frontmatter and an id
    used twice stop here. An upstream (BioNeMo) skill with broken frontmatter is kept with
    a 'problems' entry, so validate() can drop it with a warning unless it was selected
    by name; an upstream duplicate of an upstream id is dropped with a warning.
    """
    skills = {}

    def add(skill_md, group, subgroup, own):
        problems = []
        try:
            fm = read_frontmatter(skill_md)
        except FrontmatterError as err:
            if own:
                die(f"{err}; fix the frontmatter (--- / name / description / ---)")
            fm, problems = {}, [str(err)]
        if fm is None:
            if own:
                die(f"{skill_md}: no frontmatter; a skill starts with '---', name, description, '---'")
            return  # upstream: no frontmatter = an index/README page, not a skill
        sid = skill_md.parent.name
        if sid in skills:
            first = skills[sid]
            if own or first["group"] in own_groups():
                die(
                    f"duplicate skill id '{sid}': {first['src']} and {skill_md.parent}; "
                    "rename one of the folders (opencode needs unique skill ids)"
                )
            warn(f"upstream skill: duplicate id '{sid}': {skill_md.parent} dropped, {first['src']} kept")
            return
        skills[sid] = {
            "id": sid,
            "group": group,
            "subgroup": subgroup,
            "src": skill_md.parent,
            "description": fm.get("description", ""),
            "name": fm.get("name", ""),
            "problems": problems,
        }

    for group in own_groups():
        for skill_md in sorted((SKILLS / group).glob("*/SKILL.md")):
            add(skill_md, group, group, own=True)
    if not (BIONEMO / ".git").exists():
        ensure_submodules(("bionemo",))
    for folder, subgroup in BIONEMO_CATEGORIES.items():
        for skill_md in sorted((BIONEMO / folder).rglob("SKILL.md")):
            add(skill_md, "bionemo", subgroup, own=False)
    return skills


def explicit_ids(spec, skills):
    """Skill ids named one by one in a selection (not via a group)."""
    sel = groups(skills)
    tokens = [t.strip() for t in (spec or "").split(",") if t.strip()]
    return {t for t in tokens if t in skills and t not in sel}


def validate(skills, explicit=()):
    """Check the skills the way opencode uses them; return the usable ones.

    Strict (ERROR, nothing installed) for our own skill groups and for skills the user
    named explicitly; other upstream skills with a problem are dropped with a WARNING,
    so one broken upstream skill can't block a deploy.
    """
    errors, warnings = [], []
    own = set(own_groups())
    usable = {}
    for sid, s in skills.items():
        where = s["src"] / "SKILL.md"
        hard, soft = list(s.get("problems", [])), []
        if not s["description"] and not hard:
            hard.append(f"{where}: no description (opencode would not advertise it)")
        elif len(s["description"]) > 1024:
            # opencode 2 does not enforce the limit; it only matters for portability
            soft.append(f"{where}: description has {len(s['description'])} chars (portable limit 1024)")
        if s["group"] in own:
            # our own skills follow the portable naming rules exactly
            if not SKILL_ID_RE.match(s["id"]) or len(s["id"]) > 64:
                hard.append(f"{where}: folder name must match {SKILL_ID_RE.pattern}, max 64 chars")
            if s["name"] != s["id"]:
                hard.append(f"{where}: name '{s['name']}' must equal folder name '{s['id']}'")
            errors += hard + soft
        elif hard and sid in explicit:
            errors += [f"{m} (selected by name in --skills)" for m in hard]
        elif hard:
            warnings += [f"{m}; skill '{sid}' dropped" for m in hard]
            continue
        else:
            warnings += soft
        usable[sid] = s
    for msg in warnings:
        warn(f"upstream skill: {msg}")
    if errors:
        die("skill validation failed, nothing installed:\n  " + "\n  ".join(errors))
    return usable


def groups(skills):
    """{selector: [ids]} for every group and sub-group, plus 'all'."""
    sel = {"all": sorted(skills)}
    for s in skills.values():
        sel.setdefault(s["group"], []).append(s["id"])
        if s["subgroup"] != s["group"]:
            sel.setdefault(s["subgroup"], []).append(s["id"])
    return {k: sorted(v) for k, v in sel.items()}


def resolve_selection(spec, skills):
    """Turn 'nf-core,bionemo-nim,evo2-nim' into a sorted list of skill ids."""
    sel = groups(skills)
    chosen = set()
    for token in [t.strip() for t in spec.split(",") if t.strip()]:
        if token == "none":
            continue
        if token in sel:
            chosen.update(sel[token])
        elif token in skills:
            chosen.add(token)
        else:
            die(
                f"--skills: unknown selector '{token}'. Use groups ({', '.join(sorted(sel))}), "
                "skill ids (codebase/opencode-kit.py list-skills) or 'none'"
            )
    return sorted(chosen)


def read_manifest(target=None):
    """The kit's record of installed skills, or an empty one; stops on a corrupt file.

    A corrupt manifest is not treated as empty: the kit would then forget which skill
    folders are its own and back up its own copies as user skills on every deploy.
    """
    target = OC_SKILLS_DIR if target is None else target
    path = target / MANIFEST
    if not path.is_file():
        return {"selection": None, "installed": {}}
    fix = (
        f"repair it or delete it (the kit then no longer knows which folders under {target} it "
        "installed; it backs them up instead of replacing them) and deploy again"
    )
    data = load_json(path, expect=dict, fix=fix)
    installed = data.get("installed", {})
    selection = data.get("selection")
    if not isinstance(installed, dict) or not all(
        isinstance(ids, list) and all(isinstance(i, str) for i in ids) for ids in installed.values()
    ):
        die(f"{path}: 'installed' must map group names to lists of skill ids; {fix}")
    if selection is not None and not isinstance(selection, str):
        die(f"{path}: 'selection' must be text like 'nf-core,cubi-dev'; {fix}")
    return {**data, "installed": installed, "selection": selection}


def unknown_selectors(spec, skills):
    """Tokens of a selection that are neither a group, a skill id, nor 'none'."""
    sel = groups(skills)
    tokens = [t.strip() for t in (spec or "").split(",") if t.strip()]
    return [t for t in tokens if t != "none" and t not in sel and t not in skills]


def default_selection(skills, interactive, fallback=None):
    """Selection to use when --skills is not given.

    Order: the previous selection (manifest), else ask in a terminal, else `fallback`
    (derived from the chosen agent packages), else DEFAULT_SELECTION.
    """
    previous = read_manifest().get("selection")
    if previous:
        unknown = unknown_selectors(previous, skills)
        if unknown:
            die(
                f"{OC_SKILLS_DIR / MANIFEST}: the saved skill selection '{previous}' names unknown "
                f"selector(s) {', '.join(unknown)} (renamed or removed skills); choose again with "
                "--skills <selection> (see: codebase/opencode-kit.py list-skills)"
            )
        info(f"using the previous skill selection: {previous}")
        return previous
    default = fallback or DEFAULT_SELECTION
    if not interactive:
        info(f"no skill selection given; installing '{default}'")
        return default
    sel = groups(skills)
    print("\nSkill groups (comma-separated; groups or single skill ids; 'none'):", file=sys.stderr)
    for name in [*own_groups(), "bionemo", *sorted(BIONEMO_CATEGORIES.values()), "all"]:
        print(f"  {name:22} {len(sel.get(name, []))} skills", file=sys.stderr)
    answer = input(f"Install which skills? [{default}]: ").strip()
    return answer or default


def _ignore_nested_skills(src_root):
    """copytree ignore function: skip .git and sub-folders that are skills themselves."""

    def ignore(directory, names):
        skipped = {".git"}
        for name in names:
            sub = Path(directory) / name
            # a nested skill is installed on its own; inside a skill opencode would not see it
            if sub.is_dir() and (sub / "SKILL.md").is_file() and sub != src_root:
                skipped.add(name)
        return skipped & set(names)

    return ignore


def prepare(selection_spec, skills):
    """Validate the catalog and the selection; return (usable skills, wanted ids). Writes nothing."""
    unknown = unknown_selectors(selection_spec, skills)
    if unknown:
        resolve_selection(selection_spec, skills)  # stops with the list of valid selectors
    usable = validate(skills, explicit_ids(selection_spec, skills))
    wanted = [sid for sid in resolve_selection(selection_spec, skills) if sid in usable]
    return usable, wanted


def _manifest_entries(manifest, target, path):
    """{(group, id)} of the manifest that are safe to touch; unsafe entries are skipped with a warning.

    Entries come from a file on disk, so they are checked before any folder is removed:
    plain names (no '/', not '.' or '..') whose folder stays inside `target`.
    """
    root = os.path.realpath(str(target))
    entries = set()
    for group, ids in manifest.get("installed", {}).items():
        for sid in ids:
            if not (SAFE_NAME_RE.match(group) and SAFE_NAME_RE.match(sid)) or {group, sid} & {".", ".."}:
                warn(f"{path}: entry '{group}/{sid}' is not a plain skill name; skipped, nothing removed there")
                continue
            folder = os.path.realpath(os.path.join(root, group, sid))
            if not is_within(folder, root) or folder == root:
                warn(f"{path}: entry '{group}/{sid}' points outside {target}; skipped, nothing removed there")
                continue
            entries.add((group, sid))
    return entries


def _backup_dir(target):
    """New, unique ~/.config/opencode/backups/skills-<YYYYMMDD>-<HHMMSS>-<n>/ (not created)."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = target.parent / "backups"
    n = 1
    while (root / f"skills-{stamp}-{n}").exists():
        n += 1
    return root / f"skills-{stamp}-{n}"


def _move_to_backup(path, backup_root, rel):
    """Move a folder into the backup folder (keeping `rel` below it); return the new path."""
    dest = backup_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest))
    return dest


def _swap_in(src, dest):
    """Copy skill `src` to `dest` via a temp sibling and renames (no half-copied skill)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tag = f"{os.getpid()}"
    new = dest.parent / f".{dest.name}.opencode-kit-new-{tag}"
    old = dest.parent / f".{dest.name}.opencode-kit-old-{tag}"
    for leftover in (new, old):
        if leftover.exists():
            shutil.rmtree(leftover)
    shutil.copytree(src, new, ignore=_ignore_nested_skills(src))
    if dest.exists():
        os.replace(str(dest), str(old))
    os.replace(str(new), str(dest))
    if old.exists():
        shutil.rmtree(old)


def install(selection_spec, skills, target=None, dry_run=False, prepared=None):
    """Install the selected skills, remove de-selected kit-managed ones.

    Only folders listed in the manifest are kit-managed. A folder in the way that is not
    (the user's own skill, or a flat copy of the old layout) is moved to
    ~/.config/opencode/backups/skills-<stamp>-<n>/ instead of being deleted.
    """
    target = OC_SKILLS_DIR if target is None else target
    skills, wanted = prepared or prepare(selection_spec, skills)
    manifest_path = target / MANIFEST
    manifest = read_manifest(target)
    previous = _manifest_entries(manifest, target, manifest_path)
    new = {(skills[sid]["group"], sid) for sid in wanted}

    # skills of an earlier deploy.py were copied flat to <target>/<id>; they would now
    # duplicate the grouped copies, so move away those that carry our own skill name
    legacy = []
    for sid in wanted:
        flat = target / sid / "SKILL.md"
        try:
            fm = read_frontmatter(flat) if flat.is_file() else None
        except FrontmatterError:
            fm = None
        if fm is not None and fm.get("name") == skills[sid]["name"]:
            legacy.append(target / sid)
    remove = sorted(previous - new)
    foreign = [
        (skills[sid]["group"], sid)
        for sid in wanted
        if (target / skills[sid]["group"] / sid).exists() and (skills[sid]["group"], sid) not in previous
    ]
    if dry_run:
        info(f"[dry-run] would install {len(new)} skills into {target}: {', '.join(wanted) or '-'}")
        if remove:
            info(f"[dry-run] would remove de-selected: {', '.join(sid for _, sid in remove)}")
        if legacy:
            info(f"[dry-run] would move {len(legacy)} flat legacy copies (old layout) to backups/")
        if foreign:
            info(f"[dry-run] would move {len(foreign)} skill folder(s) not installed by the kit to backups/: "
                 + ", ".join(f"{g}/{s}" for g, s in foreign))
        return wanted
    target.mkdir(parents=True, exist_ok=True)
    backup = _backup_dir(target)
    for path in legacy:
        moved = _move_to_backup(path, backup, path.name)
        warn(f"moved the flat legacy skill copy {path} (old layout) to {moved}")
    for group, sid in remove:
        folder = target / group / sid
        if not folder.exists():
            continue
        if not (folder / "SKILL.md").is_file():
            warn(f"{folder}: listed in {manifest_path} but has no SKILL.md; not removed, check it by hand")
            continue
        shutil.rmtree(folder)
    if remove:
        info(f"removed de-selected skills: {', '.join(sid for _, sid in remove)}")
    for group, sid in foreign:
        path = target / group / sid
        moved = _move_to_backup(path, backup, os.path.join(group, sid))
        warn(f"{path} was not installed by the kit (your own skill?); moved it to {moved} before installing "
             f"the kit's '{sid}'. Rename your copy to keep both")
    for sid in wanted:
        s = skills[sid]
        # replace our own copy completely so deleted upstream files disappear too
        _swap_in(s["src"], target / s["group"] / sid)
    installed = {}
    for group, sid in sorted(new):
        installed.setdefault(group, []).append(sid)
    record = {
        "selection": selection_spec,
        "installed": installed,
        "updated": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    write_atomic(manifest_path, render(record))
    info(f"installed {len(wanted)} skills into {target} ({', '.join(f'{g}: {len(i)}' for g, i in installed.items()) or 'none'})")
    return wanted


def print_list(skills):
    """Human-readable catalog for 'opencode-kit.py list-skills'."""
    manifest = read_manifest()
    installed = {sid for ids in manifest.get("installed", {}).values() for sid in ids}
    sel = groups(skills)
    print("Selectors: " + ", ".join(f"{k} ({len(v)})" for k, v in sorted(sel.items())))
    print(f"Installed selection: {manifest.get('selection') or '-'}\n")
    for s in sorted(skills.values(), key=lambda x: (x["subgroup"], x["id"])):
        mark = "*" if s["id"] in installed else " "
        desc = s["description"][:90] + ("…" if len(s["description"]) > 90 else "")
        print(f"{mark} {s['subgroup']:20} {s['id']:34} {desc}")
    print("\n* = installed")


if __name__ == "__main__":
    sys.exit("ERROR: library module; run codebase/opencode-kit.py")
