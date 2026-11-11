#!/usr/bin/env python3
"""opencode-kit: install, deploy, test and maintain this opencode 2 configuration.

Commands:
  Install and deploy
    setup-opencode <backend>    fresh machine: install opencode 2, store + check the API key,
                                then deploy-configs and test-deployment
    deploy-configs <backend>    generate the config from configs/ and write it to
                                ~/.config/opencode/opencode.json, together with the CUBI
                                knowledge-base files and the selected skills; then test
    test-deployment             check the deployed setup (--live: also a real model call)
    preview-configs             generate configs + knowledge-base files into generated/ and
                                validate all skills, WITHOUT installing anything (for review)
  Directories
    configure-directories       state which folders outside the project opencode may use
                                (conda, envs, scratch, temp, extra); saved per user
    configure-lmstudio          choose the LM Studio models (local backend): pick from the
                                server's list (heavy/fast or one per tier, plus extra models),
                                or import a hand-written model set (--models-file)
  Agents and skills
    list-agents                 show agent packages (core, nf-core, dev, bioinformatics, refdata) and what is installed
    list-skills                 show installable skills (nf-core, BioNeMo) and what is installed
    install-skills              install/remove skills by selection, config untouched
  CUBI rules digest (cubi-rules/cubi-rules-condensed.md)
    check-cubi-digest           is the digest derived from the checked-out knowledge base?
    update-cubi-digest          write the AI prompt that updates the digest and guide the
                                steps (--run: let opencode apply it)
    print-cubi-digest-prompt    print that AI prompt
    mark-cubi-digest-synced     record that the digest matches the checked-out knowledge base
  Maintenance
    update-git-submodules       move the submodules (knowledge base, BioNeMo skills) to upstream

Backends: configs/backends/<name>/backend.json (kiconnect, local).
Agent packages (--agents): comma-separated packages from configs/agents/packages.json or all;
'core' is always installed. The orchestrator's routing table only lists installed agents.
The 'refdata' package needs seqc2-toolkit, an external tool that is not included.
Skill selection (--skills): comma-separated groups (nf-core, bionemo, bionemo-nim,
refdata, bionemo-library, bionemo-open-models, bionemo-workflows, all), skill ids, or none.

Examples:
    codebase/opencode-kit.py setup-opencode kiconnect --skills nf-core,bionemo-nim
    codebase/opencode-kit.py deploy-configs local --dry-run
    codebase/opencode-kit.py test-deployment --live
    codebase/opencode-kit.py update-git-submodules && codebase/opencode-kit.py update-cubi-digest --run

Docs: docs/deploy.md, docs/skills.md, docs/updating-cubi-rules.md
"""

import argparse
import sys
from pathlib import Path

# checked before the library is imported: it needs Python 3.8 or newer
if sys.version_info < (3, 8):
    sys.exit(f"ERROR: Python {sys.version.split()[0]} found; opencode-kit needs Python 3.8 or newer (python3 --version)")

# the library lives next to this script
sys.path.insert(0, str(Path(__file__).resolve().parent))

import kitlib  # noqa: E402
from kitlib import build, deploy, install, kb, lmstudio, skills  # noqa: E402
from kitlib import settings as user_settings  # noqa: E402
from kitlib.common import REPO, SUBMODULES, die, ensure_submodules, git, info, warn  # noqa: E402

KIT = "codebase/opencode-kit.py"


def cmd_setup_opencode(args):
    """Fresh machine: opencode 2, API key, deploy-configs, test-deployment."""
    install.check_prerequisites()
    ensure_submodules(dry_run=args.dry_run)
    exe = install.ensure_opencode(args.opencode_version, args.upgrade_from_v1, args.dry_run)

    def store_key(config):
        # runs inside deploy() after everything is validated, before anything is written
        if args.no_key:
            info("skipping the API key step (--no-key)")
        else:
            install.handle_key(exe, config, args.api_key_env, args.replace_key, args.dry_run)

    deploy.deploy(
        args.backend, args.skills, args.dry_run, run_tests=not args.no_test, live=args.live,
        agent_spec=args.agents, dir_overrides=dir_overrides(args), before_write=store_key,
    )
    info("setup complete. Open a new shell (PATH), cd into a project and run: opencode")


