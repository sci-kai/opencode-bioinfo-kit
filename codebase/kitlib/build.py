#!/usr/bin/env python3
"""Generate opencode 2 configs from configs/ (library module of opencode-kit).

Sources (all opencode 2 schema): configs/shared/{base,permissions}.json,
configs/agents/<name>/{agent.json,prompt.md}, configs/backends/<b>/backend.json.
"{REPO}" in configs/shared/*.json becomes the checkout path, "{OC_CONFIG}" and
"{OC_DATA}" opencode's config and data folders (XDG-aware, common.config_dir and
common.data_dir); tier sampling
becomes model variants ("provider/model#t0.6-p0.95") because opencode 2 has
no per-agent temperature/top_p.

Run codebase/opencode-kit.py instead of this file.
"""

import json
import os
import re
import sys
from pathlib import Path

from . import common
from .common import REPO, die, load_json

# Fields of agent.json handled by this script; everything else is passed through.
CONTROL_FIELDS = {"tier", "prompt", "package"}
# line in a prompt.md that opencode-kit replaces with the rendered routing table
ROUTING_MARKER = "<!-- opencode-kit:routing -->"
# opencode 1.x agent fields that opencode 2 silently drops; reject them early.
V1_AGENT_FIELDS = {"model", "temperature", "top_p", "env", "tools", "permission", "maxSteps", "disable"}
# Output order of agent fields, so the generated JSON is stable and readable.
FIELD_ORDER = ["description", "mode", "model", "system", "steps"]
AGENT_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
VALID_MODES = {"primary", "subagent", "all"}
VALID_EFFECTS = {"allow", "ask", "deny"}
# built-in opencode 2 agents; an entry without mode/description/prompt is only
# a model override and must name one of these (else v2 creates an empty agent)
V2_BUILTIN_AGENTS = {"build", "plan", "general", "explore", "title", "summary", "compaction"}


def substitute(obj, repo, token="{REPO}"):
    """Replace a placeholder (default {REPO}) in every string of a nested structure.

    Works on the data, not on serialised JSON, so a value with quotes or backslashes
    can't break the config.
    """
    if isinstance(obj, str):
        return obj.replace(token, str(repo))
    if isinstance(obj, list):
        return [substitute(x, repo, token) for x in obj]
    if isinstance(obj, dict):
        return {substitute(k, repo, token): substitute(v, repo, token) for k, v in obj.items()}
    return obj


def substitute_oc_dirs(obj):
    """Replace {OC_CONFIG} and {OC_DATA} with opencode's real config and data folders."""
    obj = substitute(obj, common.OC_CONFIG_DIR, "{OC_CONFIG}")
    return substitute(obj, common.OC_DATA_DIR, "{OC_DATA}")


def contains_token(obj, token):
    """True when any string (key or value) of a nested structure contains `token`."""
    if isinstance(obj, str):
        return token in obj
    if isinstance(obj, list):
        return any(contains_token(x, token) for x in obj)
    if isinstance(obj, dict):
        return any(contains_token(k, token) or contains_token(v, token) for k, v in obj.items())
    return False


# start of every opencode-kit marker; none may be left after rendering
MARKER_PREFIX = "<!-- opencode-kit:"


def check_no_markers(text, where):
    """Stop when a rendered text still contains an opencode-kit marker (unknown or unclosed block)."""
    if MARKER_PREFIX in text:
        line = next(ln for ln in text.splitlines() if MARKER_PREFIX in ln)
        die(
            f"{where}: marker left after rendering: '{line.strip()}'; expected only "
            "routing, if-package/if-setting/if-no-setting <name> blocks closed by "
            "'<!-- opencode-kit:end -->'; fix the marker in the source file"
        )


def load_permissions(path):
    """Read and validate shared/permissions.json (an ordered list of rules)."""
    rules = load_json(path)
    if not isinstance(rules, list):
        die(f"{path}: expected a list of {{action, resource, effect}} rules (opencode 2 schema)")
    for i, rule in enumerate(rules):
        if set(rule) != {"action", "resource", "effect"}:
            die(f"{path}: rule {i} has keys {sorted(rule)}; expected exactly action, resource, effect")
        if rule["effect"] not in VALID_EFFECTS:
            die(f"{path}: rule {i} effect '{rule['effect']}' invalid (expected {sorted(VALID_EFFECTS)})")
    # opencode 2 allows external directories by default; the deny must come first
    first = rules[0] if rules else {}
    if (first.get("action"), first.get("resource"), first.get("effect")) != ("external_directory", "*", "deny"):
        die(f"{path}: first rule must be external_directory '*' deny (opencode 2 allows them by default)")
    return rules


