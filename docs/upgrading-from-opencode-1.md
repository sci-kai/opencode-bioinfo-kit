# Upgrading from opencode 1

This configuration supports **opencode 2 only** (checked with 2.2.6 on 2026-11-08).
opencode 1.x uses a different config schema. `codebase/opencode-kit.py` refuses
to run with it and points here.

## The upgrade is one-way

opencode 1 and 2 share `~/.config/opencode` and `~/.local/share/opencode`. On its first
start, opencode 2 migrates the session database (`opencode.db`) and imports the 1.x
credentials from `auth.json`. After that, going back to 1.x is not supported.

```bash
# optional safety copy of sessions and credentials (can be large: check df -h first)
cp -a ~/.local/share/opencode ~/.local/share/opencode_backup_v1

cd ~/Projects/opencode-config
codebase/opencode-kit.py setup-opencode kiconnect --upgrade-from-v1
```

`--upgrade-from-v1` runs the official opencode 2 installer (`~/.opencode/bin/opencode`
is replaced). It then stores the API key in opencode 2's credential store and deploys
the v2 config. The previous `opencode.json` goes to `~/.config/opencode/backups/`.
Tested on 2026-11-08 by upgrading a real 1.19.5 install.

Alternative without the script: upgrade opencode itself (`opencode upgrade --major` on an
opencode 1.x install; opencode 2 has no such flag), then
`codebase/opencode-kit.py setup-opencode kiconnect`.

## What changed between the schemas

The sources in this repo (`configs/shared/`, `configs/backends/`, `configs/agents/`) are written in the v2
schema. This table helps with reading old configs or porting other ones:

| opencode 1 | opencode 2 (as used here) |
|---|---|
| `agent.<n>.prompt: "{file:…}"` | `agents.<n>.system: "{file:…}"` |
| agent `temperature`, `top_p` | model **variant** `{id: "t0.6-p0.95", body: {temperature, top_p}}`, selected with `model: "prov/model#t0.6-p0.95"`. The generator makes one per backend tier |
| agent `env`, `tools`, `maxSteps` | dropped / `permissions` / `steps` |
| `small_model` | `agents.title.model` (the `title` agent's tier) |
| `permission` map | `permissions`: ordered list of `{action, resource, effect}`. The last matching rule wins |
| `bash` patterns | `shell` rules. No `~` expansion; `x *` also matches bare `x` |
| `external_directory` (asks by default) | `external_directory` (**allows** by default, so `* deny` must be the first rule; the generator enforces it) |
| `external_directory` file denies (`*/.env`, …) | `read` + `edit` deny rules |
| `doom_loop` | no equivalent |
| `provider` (`npm`, `options`) | `providers` (`package: @opencode/ai/providers/openai-compatible`, `settings`) |
| model `tool_call` / `temperature` / `reasoning` | `capabilities.tools` / `.temperature` / `.reasoning.supported` |
| model `options` | model `settings` |
| `compaction.reserved` / `prune` | `compaction.buffer` / no equivalent |
| `server` block | no equivalent: `opencode serve --hostname 0.0.0.0 --port 4096`, password via `OPENCODE_PASSWORD` |
| built-in agent `scout` | does not exist in v2 (built-ins: build, plan, general, explore, title, summary, compaction) |
| skills in `~/.opencode/skills` | `~/.config/opencode/skills` (also `~/.claude/skills`, `~/.agents/skills`, project `.opencode/skills`) |
| project `CLAUDE.md` read as instructions | only `AGENTS.md`: `ln -s CLAUDE.md AGENTS.md` |

## Credentials in opencode 2

- Stored in the table `credential` of `~/.local/share/opencode/opencode.db`, in plain
  text. The agents may not read it: `configs/shared/permissions.json` denies `opencode.db*`.
- Interactive: `opencode auth login ki_connect --method key`.
- Non-interactive (what `opencode-kit.py setup-opencode` does): `opencode auth import` with a JSON list
  on stdin, in the format of `opencode auth export`.
- Check: `opencode auth list --format json`.

## Known 2.2.6 quirks

- On slow machines (e.g. a Raspberry Pi), commands sometimes fail at start-up with `ServiceUnavailableError:
  Location plugins did not finish activating`. Setting `OPENCODE_DISABLE_MODELS_FETCH=1`
  makes it rarer, and a retry works. The scripts retry automatically.
- One-shot debug commands need `--standalone`, otherwise opencode starts a background
  service.
- opencode never rejects a bad config. It drops unknown fields with at most a log line
  (`--print-logs --log-level warn`, look for `configuration normalization diagnostic`).
  `opencode-kit.py` therefore rejects the v1 fields itself.
