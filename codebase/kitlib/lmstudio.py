#!/usr/bin/env python3
"""LM Studio model sets for the 'local' backend (library module of opencode-kit).

A model set says which LM Studio models opencode declares and which model runs each tier.
It is stored in the user settings (key 'lmstudio_models'), never in the repository:

    {"format": 2,
     "models": {"<LM Studio model ID>": {"context": 65536, "output": 16384, "tools": true,
                                         "reasoning": true, "name": "...",
                                         "temperature": 0.6, "top_p": 0.95}, ...},
     "tiers":  {"light": "<ID>", "main": "<ID>", "writing": "<ID>",
                "codegen": "<ID>", "careful": "<ID>"}}

Only 'context' is required per model. Models that run no tier are declared too, so the
user can switch to them by hand in opencode. A model's temperature/top_p (both or none)
override the tier sampling of configs/backends/local/backend.json wherever it runs.

Ways to get a set: pick from the models the server lists (configure-lmstudio, asks or
takes --heavy/--fast/--tier/--extra), or write one by hand and import it with
--models-file (works offline). configs/backends/local/lmstudio-models.example.json is a
real example; it is used, with a warning, until the user has chosen a set.

Run codebase/opencode-kit.py instead of this file.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .common import CONFIGS, die, info, load_json, warn

# Design decision: LM Studio's own REST API (/api/v0/models) reports type, tool support,
# maximum and loaded context; the OpenAI-compatible /v1/models only lists IDs, so it is
# the fallback for older LM Studio versions.
REASONING_HINTS = ("qwen3", "qwq", "deepseek-r1", "gpt-oss", "magistral", "reasoning", "nemotron")
DEFAULT_CONTEXT = 65536
MIN_CONTEXT = 4096  # hard floor: below this nothing useful fits
# Assumption: agent system prompts plus tool definitions take about 20K tokens, so below
# this length sessions compact constantly or overflow; allowed, but warned about
WARN_CONTEXT = 32768
MIN_FAST_BILLIONS = 4
FORMAT = 2
MODEL_KEYS = {"name", "context", "output", "tools", "reasoning", "temperature", "top_p"}
TOP_KEYS = {"format", "description", "models", "tiers"}
LOCAL_BACKEND = CONFIGS / "backends" / "local" / "backend.json"
API_KEY_ENV = "LMSTUDIO_API_KEY"


class ServerError(Exception):
    """The LM Studio server did not deliver a model list; the message says why."""


class ModelSetError(ValueError):
    """A model set is invalid; the message names the file/record, expected and observed value."""


# --- server ---------------------------------------------------------------------------


def normalise_url(url, where="lmstudio_url"):
    """'host:1234', 'http://host:1234' or '.../v1/' -> 'http://host:1234/v1'; stops on junk."""
    if url is not None and not isinstance(url, str):
        die(f"{where}: expected a URL (text), got {type(url).__name__} {url!r}; expected e.g. http://localhost:1234/v1")
    url = (url or "").strip()
    if not url:
        return None
    if "://" not in url:
        url = f"http://{url}"
    try:
        parts = urllib.parse.urlsplit(url)
        parts.port  # noqa: B018 (raises ValueError on a bad port)
    except ValueError as err:
        die(f"{where}: '{url}' is not a valid URL ({err}); expected e.g. http://localhost:1234/v1")
    if parts.scheme not in ("http", "https") or not parts.hostname:
        die(f"{where}: '{url}' is not an http(s) URL; expected e.g. http://localhost:1234/v1")
    if parts.query or parts.fragment:
        die(f"{where}: '{url}' has a query or fragment; expected e.g. http://localhost:1234/v1")
    path = parts.path.rstrip("/")
    # opencode's OpenAI-compatible provider needs the /v1 base; LM Studio serves it there
    if not path.endswith("/v1"):
        path = f"{path}/v1"
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def api_key():
    """LM Studio token from $LMSTUDIO_API_KEY (only needed with 'Require authentication')."""
    return os.environ.get(API_KEY_ENV) or None


def _get_json(url, key=None):
    """GET a JSON document; raises ServerError with the reason."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        if err.code in (401, 403):
            raise ServerError(
                f"{url}: HTTP {err.code}, the server requires a token; "
                f"export {API_KEY_ENV}=<token from LM Studio, Developer -> Server Settings>"
            ) from None
        raise ServerError(f"{url}: HTTP {err.code}") from None
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as err:
        reason = getattr(err, "reason", err)
        raise ServerError(f"{url}: not reachable ({reason})") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ServerError(f"{url}: answer is not JSON (is this an LM Studio server?)") from None