def cmd_update_git_submodules(args):
    """Move submodules to their upstream heads and say what to do next."""
    names = args.only or list(SUBMODULES)
    ensure_submodules(names)
    for name in names:
        path = SUBMODULES[name]
        before = git(["rev-parse", "HEAD"], cwd=path)
        git(["submodule", "update", "--init", "--remote", str(path.relative_to(REPO))])
        after = git(["rev-parse", "HEAD"], cwd=path)
        if before == after:
            info(f"{path.relative_to(REPO)}: already at upstream ({after[:7]})")
            continue
        log = git(["log", "--oneline", f"{before}..{after}"], cwd=path)
        info(f"{path.relative_to(REPO)}: {before[:7]} -> {after[:7]}\n{log}")
    changed = git(["status", "--porcelain", "--", *[str(SUBMODULES[n].relative_to(REPO)) for n in names]])
    if "kb" in names:
        print(file=sys.stderr)
        kb.status()
    if changed:
        print(
            "\nNext steps:\n"
            f"  - knowledge base changed?  {KIT} update-cubi-digest   (AI-guided digest update)\n"
            f"  - redeploy (skills, KB):   {KIT} deploy-configs <backend>\n"
            f"  - commit the new pins:     git -C {REPO} add {' '.join(str(SUBMODULES[n].relative_to(REPO)) for n in names)} && git commit",
            file=sys.stderr,
        )


def dir_overrides(args):
    """Directory flags of a command as a settings dict (unset flags omitted)."""
    return {
        "conda_base": getattr(args, "conda_base", None),
        "envs_dir": getattr(args, "envs_dir", None),
        "scratch_dir": getattr(args, "scratch_dir", None),
        "scratch_mount": getattr(args, "scratch_mount", None),
        "tmp_dir": getattr(args, "tmp_dir", None),
        "extra_dirs": getattr(args, "extra_dir", None),
        "lmstudio_url": getattr(args, "lmstudio_url", None),
    }


def cmd_configure_directories(args):
    """Ask for (or set from flags) the user's directories; redeploy to apply them."""
    if args.show:
        current = user_settings.load()
        print(user_settings.describe(current) if current else "not configured yet")
        return
    settings = user_settings.ensure(args.backend, sys.stdin.isatty(), dir_overrides(args), reconfigure=True)
    print(user_settings.describe(settings))
    info(f"apply with: {KIT} deploy-configs <backend>")


def _pairs(values, flag):
    """['a=b', ...] -> {'a': 'b'}; stops on a value without '='."""
    out = {}
    for value in values or []:
        k, sep, v = value.partition("=")
        if not sep or not k.strip() or not v.strip():
            die(f"{flag} '{value}': expected NAME=VALUE")
        out[k.strip()] = v.strip()
    return out


def _contexts(values):
    """--context N (all models) or ID=N (one model) -> {ID or '*': N}."""
    out = {}
    for value in values or []:
        mid, sep, num = value.rpartition("=") if "=" in value else ("*", "=", value)
        if not num.strip().isdigit():
            die(f"--context '{value}': expected a whole number or MODEL_ID=NUMBER")
        if not mid.strip():
            die(f"--context '{value}': model ID before '=' is empty; expected MODEL_ID=NUMBER or NUMBER")
        out[mid.strip()] = lmstudio.check_context(int(num), f"--context '{value}'")
    return out


def cmd_configure_lmstudio(args):
    """Choose the LM Studio model set (from the server, or a hand-written file)."""
    current = user_settings.load() or {}
    if args.show or args.export:
        models = current.get("lmstudio_models")
        if not models:
            die(f"no LM Studio model set saved yet; choose one with: {KIT} configure-lmstudio")
        backend = lmstudio.local_backend()
        try:
            checked = lmstudio.validate(models, backend["tiers"], "lmstudio_models", backend.get("tier_roles"))
        except lmstudio.ModelSetError as err:
            die(f"{err}; choose again with: {KIT} configure-lmstudio")
        if args.export:
            lmstudio.export(checked, args.export)
        else:
            print("\n".join(lmstudio.describe(checked)))
        return
    url = lmstudio.normalise_url(args.url or current.get("lmstudio_url"), "--url")
    if not url:
        if not sys.stdin.isatty():
            die("no LM Studio URL saved; pass --url http://<host>:1234/v1")
        url = lmstudio.normalise_url(input("LM Studio server URL, e.g. http://localhost:1234/v1: "), "URL")
        if not url:
            die("no URL given; nothing was changed")
    key = lmstudio.api_key()
    if args.models_file:
        chosen = lmstudio.load_models_file(args.models_file)
        try:
            lmstudio.check_against_server(chosen, lmstudio.list_models(url, key), url)
        except lmstudio.ServerError as err:
            warn(f"LM Studio: {err}; the model set is saved unchecked, check it when the server runs")
    else:
        chosen = lmstudio.choose(
            url, key=key, interactive=sys.stdin.isatty(), current=current.get("lmstudio_models"),
            heavy=args.heavy, fast=args.fast, tier_models=_pairs(args.tier, "--tier"),
            extras=args.extra, contexts=_contexts(args.context),
        )
        if not chosen:
            die(f"could not read the model list from {url}; start the LM Studio server, or write the "
                f"model set by hand and pass it with --models-file (example: "
                f"configs/backends/local/lmstudio-models.example.json)")
    settings = user_settings.ensure("local", False, {"lmstudio_url": url, "lmstudio_models": chosen})
    print(user_settings.describe(settings))
    info(f"apply with: {KIT} deploy-configs local")