def load_agents(repo):
    """Read and validate every agents/<name>/agent.json; return {name: spec}."""
    agents_dir = repo / "configs" / "agents"
    agents = {}
    # sorted() keeps the generated config order independent of the file system
    for agent_file in sorted(agents_dir.glob("*/agent.json")):
        name = agent_file.parent.name
        if not AGENT_NAME_RE.match(name):
            die(
                f"{agent_file}: folder name '{name}' is not a valid agent name "
                "(expected lower-case a-z0-9 separated by '-')"
            )
        spec = load_json(agent_file)
        # every agent needs a tier, because the backend maps tiers to models
        if "tier" not in spec:
            die(f"{agent_file}: missing 'tier' (expected one of the backend tiers)")
        mode = spec.get("mode")
        if mode is not None and mode not in VALID_MODES:
            die(f"{agent_file}: mode '{mode}' invalid (expected {sorted(VALID_MODES)})")
        # subagents are chosen by their description, so it must exist
        if mode == "subagent" and not spec.get("description"):
            die(f"{agent_file}: subagent needs a non-empty 'description'")
        for field in sorted(V1_AGENT_FIELDS & set(spec)):
            hint = {
                "model": "set 'tier' instead (models are per backend)",
                "temperature": "sampling is set per backend tier",
                "top_p": "sampling is set per backend tier",
                "permission": "use 'permissions' (list of {action, resource, effect})",
                "tools": "use 'permissions'",
                "maxSteps": "use 'steps'",
                "disable": "use 'disabled'",
            }.get(field, "not supported by opencode 2")
            die(f"{agent_file}: field '{field}' not allowed: {hint}")
        is_override_only = not any(k in spec for k in ("prompt", "mode", "description"))
        if is_override_only and name not in V2_BUILTIN_AGENTS:
            die(
                f"{agent_file}: '{name}' is not an opencode 2 built-in agent "
                f"({', '.join(sorted(V2_BUILTIN_AGENTS))}); add mode and description"
            )
        prompt_ref = spec.get("prompt")
        if prompt_ref is not None:
            prompt_file = agents_dir / prompt_ref / "prompt.md"
            if not prompt_file.is_file():
                die(
                    f"{agent_file}: prompt '{prompt_ref}' points to {prompt_file}, "
                    "which does not exist"
                )
        agents[name] = spec
    if not agents:
        die(f"{agents_dir}: no agents/<name>/agent.json found")
    # a prompt.md without agent.json is almost certainly a forgotten agent.json
    for prompt_file in sorted(agents_dir.glob("*/prompt.md")):
        if prompt_file.parent.name not in agents:
            used = any(s.get("prompt") == prompt_file.parent.name for s in agents.values())
            if not used:
                die(f"{prompt_file}: no agent.json next to it and no agent uses it")
    return agents


def variant_id(tdef):
    """Name of the model variant that carries a tier's sampling, or None."""
    if "temperature" not in tdef and "top_p" not in tdef:
        return None
    return f"t{tdef.get('temperature')}-p{tdef.get('top_p')}"


