#!/usr/bin/env python3
"""Deploy the configuration into opencode's config folder and test it (library module of opencode-kit).

The config folder is $XDG_CONFIG_HOME/opencode, else ~/.config/opencode (common.config_dir).
Deploy writes (and only writes) these locations:
    <config>/opencode.json                  generated config (previous one -> backups/)
    <config>/prompts/<name>.md              rendered agent prompts (routing table, blocks)
    <config>/instructions/<name>.md         global rules rendered with the user's folders
    <config>/cubi-kb/*.md                   KB concatenations read by the agents
    <config>/skills/<group>/<id>            selected skills (+ .opencode-kit.json manifest)
    <config>/opencode-kit-settings.json     the user's directory settings, when they changed
    <config>/.opencode-kit-deploy.json      deploy manifest: backend, agent packages, files written
    <config>/backups/                       replaced opencode.json, the user's own files that were
                                            in the way of prompts/instructions/skills
    <tmp_dir>                               the agents' temp folder (created, mode 0700)
A symlink at a written file is kept: the text goes to its target (common.write_atomic).

Run codebase/opencode-kit.py instead of this file.
"""

import datetime
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from . import build, kb, skills
from . import settings as user_settings
from .common import (
    BUILD,
    OC_CONFIG_DIR,
    OC_KB_DIR,
    MAX_TRIES,
    OC_SKILLS_DIR,
    REPO,
    die,
    ensure_submodules,
    find_opencode,
    info,
    load_json,
    opencode_json,
    opencode_version,
    render,
    require_v2,
    run_opencode,
    warn,
    write_atomic,
)
from .install import stored_providers


def _drift_warning(old, new, changed):
    """WARNING when the CUBI digest is older than the checked-out KB (no network)."""
    if old == new or changed is None:  # None: kb.drift already warned it cannot compare
        return
    warn(
        f"the CUBI digest was derived from KB {old[:7]}, the KB is now at {new[:7]} "
        f"({len(changed)} page(s) changed). Update it: codebase/opencode-kit.py update-cubi-digest"
    )


def preview_configs(backends=None, out_dir=BUILD, agent_spec=None):
    """Write configs and KB concatenations into generated/ for review; install nothing."""
    ensure_submodules()
    selected, _ = build.select_agents(REPO, agent_spec)
    # preview with the saved directory settings, or harmless examples for a new user
    settings = user_settings.load() or {"tmp_dir": user_settings.DEFAULT_TMP}
    if not settings.get("lmstudio_url"):
        settings = dict(settings, lmstudio_url="http://localhost:1234/v1")
        info("no LM Studio URL configured; preview uses http://localhost:1234/v1")
    write_prompts(build.render_prompts(REPO, selected, settings), out_dir / "prompts", dry_run=False)
    write_instructions(render_instruction_files(settings, out_dir / "instructions"), out_dir / "instructions", dry_run=False)
    configs = build.build_all(
        REPO, backends, REPO, packages=agent_spec, prompt_dir=out_dir / "prompts",
        settings=settings, instr_dir=out_dir / "instructions",
    )
    for backend, config in configs.items():
        target = out_dir / backend / "opencode.json"
        write_atomic(target, render(config))
        info(f"wrote {target} ({len(config['agents'])} agents)")
    kb.concat(out_dir / "cubi-kb")
    catalog = skills.catalog()
    usable = skills.validate(catalog)
    info(f"validated {len(usable)} skills ({', '.join(f'{k}: {len(v)}' for k, v in skills.groups(usable).items() if k in (*skills.own_groups(), 'bionemo'))})")
    _drift_warning(*kb.drift(fetch=False))


def _unique_backup(folder, stem, suffix):
    """folder/<stem><suffix>, or with -2, -3, ... when that name is taken."""
    path = folder / f"{stem}{suffix}"
    n = 2
    while path.exists():
        path = folder / f"{stem}-{n}{suffix}"
        n += 1
    return path