def list_agents():
    """Print agent packages with their agents; mark the installed packages."""
    installed = set((deploy.read_deploy_manifest().get("agent_packages") or "").split(","))
    agents, _ = build.select_agents(REPO, "all")
    for name, pkg in build.load_packages(REPO).items():
        mark = "*" if name in installed else " "
        members = sorted(n for n, s in agents.items() if s["package"] == name)
        flag = " (always installed)" if pkg.get("required") else ""
        print(f"{mark} {name:16} {pkg['description']}{flag}")
        print(f"  {'':16} agents: {', '.join(members)}")
        if pkg.get("skills"):
            print(f"  {'':16} default skills: {', '.join(pkg['skills'])}")
    print("\n* = installed by the last deploy-configs; select with --agents <package,...>")


def main():
    parser = argparse.ArgumentParser(
        prog="opencode-kit.py",
        description=__doc__.split("\n\n")[0],
        epilog="Run '<command> --help' for the options of a command. Overview: see the module docstring or README.md.",
    )
    parser.add_argument("--version", action="version", version=f"opencode-kit {kitlib.__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")
    backends = build.list_backends(REPO)

    def add_deploy_opts(p):
        p.add_argument("--agents", help="agent packages, e.g. nf-core,dev,bioinformatics,refdata or all (core always; default: previous, or ask, or all)")
        p.add_argument("--skills", help="skill selection (default: previous selection, or ask, or the packages' skill groups)")
        p.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
        p.add_argument("--no-test", action="store_true", help="skip test-deployment")
        p.add_argument("--live", action="store_true", help="also test a real model call")
        add_dir_opts(p)

    def add_dir_opts(p):
        g = p.add_argument_group("directories outside the project (saved per user; asked when not set)")
        g.add_argument("--conda-base", help="conda installation (default: conda info --base)")
        g.add_argument("--envs-dir", help="folder with project conda envs and their spec files")
        g.add_argument("--scratch-dir", help="folder for large data, runs and caches")
        g.add_argument("--scratch-mount", help="mount point to check before using --scratch-dir")
        g.add_argument("--tmp-dir", help="temporary folder for agents (default <system temp>/opencode-<user>)")
        g.add_argument("--extra-dir", action="append", help="further folder opencode may use (repeatable)")
        g.add_argument("--lmstudio-url", help="LM Studio server URL (local backend)")

    # install and deploy ------------------------------------------------------
    p = sub.add_parser("setup-opencode", help="fresh machine: install opencode 2, store the API key, deploy, test")
    p.add_argument("backend", choices=backends)
    p.add_argument("--opencode-version", default="latest", help="opencode 2 version when installing: latest or 2.x.y")
    p.add_argument("--upgrade-from-v1", action="store_true", help="replace an installed opencode 1 (one-way)")
    p.add_argument("--api-key-env", help="read the API key from this environment variable")
    p.add_argument("--replace-key", action="store_true", help="store a new key even if one exists")
    p.add_argument("--no-key", action="store_true", help="skip the API key step")
    add_deploy_opts(p)
    p.set_defaults(func=cmd_setup_opencode)

    p = sub.add_parser(
        "deploy-configs",
        help="write the generated config, CUBI KB files and selected skills to ~/.config/opencode, then test",
    )
    p.add_argument("backend", choices=backends)
    add_deploy_opts(p)
    p.set_defaults(
        func=lambda a: deploy.deploy(a.backend, a.skills, a.dry_run, not a.no_test, a.live, a.agents, dir_overrides(a))
    )

    p = sub.add_parser(
        "configure-directories",
        help="state which folders outside the project opencode may use (asks; or set with flags)",
    )
    p.add_argument("--backend", choices=backends, default="kiconnect", help="backend whose needs are checked")
    p.add_argument("--show", action="store_true", help="only print the current settings")
    add_dir_opts(p)
    p.set_defaults(func=cmd_configure_directories)

    p = sub.add_parser(
        "configure-lmstudio",
        help="choose the LM Studio model set: from the server's list or a hand-written file",
    )
    p.add_argument("--url", help="LM Studio server URL, e.g. http://192.168.1.20:1234/v1 (default: saved)")
    p.add_argument("--heavy", help="model ID for the heavy tiers: codegen, careful (default: ask or suggest)")
    p.add_argument("--fast", help="model ID for the fast tiers: light, main, writing (default: ask or suggest)")
    p.add_argument("--tier", action="append", metavar="TIER=ID", help="model for one tier (repeatable; wins over --heavy/--fast)")
    p.add_argument("--extra", action="append", metavar="ID", help="also declare this model for switching by hand (repeatable)")
    p.add_argument("--context", action="append", metavar="[ID=]N", help="context length the model(s) are loaded with (repeatable; default: ask or detect)")
    p.add_argument("--models-file", help="use a hand-written model set (format: configs/backends/local/lmstudio-models.example.json); works offline")
    p.add_argument("--show", action="store_true", help="print the saved model set")
    p.add_argument("--export", metavar="FILE", help="write the saved model set to FILE for editing (then --models-file FILE)")
    p.set_defaults(func=cmd_configure_lmstudio)

    p = sub.add_parser("test-deployment", help="check the deployed setup in ~/.config/opencode")
    p.add_argument("--live", action="store_true", help="also test a real model call")
    p.set_defaults(func=lambda a: deploy.test(a.live))

    p = sub.add_parser(
        "preview-configs",
        help="generate configs + KB files into generated/ and validate skills; installs nothing",
    )
    p.add_argument("--backend", action="append", choices=backends, help="backend (repeatable; default: all)")
    p.add_argument("--agents", help="agent packages to include (default: all)")
    p.set_defaults(func=lambda a: deploy.preview_configs(a.backend, agent_spec=a.agents))

    # agents --------------------------------------------------------------------
    p = sub.add_parser("list-agents", help="show agent packages, their agents and what is installed")
    p.set_defaults(func=lambda a: list_agents())

    # skills ------------------------------------------------------------------
    p = sub.add_parser("list-skills", help="show installable and installed skills")
    p.set_defaults(func=lambda a: skills.print_list(skills.catalog()))

    p = sub.add_parser("install-skills", help="install the selected skills, remove de-selected ones (config untouched)")
    p.add_argument("--skills", required=True, help="selection, e.g. nf-core,bionemo-nim or none")
    p.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    p.set_defaults(func=lambda a: skills.install(a.skills, skills.catalog(), dry_run=a.dry_run))

    # CUBI digest ---------------------------------------------------------------
    p = sub.add_parser("check-cubi-digest", help="is the CUBI digest derived from the checked-out knowledge base?")
    p.add_argument("--fetch", action="store_true", help="also check upstream for newer knowledge-base commits")
    p.set_defaults(func=lambda a: sys.exit(0 if kb.status(a.fetch) else 3))

    p = sub.add_parser("update-cubi-digest", help="write the AI prompt that updates the CUBI digest and guide the steps")
    p.add_argument("--run", action="store_true", help="let opencode apply the prompt in this repo")
    p.add_argument("--model", help="model for --run, e.g. ki_connect/qwen-3.8-27B#t0.6-p0.95")
    p.add_argument("--agent", default="build", help="opencode agent for --run (default: build)")
    p.add_argument("--full", action="store_true", help="re-derive from all rule pages, even if in sync")
    p.set_defaults(func=lambda a: kb.update(a.run, a.model, a.agent, a.full))

    p = sub.add_parser("print-cubi-digest-prompt", help="print the AI prompt for the CUBI digest update")
    p.add_argument("--full", action="store_true", help="re-derive from all rule pages")
    p.set_defaults(func=lambda a: print(kb.build_prompt(a.full), end=""))

    p = sub.add_parser("mark-cubi-digest-synced", help="record that the CUBI digest matches the checked-out knowledge base")
    p.set_defaults(func=lambda a: kb.mark_synced())

    # maintenance -----------------------------------------------------------------
    p = sub.add_parser("update-git-submodules", help="move the submodules (knowledge base, BioNeMo skills) to upstream")
    p.add_argument("--only", action="append", choices=list(SUBMODULES), help="only this submodule (repeatable)")
    p.set_defaults(func=cmd_update_git_submodules)

    args = parser.parse_args()
    if not (REPO / ".git").exists():
        die(f"{REPO}: not a git checkout; clone the repository with git (submodules need it)")
    try:
        args.func(args)
    except (KeyboardInterrupt, EOFError):
        print("\nERROR: aborted by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