def build_backend(repo, root, backend_name, agents, base, permissions, all_names=None, prompt_dir=None, settings=None):
    """Assemble the config for one backend; paths in it point to `root`."""
    backend_file = repo / "configs" / "backends" / backend_name / "backend.json"
    backend = load_json(backend_file)
    # the local backend's example models are replaced by the user's LM Studio selection
    from .lmstudio import apply_to_backend  # local import: lmstudio imports common only

    backend = apply_to_backend(backend, (settings or {}).get("lmstudio_models"))
    if "provider" in backend:
        die(f"{backend_file}: 'provider' is the opencode 1 key; use 'providers'")
    for key in ("providers", "tiers", "model"):
        if key not in backend:
            die(f"{backend_file}: missing '{key}'")
    tiers = backend["tiers"]
    # deep copy so variants added below don't change the loaded backend
    providers = json.loads(json.dumps(backend["providers"]))
    for pid, pdef in providers.items():
        if "npm" in pdef or "options" in pdef:
            die(f"{backend_file}: provider '{pid}' uses opencode 1 keys npm/options; use package/settings")

    def model_def(model_id, where):
        """Return the provider model dict for 'provider/model', or stop."""
        pid, _, mid = model_id.partition("/")
        mdef = providers.get(pid, {}).get("models", {}).get(mid)
        if mdef is None:
            declared = sorted(f"{p}/{m}" for p, d in providers.items() for m in d.get("models", {}))
            die(f"{where}: model '{model_id}' not declared in 'providers' (declared: {declared})")
        return mdef

    # every tier must point to a declared model; its sampling becomes a variant
    tier_model = {}
    for tier, tdef in tiers.items():
        mdef = model_def(tdef.get("model", ""), f"{backend_file} tier '{tier}'")
        vid = variant_id(tdef)
        ref = tdef["model"]
        if vid:
            if not mdef.get("capabilities", {}).get("temperature", True):
                die(
                    f"{backend_file}: tier '{tier}' sets sampling, but model '{ref}' "
                    "has capabilities.temperature false; remove temperature/top_p from the tier"
                )
            body = {k: tdef[k] for k in ("temperature", "top_p") if k in tdef}
            variants = mdef.setdefault("variants", [])
            if not any(v["id"] == vid for v in variants):
                variants.append({"id": vid, "body": body})
            ref = f"{ref}#{vid}"
        tier_model[tier] = ref
    for pdef in providers.values():
        for mdef in pdef.get("models", {}).values():
            if "variants" in mdef:
                mdef["variants"].sort(key=lambda v: v["id"])

    overrides = backend.get("agent_tiers", {})
    # overrides may name agents of packages that are not selected; only typos are errors
    for name in overrides:
        if name not in (all_names or agents):
            die(f"{backend_file}: agent_tiers names unknown agent '{name}'")
    suffixes = backend.get("tier_description_suffix", {})

    def resolve(tier, where):
        """Resolve a tier name to its 'provider/model[#variant]' reference."""
        if tier not in tier_model:
            die(f"{where}: tier '{tier}' not defined in {backend_file} (has {sorted(tier_model)})")
        return tier_model[tier]

    out_agents = {}
    for name, spec in agents.items():
        tier = overrides.get(name, spec["tier"])
        agent = {}
        if spec.get("description"):
            desc = spec["description"]
            # backend-specific hint (e.g. "slow tier, one file at a time")
            if suffixes.get(tier):
                desc = f"{desc} {suffixes[tier]}"
            agent["description"] = desc
        if "mode" in spec:
            agent["mode"] = spec["mode"]
        agent["model"] = resolve(tier, f"configs/agents/{name}/agent.json")
        if spec.get("prompt"):
            # {file:...} is opencode's substitution syntax; the braces are required
            source = repo / "configs" / "agents" / spec["prompt"] / "prompt.md"
            if MARKER_PREFIX in source.read_text(encoding="utf-8"):
                # rendered copy (routing table of the installed agents, conditional blocks)
                if prompt_dir is None:
                    die(f"{source}: contains opencode-kit markers but no prompt_dir was given to render it")
                path = Path(prompt_dir) / f"{spec['prompt']}.md"
            else:
                path = root / "configs" / "agents" / spec["prompt"] / "prompt.md"
            agent["system"] = "{file:" + str(path) + "}"
        for key, value in spec.items():
            if key not in CONTROL_FIELDS and key not in agent:
                agent[key] = value
        ordered = {k: agent[k] for k in FIELD_ORDER if k in agent}
        ordered.update({k: v for k, v in agent.items() if k not in ordered})
        out_agents[name] = ordered

    config = {
        "$schema": base["$schema"],
        "instructions": base["instructions"],
        "model": resolve(backend["model"], f"{backend_file} 'model'"),
        "permissions": permissions,
    }
    for key, value in base.items():
        if key not in config:
            config[key] = value
    config["providers"] = providers
    config["agents"] = out_agents
    if "compaction" in backend:
        config["compaction"] = backend["compaction"]
    return substitute(config, root)


def list_backends(repo):
    """Names of all backends = folders under backends/ with a backend.json."""
    return sorted(p.parent.name for p in (repo / "configs" / "backends").glob("*/backend.json"))


def load_packages(repo):
    """{package: {description, required, skills}} from configs/agents/packages.json."""
    data = load_json(repo / "configs" / "agents" / "packages.json")
    return data["packages"]