def size_billions(model_id):
    """Parameter count from the model ID ('qwen/qwen3.8-27b' -> 27.0), or None."""
    # Assumption: LM Studio IDs carry the size as '<number>b' (e.g. 9b, 26b-a4b -> 26)
    match = re.search(r"(\d+(?:\.\d+)?)b(?![a-z])", model_id.lower())
    return float(match.group(1)) if match else None


def _positive_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def list_models(url, key=None):
    """Chat-capable models on the server: list of dicts, largest first; raises ServerError."""
    base = normalise_url(url)
    root = base[: -len("/v1")]
    try:
        rest = _get_json(f"{root}/api/v0/models", key)
    except ServerError as err:
        if "token" in str(err) or "not reachable" in str(err):
            raise
        rest = None
    models = []
    if isinstance(rest, dict) and isinstance(rest.get("data"), list):
        for m in rest["data"]:
            # embedding models can't chat; they are never offered for agents
            if not isinstance(m, dict) or not isinstance(m.get("id"), str) or m.get("type") not in ("llm", "vlm"):
                continue
            models.append({
                "id": m["id"],
                "tools": "tool_use" in (m.get("capabilities") or []),
                "max_context": _positive_int(m.get("max_context_length")),
                "loaded_context": _positive_int(m.get("loaded_context_length")),
                "state": str(m.get("state") or "?"),
                "quantization": str(m.get("quantization") or ""),
            })
    else:
        openai = _get_json(f"{base}/models", key)
        if not isinstance(openai, dict) or not isinstance(openai.get("data"), list):
            raise ServerError(f"{base}/models: no 'data' list in the answer (is this an LM Studio server?)")
        warn(f"{root}/api/v0/models unavailable (older LM Studio?): tool support and context length unknown")
        for m in openai["data"]:
            if not isinstance(m, dict) or not isinstance(m.get("id"), str) or "embed" in m["id"].lower():
                continue
            models.append({"id": m["id"], "tools": None, "max_context": None, "loaded_context": None,
                           "state": "?", "quantization": ""})
    for m in models:
        m["size"] = size_billions(m["id"])
    models.sort(key=lambda m: (-(m["size"] or 0), m["id"]))
    return models


def suggest(models):
    """(heavy, fast) suggestion.

    heavy: the largest tool-capable model, skipping extreme quantisations (Q1/Q2, IQ1/IQ2:
    too lossy for agent work) unless nothing else is left; ties prefer a loaded model.
    fast: a loaded tool-capable model other than heavy if there is one, else the one whose
    size is nearest 9B (fast but still reliable at tool calls), at least 4B.
    """
    usable = [m for m in models if m["tools"] is not False] or models
    decent = [m for m in usable if not re.match(r"i?q[12](_|$)", m["quantization"].lower())] or usable
    heavy = sorted(decent, key=lambda m: (-(m["size"] or 0), m["state"] != "loaded", m["id"]))[0]
    loaded = [m for m in decent if m["state"] == "loaded" and m["id"] != heavy["id"]]
    smaller = [m for m in decent if MIN_FAST_BILLIONS <= (m["size"] or 0) < (heavy["size"] or 0)]
    if loaded:
        fast = loaded[0]
    elif smaller:
        fast = min(smaller, key=lambda m: (abs(m["size"] - 9), m["id"]))
    else:
        fast = heavy
    return heavy, fast


# --- model sets -------------------------------------------------------------------------


def local_backend():
    """configs/backends/local/backend.json (tiers, tier_roles, tier_help)."""
    return load_json(LOCAL_BACKEND)