def write_config(config, dry_run):
    """Back up the active opencode.json and write the new one."""
    target = OC_CONFIG_DIR / "opencode.json"
    text = render(config)
    if dry_run:
        info(f"[dry-run] would write {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        old_text = target.read_text(encoding="utf-8", errors="replace")
        if old_text == text:
            info(f"{target} already up to date")
            return
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = _unique_backup(target.parent / "backups", f"opencode_{stamp}", ".json")
        backup.parent.mkdir(exist_ok=True)
        shutil.copy2(target, backup)
        info(f"backed up previous config to {backup}")
        try:
            old = json.loads(old_text)
        except ValueError:
            old = None
        extra = sorted(set(old) - set(config)) if isinstance(old, dict) else []
        if extra:
            warn(
                f"{target} had top-level key(s) the kit does not generate: {', '.join(extra)}. "
                f"They are dropped now and kept in {backup}. The kit rewrites opencode.json on "
                "every deploy: make lasting changes in configs/ of this repository"
            )
    write_atomic(target, text)
    info(f"wrote {target}")


DEPLOY_MANIFEST = OC_CONFIG_DIR / ".opencode-kit-deploy.json"
PROMPT_DIR = OC_CONFIG_DIR / "prompts"
INSTR_DIR = OC_CONFIG_DIR / "instructions"


def render_instruction_files(settings, instr_dir):
    """{file name: text} of the global instruction files rendered with the user's directories."""
    base = load_json(REPO / "configs" / "shared" / "base.json")
    rendered, _ = build.render_instructions(REPO, REPO, base, settings, instr_dir)
    return rendered


def kit_written_files():
    """Paths (relative to the config folder) an earlier deploy wrote, from the deploy manifest.

    Empty set: no deploy yet, so every existing file belongs to the user. None: the
    manifest predates the 'files' record; files with the kit's names are taken as the kit's.
    """
    if not DEPLOY_MANIFEST.is_file():
        return set()
    files = read_deploy_manifest().get("files")
    if files is None:
        return None
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        die(f"{DEPLOY_MANIFEST}: 'files' must be a list of paths, got {files!r}; repair it or delete the file")
    return set(files)


def _move_foreign(path, text, known):
    """Move a file the kit did not write (not in `known`) to backups/ before it is replaced."""
    rel = f"{path.parent.name}/{path.name}"
    if known is None or rel in known or not os.path.lexists(str(path)):
        return
    try:
        if not path.is_symlink() and path.read_text(encoding="utf-8") == text:
            return  # identical: nothing of the user's is lost
    except (OSError, UnicodeDecodeError):
        pass
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = _unique_backup(OC_CONFIG_DIR / "backups", f"{path.parent.name}_{path.stem}_{stamp}", path.suffix)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(backup))
    warn(f"{path} was not written by the kit and is replaced now; your file was moved to {backup}")


def write_instructions(rendered, instr_dir, dry_run, known=None):
    """Write the rendered global instruction files (render_instruction_files).

    known: files the kit wrote before (kit_written_files); others are backed up first.
    """
    if dry_run:
        info(f"[dry-run] would write {len(rendered)} rendered instruction file(s) to {instr_dir}")
        return
    for name, text in rendered.items():
        _move_foreign(instr_dir / name, text, known)
        write_atomic(instr_dir / name, text)
    info(f"wrote {len(rendered)} instruction file(s) with your directories to {instr_dir}")


def read_deploy_manifest():
    """What the last deploy-configs installed (backend, agent packages), or {}."""
    if not DEPLOY_MANIFEST.is_file():
        return {}
    return load_json(
        DEPLOY_MANIFEST, expect=dict,
        fix="repair it or delete it (then pass --agents on the next deploy)",
    )


def choose_agent_packages(spec, interactive):
    """Agent package selection: --agents, else previous deploy, else ask, else all."""
    if spec:
        return ",".join(build.resolve_packages(REPO, spec))
    previous = read_deploy_manifest().get("agent_packages")
    if previous:
        known = build.load_packages(REPO)
        tokens = [t.strip() for t in str(previous).split(",") if t.strip()]
        unknown = [t for t in tokens if t not in known and t != "all"]
        if unknown:
            die(
                f"{DEPLOY_MANIFEST}: the saved agent packages '{previous}' name unknown package(s) "
                f"{', '.join(unknown)} (available: {', '.join(sorted(known))}); choose again with "
                "--agents <package,...> or --agents all"
            )
        info(f"using the previous agent packages: {previous}")
        return ",".join(build.resolve_packages(REPO, previous))
    if not interactive:
        info("no agent packages given; installing all")
        return ",".join(build.resolve_packages(REPO, "all"))
    print("\nAgent packages (comma-separated, or 'all'; core is always installed):", file=sys.stderr)
    for name, pkg in build.load_packages(REPO).items():
        flag = " (always)" if pkg.get("required") else ""
        print(f"  {name:16} {pkg['description']}{flag}", file=sys.stderr)
    answer = input("Install which agent packages? [all]: ").strip() or "all"
    return ",".join(build.resolve_packages(REPO, answer))