def resolve_packages(repo, spec):
    """Turn 'nf-core,dev' / 'all' into the sorted package list (required ones always included)."""
    packages = load_packages(repo)
    chosen = {name for name, p in packages.items() if p.get("required")}
    for token in [t.strip() for t in (spec or "all").split(",") if t.strip()]:
        if token == "all":
            chosen.update(packages)
        elif token in packages:
            chosen.add(token)
        else:
            die(f"--agents: unknown package '{token}' (available: {', '.join(sorted(packages))}, all)")
    return sorted(chosen)


def select_agents(repo, packages_spec=None):
    """(selected {name: spec}, all agent names) for the chosen agent packages."""
    agents = load_agents(repo)
    known = load_packages(repo)
    for name, spec in agents.items():
        if spec.get("package") not in known:
            die(
                f"configs/agents/{name}/agent.json: package '{spec.get('package')}' not in "
                f"configs/agents/packages.json ({', '.join(sorted(known))})"
            )
    chosen = set(resolve_packages(repo, packages_spec))
    return {n: s for n, s in agents.items() if s["package"] in chosen}, set(agents)


def render_routing(repo, installed):
    """Markdown routing table(s) and tie-breakers for the installed agents only."""
    routing = load_json(repo / "configs" / "agents" / "build" / "routing.json")
    known = set(load_agents(repo))
    for section in routing["sections"]:
        for row in section["rows"]:
            if row["agent"] not in known:
                die(f"configs/agents/build/routing.json: row names unknown agent '{row['agent']}'")
    out = []
    for section in routing["sections"]:
        rows = [r for r in section["rows"] if r["agent"] in installed]
        if not rows:
            continue  # whole section belongs to a package that is not installed
        if section.get("heading"):
            out += [section["heading"], ""]
        if section.get("intro"):
            out += [section["intro"], ""]
        out += [f"| {section['header'][0]} | {section['header'][1]} |", "|---|---|"]
        out += [f"| {r['task']} | `{r['agent']}` |" for r in rows]
        out.append("")
    # a tie-breaker is kept only if every agent it names (in backticks) is installed
    ties = [
        t for t in routing["tie_breakers"]
        if all(name in installed for name in re.findall(r"`([a-z0-9-]+)`", t) if name in known)
    ]
    if ties:
        out += ["Tie-breakers:", ""] + [f"- {t}" for t in ties] + [""]
    return "\n".join(out).rstrip() + "\n"


def render_prompts(repo, selected, settings=None):
    """{prompt name: text} for prompts with opencode-kit markers, rendered.

    The routing marker becomes the table of the installed agents; if-package blocks
    follow the selected packages, if-setting blocks the user's settings (as in the
    instruction files).
    """
    rendered = {}
    table = render_routing(repo, set(selected))
    packages = {spec["package"] for spec in selected.values()}
    for spec in selected.values():
        name = spec.get("prompt")
        if not name or name in rendered:
            continue
        source = repo / "configs" / "agents" / name / "prompt.md"
        text = source.read_text(encoding="utf-8")
        if MARKER_PREFIX in text:
            text = _keep_package_blocks(text.replace(ROUTING_MARKER, table.rstrip()), packages, settings)
            check_no_markers(text, source)
            rendered[name] = text
    return rendered


def _keep_package_blocks(text, packages, settings=None):
    """Resolve conditional blocks ending in '<!-- opencode-kit:end -->' (not nestable).

    '<!-- opencode-kit:if-package P -->'     kept when agent package P is installed
    '<!-- opencode-kit:if-setting K -->'     kept when directory setting K is configured
    '<!-- opencode-kit:if-no-setting K -->'  kept when K is not configured
    Kept blocks lose their marker lines; dropped blocks vanish, so agents never read
    procedures for agents or folders that are not there.
    """
    settings = settings or {}

    def keep(kind, name):
        if kind == "if-package":
            return name in packages
        if kind == "if-setting":
            return bool(settings.get(name))
        return not settings.get(name)  # if-no-setting

    pattern = re.compile(
        r"<!-- opencode-kit:(if-package|if-setting|if-no-setting) ([a-z0-9_-]+) -->\n(.*?)<!-- opencode-kit:end -->\n?",
        re.DOTALL,
    )
    return pattern.sub(lambda m: m.group(3) if keep(m.group(1), m.group(2)) else "", text)