def default_output(context):
    # Design decision: a quarter of the context, max 16384, so long answers fit without
    # crowding out the conversation; rejected: one fixed value for all context sizes.
    return min(16384, context // 4)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _migrate_v1(cfg, roles, where):
    """{'heavy': {...}, 'fast': {...}} (opencode-kit before 1.0) -> format 2."""
    if set(cfg) - {"heavy", "fast"} or not roles:
        raise ModelSetError(f"{where}: unknown model set layout (keys {sorted(cfg)}); expected format {FORMAT} "
            f"with 'models' and 'tiers'; fix: codebase/opencode-kit.py configure-lmstudio")
    models, by_role = {}, {}
    for role in ("heavy", "fast"):
        m = cfg.get(role)
        if not isinstance(m, dict) or not isinstance(m.get("id"), str):
            raise ModelSetError(f"{where}: '{role}' has no model 'id'; fix: codebase/opencode-kit.py configure-lmstudio")
        models[m["id"]] = {k: v for k, v in m.items() if k in MODEL_KEYS}
        by_role[role] = m["id"]
    return {"format": FORMAT, "models": models, "tiers": {t: by_role[r] for t, r in roles.items()}}


def validate(cfg, tiers, where, roles=None):
    """Checked, completed copy of a model set; stops with the first problem.

    tiers: tier names the set must fill (all of them, no others); roles: tier -> heavy/fast
    (only needed to migrate the old two-model layout).
    """
    if not isinstance(cfg, dict):
        raise ModelSetError(f"{where}: expected a JSON object with 'models' and 'tiers', got {type(cfg).__name__}")
    if "models" not in cfg and ("heavy" in cfg or "fast" in cfg):
        cfg = _migrate_v1(cfg, roles, where)
    if cfg.get("format", FORMAT) != FORMAT:
        raise ModelSetError(f"{where}: format {cfg.get('format')!r} is not supported; expected {FORMAT}")
    unknown = sorted(set(cfg) - TOP_KEYS)
    if unknown:
        raise ModelSetError(f"{where}: unknown keys {unknown}; allowed: {sorted(TOP_KEYS)}")
    models = cfg.get("models")
    if not isinstance(models, dict) or not models:
        raise ModelSetError(f"{where}: 'models' must be a non-empty object of '<LM Studio model ID>': {{...}}")
    out_models = {}
    for mid, m in models.items():
        here = f"{where}: model '{mid}'"
        if not mid or mid != mid.strip() or any(c.isspace() for c in mid):
            raise ModelSetError(f"{here}: the ID must be the LM Studio model ID, without spaces")
        if "#" in mid:
            # opencode reads 'provider/model#variant': a '#' in the ID would cut it short
            raise ModelSetError(f"{here}: the ID must not contain '#' (opencode's variant separator)")
        if not isinstance(m, dict):
            raise ModelSetError(f"{here}: expected an object with at least 'context', got {type(m).__name__}")
        bad = sorted(set(m) - MODEL_KEYS)
        if bad:
            raise ModelSetError(f"{here}: unknown keys {bad}; allowed: {sorted(MODEL_KEYS)}")
        context = m.get("context")
        if not isinstance(context, int) or isinstance(context, bool) or context < MIN_CONTEXT:
            raise ModelSetError(f"{here}: 'context' must be an integer >= {MIN_CONTEXT} (the length the model is "
                f"loaded with in LM Studio), got {context!r}")
        output = m.get("output", default_output(context))
        if not isinstance(output, int) or isinstance(output, bool) or not 0 < output < context:
            raise ModelSetError(f"{here}: 'output' must be an integer between 1 and context-1 ({context - 1}), got {output!r}")
        tools = m.get("tools", True)
        if not (tools is None or isinstance(tools, bool)):  # 1/0 compare equal to true/false
            raise ModelSetError(f"{here}: 'tools' must be true, false or null, got {tools!r}")
        reasoning = m.get("reasoning", any(h in mid.lower() for h in REASONING_HINTS))
        if not isinstance(reasoning, bool):
            raise ModelSetError(f"{here}: 'reasoning' must be true or false, got {reasoning!r}")
        name = m.get("name", f"{mid} (LM Studio)")
        if not isinstance(name, str) or not name.strip():
            raise ModelSetError(f"{here}: 'name' must be a non-empty string, got {name!r}")
        rec = {"name": name, "context": context, "output": output, "tools": tools, "reasoning": reasoning}
        sampling = [k for k in ("temperature", "top_p") if k in m]
        if sampling and len(sampling) != 2:
            raise ModelSetError(f"{here}: set 'temperature' and 'top_p' together (or neither), got only {sampling}")
        if sampling:
            if not _is_number(m["temperature"]) or not 0 <= m["temperature"] <= 2:
                raise ModelSetError(f"{here}: 'temperature' must be a number from 0 to 2, got {m['temperature']!r}")
            if not _is_number(m["top_p"]) or not 0 < m["top_p"] <= 1:
                raise ModelSetError(f"{here}: 'top_p' must be a number above 0 and at most 1, got {m['top_p']!r}")
            rec["temperature"], rec["top_p"] = m["temperature"], m["top_p"]
        out_models[mid] = rec
    given = cfg.get("tiers")
    if not isinstance(given, dict):
        raise ModelSetError(f"{where}: 'tiers' must be an object '<tier>': '<model ID>' for {sorted(tiers)}")
    missing = sorted(set(tiers) - set(given))
    extra = sorted(set(given) - set(tiers))
    if missing or extra:
        raise ModelSetError(f"{where}: 'tiers' must name exactly {sorted(tiers)}; missing {missing}, unknown {extra}")
    for tier, mid in given.items():
        if not isinstance(mid, str):
            raise ModelSetError(f"{where}: tier '{tier}' must name a model ID (text), got {mid!r}")
        if mid not in out_models:
            raise ModelSetError(f"{where}: tier '{tier}' uses '{mid}', which is not declared in 'models' "
                f"(declared: {', '.join(out_models)})")
    result = {"format": FORMAT}
    if isinstance(cfg.get("description"), str):
        result["description"] = cfg["description"]
    result["models"] = out_models
    result["tiers"] = {t: given[t] for t in tiers}
    return result


def check_against_server(cfg, server_models, url):
    """Stop when a model is not on the server or exceeds its maximum context; warn on no tools."""
    by_id = {m["id"]: m for m in server_models}
    for mid, m in cfg["models"].items():
        found = by_id.get(mid)
        if not found:
            die(f"model '{mid}' is not on the LM Studio server {url} (available: {', '.join(by_id) or 'none'}); "
                "download it in LM Studio or remove it from the model set")
        limit = found.get("max_context")
        if limit and m["context"] > limit:
            die(f"model '{mid}': context {m['context']} exceeds its maximum {limit} on {url}; lower 'context'")
        if found.get("tools") is False and mid in cfg["tiers"].values():
            warn(f"{mid} does not report tool use; agents need tool calls and may fail with it")


def load_models_file(path, backend=None):
    """Read and validate a hand-written model set file."""
    path = Path(path).expanduser()
    if not path.is_file():
        die(f"model set file '{path}' not found; start from configs/backends/local/lmstudio-models.example.json")
    backend = backend or local_backend()
    try:
        cfg = validate(load_json(path), backend["tiers"], str(path), backend.get("tier_roles"))
    except ModelSetError as err:
        die(str(err))
    for mid, m in cfg["models"].items():
        warn_small_context(mid, m["context"], str(path))
    return cfg


def warn_small_context(mid, context, where="model set"):
    """WARNING when a context length works but is too small for the agents' prompts."""
    if context < WARN_CONTEXT:
        warn(f"{where}: model '{mid}' has context {context}, below {WARN_CONTEXT}: the agents' system prompts "
             "and tools take about 20K tokens, so sessions compact constantly or overflow. If the hardware "
             f"allows, raise the model's 'Context Length' load setting in LM Studio (My Models -> gear -> Load) "
             f"to at least {WARN_CONTEXT}, and set the same value here")


def _server_default_context(m):
    """Loaded context if the model is loaded, else min(max context, DEFAULT_CONTEXT)."""
    if m.get("loaded_context"):
        return m["loaded_context"]
    return min(m.get("max_context") or DEFAULT_CONTEXT, DEFAULT_CONTEXT)


def _record(server_model, context, previous=None):
    """Model entry for the set: keeps hand-set fields of the previous entry (name, sampling, output)."""
    rec = {k: v for k, v in (previous or {}).items() if k in MODEL_KEYS}
    if rec.get("context") != context:
        rec.pop("output", None)  # derived from the context unless the user set it for this length
    rec["context"] = int(context)
    if server_model.get("tools") is not None:
        rec["tools"] = server_model["tools"]
    return rec


# --- interactive selection --------------------------------------------------------------


def _ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        die("input aborted; nothing was changed")


def print_table(models):
    """Numbered model table for the questions."""
    print("\nModels on the LM Studio server (chat models only):", file=sys.stderr)
    print(f"  {'#':>2}  {'model':40} {'size':>6} {'tools':>5} {'max ctx':>8} {'loaded':>8} {'state'}", file=sys.stderr)
    for i, m in enumerate(models, 1):
        tools = {True: "yes", False: "NO", None: "?"}[m["tools"]]
        size = f"{m['size']:g}B" if m["size"] else "?"
        print(
            f"  {i:>2}  {m['id']:40} {size:>6} {tools:>5} {str(m['max_context'] or '?'):>8} "
            f"{str(m['loaded_context'] or '-'):>8} {m['state']}",
            file=sys.stderr,
        )


def _pick_one(models, by_id, label, default):
    """Ask for one model (number or ID); Enter keeps the default; asks again on a typo."""
    while True:
        reply = _ask(f"{label} [{default['id']}]: ")
        if not reply:
            return default
        if reply.isdigit() and 1 <= int(reply) <= len(models):
            return models[int(reply) - 1]
        if reply in by_id:
            return by_id[reply]
        print(f"  '{reply}' is neither a number from the table nor a model ID; try again", file=sys.stderr)


def _pick_many(models, by_id, label, default_ids):
    """Ask for a comma-separated list of models; '-' = none; Enter keeps the default."""
    while True:
        reply = _ask(f"{label} [{', '.join(default_ids) or 'none'}]: ")
        if not reply:
            return list(default_ids)
        if reply == "-":
            return []
        picked, bad = [], []
        for item in (p.strip() for p in reply.split(",") if p.strip()):
            if item.isdigit() and 1 <= int(item) <= len(models):
                picked.append(models[int(item) - 1]["id"])
            elif item in by_id:
                picked.append(item)
            else:
                bad.append(item)
        if not bad:
            return picked
        print(f"  not in the table: {', '.join(bad)}; try again", file=sys.stderr)


def check_context(value, where):
    """Stop unless a context length is a whole number of at least MIN_CONTEXT."""
    if not isinstance(value, int) or isinstance(value, bool) or value < MIN_CONTEXT:
        die(f"{where}: context {value!r} is too small; expected a whole number of at least {MIN_CONTEXT} "
            "(the length the model is loaded with in LM Studio)")
    return value


def _ask_context(m, default):
    limit = m.get("max_context")
    while True:
        reply = _ask(f"Context length {m['id']} is loaded with in LM Studio (must match its load setting) [{default}]: ")
        if not reply:
            return default
        if reply.isdigit() and int(reply) >= MIN_CONTEXT and not (limit and int(reply) > limit):
            return int(reply)
        print(f"  expected a whole number from {MIN_CONTEXT} to {limit or 'the model maximum'}; try again",
              file=sys.stderr)


def choose(url, key=None, interactive=True, current=None, heavy=None, fast=None, tier_models=None,
           extras=None, contexts=None, backend=None):
    """Build a model set from the models on the server; returns it, or None if the server is down.

    current: the saved set (its choices are the defaults where the models still exist);
    heavy/fast: model IDs for the two-model shortcut (tier_roles); tier_models: {tier: ID}
    for single tiers (wins over heavy/fast); extras: further IDs to declare; contexts:
    {ID: length} or {'*': length} for all models. With any of these given, nothing is asked.
    """
    backend = backend or local_backend()
    tiers, roles, helps = list(backend["tiers"]), backend.get("tier_roles") or {}, backend.get("tier_help") or {}
    try:
        models = list_models(url, key)
    except ServerError as err:
        warn(f"LM Studio: {err}")
        return None
    if not models:
        die(f"LM Studio at {url} lists no chat models; download or load one in LM Studio first")
    by_id = {m["id"]: m for m in models}
    tier_models = dict(tier_models or {})
    contexts = dict(contexts or {})
    for tier in tier_models:
        if tier not in tiers:
            die(f"--tier {tier}=...: unknown tier; tiers are {', '.join(tiers)}")
    for mid, ctx in contexts.items():
        check_context(ctx, f"--context {'' if mid == '*' else mid + '='}{ctx}")
    named = [heavy, fast, *tier_models.values(), *(extras or []), *(k for k in contexts if k != "*")]
    for mid in named:
        if mid and mid not in by_id:
            die(f"model '{mid}' is not on the LM Studio server {url} (available: {', '.join(by_id)})")
    previous = {}
    if current:
        try:
            previous = validate(current, tiers, "saved lmstudio_models", roles)
        except ModelSetError as err:
            warn(f"{err}; the saved set is replaced by the new choice")
    prev_models = previous.get("models", {})
    # defaults: the saved choice where the model is still on the server, else the suggestion
    s_heavy, s_fast = suggest(models)
    assign = {}
    for tier in tiers:
        prev = previous.get("tiers", {}).get(tier)
        assign[tier] = prev if prev in by_id else (s_heavy if roles.get(tier) == "heavy" else s_fast)["id"]
    prev_extras = [m for m in prev_models if m in by_id and m not in previous.get("tiers", {}).values()]
    flags_given = bool(heavy or fast or tier_models or extras or contexts)
    if interactive and not flags_given:
        print_table(models)
        print("\nopencode agents run on five tiers:", file=sys.stderr)
        for tier in tiers:
            print(f"  {tier:8} {helps.get(tier, '')}", file=sys.stderr)
        distinct = len(set(assign.values()))
        print("\n  [1] two models: 'heavy' for codegen + careful, 'fast' for the rest (simplest)\n"
              "  [2] one model per tier", file=sys.stderr)
        mode = _ask(f"How should the tiers be filled? [{2 if distinct > 2 else 1}]: ") or str(2 if distinct > 2 else 1)
        while mode not in ("1", "2"):
            mode = _ask("Please answer 1 or 2: ")
        if mode == "1":
            def role_default(role):
                return by_id[next((assign[t] for t in tiers if roles.get(t) == role), s_heavy["id"])]

            h = _pick_one(models, by_id, "Heavy model (number or ID)", role_default("heavy"))
            f = _pick_one(models, by_id, "Fast model (number or ID)", role_default("fast"))
            assign = {t: (h if roles.get(t) == "heavy" else f)["id"] for t in tiers}
        else:
            for tier in tiers:
                assign[tier] = _pick_one(models, by_id, f"{tier} ({helps.get(tier, '')})", by_id[assign[tier]])["id"]
        used = set(assign.values())
        extra_ids = _pick_many(
            models, by_id,
            "Further models to declare for switching by hand in opencode (numbers or IDs, comma-separated, '-' = none)",
            [m for m in prev_extras if m not in used],
        )
        chosen_ids = list(dict.fromkeys([*assign.values(), *extra_ids]))
        for mid in chosen_ids:
            default = prev_models.get(mid, {}).get("context") or _server_default_context(by_id[mid])
            limit = by_id[mid].get("max_context")
            if limit and default > limit:
                info(f"{mid}: the saved context {default} exceeds the server's maximum {limit}; offering {limit}")
                default = limit
            contexts[mid] = _ask_context(by_id[mid], default)
    else:
        for tier in tiers:
            if roles.get(tier) == "heavy" and heavy:
                assign[tier] = heavy
            elif roles.get(tier) == "fast" and fast:
                assign[tier] = fast
        assign.update(tier_models)
        extra_ids = list(extras) if extras is not None else prev_extras
        chosen_ids = list(dict.fromkeys([*assign.values(), *extra_ids]))
        outside = [mid for mid in contexts if mid != "*" and mid not in chosen_ids]
        if outside:
            die(f"--context {outside[0]}=...: model '{outside[0]}' is not part of the chosen set "
                f"({', '.join(chosen_ids)}); add it with --extra {outside[0]} or drop that --context")
    set_models = {}
    for mid in chosen_ids:
        ctx = contexts.get(mid) or contexts.get("*") or prev_models.get(mid, {}).get("context")
        if not ctx:
            ctx = _server_default_context(by_id[mid])  # loaded length (warned below if small)
        set_models[mid] = _record(by_id[mid], ctx, prev_models.get(mid))
        warn_small_context(mid, set_models[mid]["context"], "chosen model set")
    try:
        cfg = validate({"format": FORMAT, "models": set_models, "tiers": assign}, tiers, "chosen model set")
    except ModelSetError as err:
        die(str(err))
    check_against_server(cfg, models, url)
    for line in describe(cfg):
        info(line)
    info("load each model in LM Studio with exactly these context lengths (My Models -> gear -> Load), "
         "or compaction breaks")
    return cfg


# --- build ------------------------------------------------------------------------------


def describe(cfg):
    """Human-readable lines for a (validated) model set."""
    lines = []
    for mid, m in cfg["models"].items():
        tiers = [t for t, used in cfg["tiers"].items() if used == mid]
        role = ", ".join(tiers) if tiers else "by hand only"
        lines.append(f"lmstudio {mid}: {role} (context {m['context']}, output {m['output']})")
    return lines


def _variant(temperature, top_p):
    return {"id": f"t{temperature}-p{top_p}", "body": {"temperature": temperature, "top_p": top_p}}


def apply_to_backend(backend, cfg, where="lmstudio_models"):
    """Fill the local backend's models and tier models from a model set (in place).

    Backends without 'tier_roles' are returned unchanged. Without a set, the example set
    named by 'models_example' is used with a warning.
    """
    if "tier_roles" not in backend:
        return backend
    if not cfg:
        example = LOCAL_BACKEND.parent / backend.get("models_example", "lmstudio-models.example.json")
        warn(f"no LM Studio model set chosen: using the example {example.name}; "
             "choose yours with: codebase/opencode-kit.py configure-lmstudio")
        cfg, where = load_json(example), str(example)
    try:
        cfg = validate(cfg, backend["tiers"], where, backend.get("tier_roles"))
    except ModelSetError as err:
        die(f"{err}; fix: codebase/opencode-kit.py configure-lmstudio")
    if len(backend["providers"]) != 1:
        die(f"{LOCAL_BACKEND}: expected exactly one provider, found {sorted(backend['providers'])}")
    ((pid, provider),) = backend["providers"].items()
    provider["models"] = {}
    for mid, m in cfg["models"].items():
        mdef = {
            "name": m["name"],
            "capabilities": {"tools": m["tools"] is not False, "temperature": True,
                             "reasoning": {"supported": m["reasoning"]}},
            "limit": {"context": m["context"], "output": m["output"]},
        }
        if "temperature" in m:
            # selectable by hand as <model>#<variant>; tiers running it get the same sampling
            mdef["variants"] = [_variant(m["temperature"], m["top_p"])]
        provider["models"][mid] = mdef
    for tier, mid in cfg["tiers"].items():
        tdef = backend["tiers"][tier]
        tdef["model"] = f"{pid}/{mid}"
        if "temperature" in cfg["models"][mid]:
            tdef["temperature"] = cfg["models"][mid]["temperature"]
            tdef["top_p"] = cfg["models"][mid]["top_p"]
    return backend


def export(cfg, path):
    """Write a model set as an editable file (for --models-file)."""
    path = Path(path).expanduser()
    if path.exists():
        die(f"{path} exists; choose a new file name (nothing was overwritten)")
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    info(f"wrote the model set to {path}; edit it, then: codebase/opencode-kit.py configure-lmstudio --models-file {path}")


if __name__ == "__main__":
    sys.exit("ERROR: library module; run codebase/opencode-kit.py")