def write_prompts(rendered, prompt_dir, dry_run, known=None):
    """Write the rendered prompts (build.render_prompts: routing table, conditional blocks).

    known: files the kit wrote before (kit_written_files); others are backed up first.
    """
    if dry_run:
        info(f"[dry-run] would write {len(rendered)} rendered prompt(s) to {prompt_dir}")
        return
    for name, text in rendered.items():
        _move_foreign(prompt_dir / f"{name}.md", text, known)
        write_atomic(prompt_dir / f"{name}.md", text)
    info(f"wrote {len(rendered)} rendered prompt(s) with the routing table to {prompt_dir}")


def deploy(backend, skill_spec=None, dry_run=False, run_tests=True, live=False, agent_spec=None,
           dir_overrides=None, before_write=None):
    """Build and install config, KB files and skills for one backend, then test.

    Everything is read, rendered and validated first (settings, agent packages, prompts,
    instructions, config, KB files, skill catalog and selection); only then is anything
    written, so an error leaves the previous deployment untouched. `before_write(config)`
    runs between the two phases (setup-opencode stores the API key there).
    """
    ensure_submodules(dry_run=dry_run)
    exe = find_opencode()
    if dry_run and not exe:
        warn("opencode not installed; dry run continues without it")
    else:
        exe = require_v2(exe)
        info(f"opencode {opencode_version(exe)} at {exe}")
    if backend not in build.list_backends(REPO):
        die(f"backend '{backend}' not found (available: {', '.join(build.list_backends(REPO))})")

    # phase 1: read, render, validate (no writes) ------------------------------
    interactive = sys.stdin.isatty() and not dry_run
    # directories outside the project that this user grants (asked once, then saved)
    # a dry run may build with the example LM Studio set; a real deploy needs the user's own
    settings, settings_changed = user_settings.resolve(
        backend, interactive, dir_overrides, create=False, allow_example=dry_run
    )
    info("allowed folders outside the project: " + (", ".join(user_settings.allowed_dirs(settings)) or "none"))
    packages = choose_agent_packages(agent_spec, interactive)
    selected, _ = build.select_agents(REPO, packages)
    prompts = build.render_prompts(REPO, selected, settings)
    instructions = render_instruction_files(settings, INSTR_DIR)
    config = build.build_all(
        REPO, [backend], REPO, packages=packages, prompt_dir=PROMPT_DIR, settings=settings, instr_dir=INSTR_DIR
    )[backend]
    info(f"agent packages: {packages}")
    info(f"built '{backend}' config: {len(config['agents'])} agents, default model {config['model']}")
    kb_texts = kb.render_concat()
    catalog = skills.catalog()
    pkg_info = build.load_packages(REPO)
    fallback = ",".join(sorted({g for p in packages.split(",") for g in pkg_info[p].get("skills", [])})) or "none"
    spec = skill_spec or skills.default_selection(catalog, interactive=interactive, fallback=fallback)
    prepared = skills.prepare(spec, catalog)
    known = kit_written_files()
    # is the CUBI digest still derived from the checked-out KB? (local only, no network)
    _drift_warning(*kb.drift(fetch=False))
    if before_write:
        before_write(config)

    # phase 2: write ---------------------------------------------------------------
    user_settings.persist(settings, settings_changed, dry_run)
    write_prompts(prompts, PROMPT_DIR, dry_run, known)
    write_instructions(instructions, INSTR_DIR, dry_run, known)
    write_config(config, dry_run)
    jsonc = OC_CONFIG_DIR / "opencode.jsonc"
    if jsonc.is_file():
        warn(f"{jsonc} also exists and is merged with opencode.json; keep it minimal or remove it")
    # KB concatenations the agents read on demand
    if dry_run:
        info(f"[dry-run] would write KB concatenations to {OC_KB_DIR}")
    else:
        kb.write_concat(OC_KB_DIR, kb_texts)
    skills.install(spec, catalog, target=OC_SKILLS_DIR, dry_run=dry_run, prepared=prepared)
    old_v1_dir = Path.home() / ".opencode" / "skills"
    if old_v1_dir.is_dir():
        warn(f"{old_v1_dir} is the opencode 1 skill folder; opencode 2 ignores it (safe to delete)")

    if dry_run:
        info("dry run: nothing written, tests skipped")
        return config
    written = {f"{PROMPT_DIR.name}/{n}.md" for n in prompts} | {f"{INSTR_DIR.name}/{n}" for n in instructions}
    # files of earlier deploys that are not rendered now stay the kit's while they exist
    earlier = {f for f in (known or set()) if (OC_CONFIG_DIR / f).exists()}
    record = {
        "backend": backend,
        "agent_packages": packages,
        "files": sorted(written | earlier),
        "updated": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    write_atomic(DEPLOY_MANIFEST, render(record))
    if run_tests:
        test(live=live)
    info("deployed; start opencode in a project folder with: opencode")
    return config


def _agent_ref(resolved):
    """'provider/model#variant' of an agent as 'opencode debug agents' reports it."""
    model = resolved.get("model") or {}
    if not model:
        return None
    ref = f"{model.get('providerID')}/{model.get('id')}"
    return f"{ref}#{model['variant']}" if model.get("variant") else ref


# opencode 2.2.6 loads agent definitions from {agent,agents}/**/*.md and {mode,modes}/*.md in
# every config folder; their frontmatter permissions are appended and win (last match)
AGENT_DEF_DIRS = ("agent", "agents", "mode", "modes")


def agent_definition_dirs(config_dir=None):
    """Agent/mode definition folders in opencode's config folder (they bypass the sandbox)."""
    config_dir = OC_CONFIG_DIR if config_dir is None else config_dir
    return [config_dir / d for d in AGENT_DEF_DIRS if os.path.lexists(str(config_dir / d))]


def test(live=False):
    """Check the deployed setup; print a PASS/FAIL table and stop if anything failed."""
    results = []

    def check(name, ok, detail=""):
        results.append((name, ok, detail))

    exe = find_opencode()
    version = opencode_version(exe) if exe else None
    check("opencode 2 installed", bool(version and version.startswith("2.")), f"{exe} {version}")
    if not version or not version.startswith("2."):
        _report(results)
    cfg_path = OC_CONFIG_DIR / "opencode.json"
    if not cfg_path.is_file():
        check("config present", False, f"{cfg_path} missing; run deploy")
        _report(results)
    config = load_json(cfg_path)
    check("config present", True, str(cfg_path))

    # strict sandbox: external directories = deny all first, then only standard + user folders
    rules = config.get("permissions", [])
    ext = [r for r in rules if r.get("action") == "external_directory"]
    first_ok = bool(ext) and (ext[0]["resource"], ext[0]["effect"]) == ("*", "deny")
    standard = {
        r["resource"].replace("{REPO}", str(REPO))
        for r in build.substitute_oc_dirs(load_json(REPO / "configs" / "shared" / "permissions.json"))
        if r["action"] == "external_directory" and r["effect"] == "allow" and r["resource"] != "<user-directories>"
    }
    saved = user_settings.load() or {}
    granted = {r["resource"] for r in build.user_permission_rules(saved)}
    unexpected = sorted(r["resource"] for r in ext if r["effect"] == "allow" and r["resource"] not in standard | granted)
    agent_dirs = agent_definition_dirs()
    problems = []
    if not first_ok:
        problems.append("first rule is not 'external_directory * deny'")
    if unexpected:
        problems.append(f"unexpected allowed: {', '.join(unexpected)}")
    if agent_dirs:
        problems.append(
            f"{', '.join(map(str, agent_dirs))} exist(s): opencode loads agent definitions from there and their "
            "permissions override the sandbox; remove it, or move the definitions into configs/agents/ of this repo"
        )
    check(
        "directory sandbox",
        not problems,
        "; ".join(problems) or f"{len(user_settings.allowed_dirs(saved))} user folder(s) + standard folders",
    )

    # instruction files must exist, or agents silently run without the global rules
    missing = [p for p in config.get("instructions", []) if not Path(p).expanduser().is_file()]
    check("instruction files", not missing, ", ".join(missing) or f"{len(config.get('instructions', []))} found")

    # every agent resolves to the configured model and its prompt text (not a path)
    resolved = opencode_json(exe, ["debug", "agents"])
    if resolved is None:
        check("agents resolve", False, "'opencode debug agents' gave no JSON (retry; see docs/deploy.md)")
    else:
        by_id = {a["id"]: a for a in resolved}
        bad = []
        for name, agent in config.get("agents", {}).items():
            got = by_id.get(name)
            if got is None:
                bad.append(f"{name}: missing")
                continue
            if "system" in agent:
                text = got.get("system") or ""
                if len(text) < 200 or text.startswith(("file:", "{file:")):
                    bad.append(f"{name}: prompt not loaded ({text[:40]!r})")
            if agent.get("model") and _agent_ref(got) != agent["model"]:
                bad.append(f"{name}: model {_agent_ref(got)} != {agent['model']}")
        check("agents resolve", not bad, "; ".join(bad) or f"{len(config.get('agents', {}))} agents: models and prompts OK")

    # credentials for every provider (LM Studio may run without a token)
    keyed = sorted(p for p in config.get("providers", {}) if p != "lmstudio")
    stored = stored_providers(exe) if keyed else set()
    if stored is None:
        check("credentials", False, "'opencode auth list' gave no JSON")
    else:
        missing = [p for p in keyed if p not in stored]
        check("credentials", not missing, f"missing: {', '.join(missing)}" if missing else ("stored" if keyed else "not needed (LM Studio)"))

    # KB concatenations that agents read on demand
    kb_files = [OC_KB_DIR / f"{c}-kb-agents-instructions.md" for c in kb.CATEGORIES]
    missing = [str(p) for p in kb_files if not p.is_file()]
    check("CUBI KB files", not missing, ", ".join(missing) or str(OC_KB_DIR))

    # what a real session sends to the model: advertised skills, global rules, agent prompt
    manifest = skills.read_manifest()
    wanted = {sid for ids in manifest.get("installed", {}).values() for sid in ids}
    session = capture_session(exe, config)
    if session is None:
        check("session: skills", False, "no request captured from 'opencode run' (retry; see docs/deploy.md)")
    else:
        missing = sorted(wanted - session["skills"])
        check(
            "session: skills",
            not missing,
            f"not advertised: {', '.join(missing)}" if missing else f"all {len(wanted)} installed skills advertised",
        )
        rules = [Path(p).expanduser() for p in config.get("instructions", [])]
        lost = []
        for p in rules:
            line = _first_line(p)
            if line is None:
                lost.append(f"{p.name} (file missing or unreadable)")
            elif line not in session["system"]:
                lost.append(p.name)
        check("session: instructions", not lost, f"not in system prompt: {', '.join(lost)}" if lost else f"{len(rules)} files in system prompt")
        build_prompt = config.get("agents", {}).get("build", {}).get("system", "")
        path = build_prompt[len("{file:"):-1] if build_prompt.startswith("{file:") else None
        line = _first_line(Path(path)) if path else ""
        if line is None:
            check("session: build prompt", False, f"{path} missing or unreadable; run deploy-configs again")
        else:
            ok = path is None or line in session["system"]
            check("session: build prompt", ok, "in system prompt" if ok else f"{path} text not in system prompt")
        # the orchestrator must be able to route to every installed subagent
        subagents = sorted(n for n, a in config.get("agents", {}).items() if a.get("mode") == "subagent")
        unrouted = [n for n in subagents if f"`{n}`" not in session["system"]]
        check(
            "session: routing",
            not unrouted,
            f"not in the routing table: {', '.join(unrouted)}" if unrouted else f"all {len(subagents)} subagents routable",
        )

    if live:
        res = run_opencode(exe, ["run", "--archived", "Reply with exactly one word: pong"], retries=3, timeout=600)
        answer = (res.stdout.strip() if res else "")[-200:]
        check("live model call", bool(res and res.returncode == 0 and "pong" in answer.lower()), answer or "no answer")
    _report(results)


def _first_line(path):
    """First non-empty line of a text file (used to recognise it inside a prompt).

    None when the file is missing or unreadable (the caller reports a FAIL row).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


class _Capture(http.server.BaseHTTPRequestHandler):
    """Fake OpenAI-compatible endpoint: stores request bodies, answers with an error."""

    bodies = []

    def do_POST(self):  # noqa: N802 (http.server naming)
        length = int(self.headers.get("content-length", 0))
        _Capture.bodies.append(self.rfile.read(length))
        self.send_response(400)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error":{"message":"opencode-kit capture","type":"invalid_request_error"}}')

    def log_message(self, *args):
        pass


def capture_session(exe, config):
    """Run one opencode session against a local fake endpoint and inspect its request.

    The deployed config, skills and KB files are copied into a throwaway HOME,
    the model is pointed at a local capture server, and 'opencode run' sends one
    message. The captured request shows exactly what the model would get. Returns
    {"skills": set of advertised skill ids, "system": system prompt text} or None.
    No API key is needed and the real ~/.local/share/opencode is not touched.
    """
    _Capture.bodies = []
    try:
        server = http.server.HTTPServer(("127.0.0.1", 0), _Capture)
    except OSError as err:
        warn(f"cannot start the local capture server on 127.0.0.1: {err}")
        return None
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="opencode-kit-test-") as tmp:
            home = Path(tmp)
            cfg_dir = home / ".config" / "opencode"
            cfg_dir.mkdir(parents=True)
            for name in ("skills", "cubi-kb"):
                if (OC_CONFIG_DIR / name).is_dir():
                    shutil.copytree(OC_CONFIG_DIR / name, cfg_dir / name)
            test_cfg = json.loads(json.dumps(config))
            test_cfg["providers"]["kitcapture"] = {
                "name": "opencode-kit capture",
                "package": "@opencode/ai/providers/openai-compatible",
                "settings": {"baseURL": f"http://127.0.0.1:{port}/v1", "apiKey": "capture"},
                "models": {"m": {"name": "capture", "capabilities": {"tools": True}, "limit": {"context": 200000, "output": 1000}}},
            }
            test_cfg["model"] = "kitcapture/m"
            for name in ("build", "title"):
                test_cfg.setdefault("agents", {}).setdefault(name, {})["model"] = "kitcapture/m"
            (cfg_dir / "opencode.json").write_text(render(test_cfg), encoding="utf-8")
            (home / "project").mkdir()
            env = {"PATH": os.environ.get("PATH", ""), "HOME": str(home), "TERM": "dumb", "OPENCODE_DISABLE_MODELS_FETCH": "1"}
            for attempt in range(1, MAX_TRIES + 1):
                if attempt > 1:
                    info(f"retrying the captured 'opencode run' session (try {attempt} of {MAX_TRIES})")
                try:
                    subprocess.run(
                        [exe, "run", "--archived", "--agent", "build", "ping", "--standalone"],
                        cwd=home / "project", env=env, capture_output=True, text=True, timeout=180,
                    )
                except subprocess.TimeoutExpired:
                    warn("captured 'opencode run' session timed out after 180 s")
                if any(b"<available_skills>" in b or b'"tools"' in b for b in _Capture.bodies):
                    break
    except (OSError, shutil.Error) as err:
        # e.g. opencode binary missing, temp folder not writable; reported as a FAIL row
        warn(f"captured 'opencode run' session could not run: {err}")
        return None
    finally:
        server.shutdown()
        server.server_close()
    for raw in _Capture.bodies:
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            continue
        # the main agent request carries tools; the title request does not
        if not body.get("tools"):
            continue
        system = "\n".join(
            m["content"] if isinstance(m["content"], str) else json.dumps(m["content"])
            for m in body.get("messages", [])
            if m.get("role") == "system"
        )
        return {"skills": set(re.findall(r"<id>([^<]+)</id>", system)), "system": system}
    return None


def _report(results):
    """Print the test table; exit non-zero if any check failed."""
    print("\nDeployment test:", file=sys.stderr)
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:20} {detail}", file=sys.stderr)
    failed = [r for r in results if not r[1]]
    if failed:
        die(f"{len(failed)} check(s) failed")
    info(f"all {len(results)} checks passed")


if __name__ == "__main__":
    sys.exit("ERROR: library module; run codebase/opencode-kit.py")