def render_instruction(text, settings, repo):
    """Fill the {{...}} directory placeholders and settings blocks of an instruction file."""
    text = _keep_package_blocks(text, set(), settings)
    values = {
        "ENVS_DIR": settings.get("envs_dir"),
        "CONDA_BASE": settings.get("conda_base"),
        "SCRATCH_DIR": settings.get("scratch_dir"),
        "SCRATCH_MOUNT": settings.get("scratch_mount"),
        "TMP_DIR": settings.get("tmp_dir"),
        "EXTRA_DIRS": ", ".join(f"`{d}`" for d in settings.get("extra_dirs") or []) or None,
        "REPO": str(repo),
        "OC_CONFIG": str(common.OC_CONFIG_DIR),
    }
    for key, value in values.items():
        shown = value if key == "EXTRA_DIRS" else (f"`{value}`" if value else None)
        text = text.replace("{{" + key + "}}", shown or "not configured")
    leftover = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if leftover:
        die(f"instruction placeholder(s) without a value: {', '.join(sorted(set(leftover)))}")
    return text


def render_instructions(repo, root, base, settings, instr_dir):
    """{file name: rendered text} for instruction files with placeholders; paths for base.json."""
    rendered, paths = {}, []
    for entry in base["instructions"]:
        source = Path(entry.replace("{REPO}", str(repo)))
        text = source.read_text(encoding="utf-8")
        if "{{" in text or "opencode-kit:" in text:
            if instr_dir is None:
                die(f"{source}: has placeholders but no instruction output folder was given")
            rendered[source.name] = render_instruction(text, settings, root)
            check_no_markers(rendered[source.name], source)
            paths.append(str(Path(instr_dir) / source.name))
        else:
            paths.append(entry)
    return rendered, paths


def user_permission_rules(settings):
    """external_directory allow rules (folder and its contents) for the user's folders.

    Settings keep each folder as the user wrote it (symlinks not resolved). When it is
    a symlink, the resolved target gets rules too: agents may reach the folder by either
    path. Resolving here (not when saving) follows a moved symlink on the next deploy.
    """
    from .settings import allowed_dirs, check_glob  # local import: settings imports common only

    rules, seen = [], set()
    for folder in allowed_dirs(settings or {}):
        for form in (folder, os.path.realpath(folder)):
            if form in seen:
                continue
            seen.add(form)
            # defensive: settings checked this when saved, but a symlink may have moved since
            check_glob(form, "allowed folder", shown=folder if form != folder else None)
            rules.append({"action": "external_directory", "resource": form, "effect": "allow"})
            rules.append({"action": "external_directory", "resource": f"{form}/*", "effect": "allow"})
    return rules


def build_all(repo, backends=None, root=None, packages=None, prompt_dir=None, settings=None, instr_dir=None):
    """Build {backend: config}; sources from `repo`, paths rendered for `root`.

    packages: agent package selection ('all' if None); prompt_dir: where the rendered
    prompts (render_prompts) are written, so the config can point to them.
    """
    root = root or repo
    base = load_json(repo / "configs" / "shared" / "base.json")
    for v1_key in ("server", "permission", "provider", "agent", "small_model"):
        if v1_key in base:
            die(f"{repo / 'configs' / 'shared' / 'base.json'}: '{v1_key}' is an opencode 1 key; remove it")
    permissions = substitute_oc_dirs(load_permissions(repo / "configs" / "shared" / "permissions.json"))
    # the marker rule becomes the user's own folders, in the same position (order matters)
    marker = [i for i, r in enumerate(permissions) if r["resource"] == "<user-directories>"]
    if len(marker) != 1:
        die("configs/shared/permissions.json: needs exactly one '<user-directories>' rule")
    i = marker[0]
    permissions = permissions[:i] + user_permission_rules(settings) + permissions[i + 1 :]
    _, base["instructions"] = render_instructions(repo, root, base, settings or {}, instr_dir)
    agents, all_names = select_agents(repo, packages)
    available = list_backends(repo)
    selected = backends or available
    for b in selected:
        if b not in available:
            die(f"backend '{b}' not found (available: {', '.join(available)})")
    configs = {
        b: build_backend(repo, root, b, agents, base, permissions, all_names, prompt_dir, settings) for b in selected
    }
    # backend tokens filled from the user's settings (e.g. the LM Studio server URL)
    url = (settings or {}).get("lmstudio_url")
    for b, config in configs.items():
        if contains_token(config, "{LMSTUDIO_URL}"):
            if not url:
                die(f"backend '{b}' needs the LM Studio URL: run configure-directories or pass --lmstudio-url")
            configs[b] = substitute(config, url, "{LMSTUDIO_URL}")
    return configs


if __name__ == "__main__":
    sys.exit("ERROR: library module; run codebase/opencode-kit.py")
