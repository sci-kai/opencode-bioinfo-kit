# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A general **opencode 2 agent configuration** plus deployment toolkit (maintained by Kai Horny). It holds agent
definitions and prompts, two model backends (KI Connect NRW, local LM Studio), skills, and
the CUBI knowledge base. opencode 1.x is not supported. The README links all docs, and
`docs/deploy.md` is the install guide.

## Layout and data flow

```
configs/shared/{base,permissions}.json      identical on every backend (opencode 2 schema)
configs/agents/<name>/{agent.json,prompt.md} one folder per agent, backend-neutral "tier"
configs/backends/<b>/backend.json           providers, tier -> model + sampling, agent_tiers
configs/instructions/*.md                   global agent rules + coding/data/testing standards (loaded by every agent)
cubi-rules/cubi-rules-condensed.md          CUBI digest (loaded by every agent), AI-derived from
cubi-rules/knowledge-base.wiki/             … the CUBI KB (git submodule); kb-source.json = KB commit of the digest
skills/<group>/<id>/SKILL.md                own skills (nf-core, cubi-dev, refdata); skills/bionemo-agent-toolkit/ = submodule
        └─ codebase/opencode-kit.py deploy-configs <b> ─> ~/.config/opencode/{opencode.json, cubi-kb/, skills/<group>/<id>/}
        └─ codebase/opencode-kit.py preview-configs      ─> generated/ (gitignored review copy)
```

- Generated files are **not** committed: no `opencode.json`, no KB concatenations.
  `deploy-configs` produces them, and `preview-configs` writes review copies.
- `codebase/opencode-kit.py` is the only entry point (`setup-opencode`, `deploy-configs`,
  `test-deployment`, `preview-configs`, `list-skills`, `install-skills`, `*-cubi-digest*`,
  `update-git-submodules`). Its library is `codebase/kitlib/`: `common.py` (paths, opencode helpers),
  `build.py` (config generation), `skills.py`, `kb.py`, `install.py`, `deploy.py`
  (deploy + test). Python stdlib only; executable with a `#!/usr/bin/env python3`
  shebang; messages go to stderr as `ERROR:`/`WARNING:`/`INFO:`.
- **No machine-specific paths in the repo.** Each user's folders (conda base, envs, scratch,
  mount point, temp, extra, LM Studio URL) live in `~/.config/opencode/opencode-kit-settings.json`
  (`kitlib/settings.py`, `configure-directories`). They expand the `<user-directories>` rule in
  `permissions.json`; `general-work-rules.md` has `{{ENVS_DIR}}`-style placeholders and
  `if-setting`/`if-no-setting` blocks and is rendered to `~/.config/opencode/instructions/`.
  Prompts and skills only use the tokens `<ENVS_DIR>`, `<CONDA_BASE>`, `<SCRATCH_DIR>`,
  `<TMP_DIR>`, never literal paths. `/`, the home folder, system and credential folders are refused.
- **LM Studio**: `kitlib/lmstudio.py`. A *model set* (format 2: `models` = ID -> context,
  output, tools, reasoning, optional name and temperature+top_p; `tiers` = tier -> ID) is saved
  as `lmstudio_models` in the user settings. `configure-lmstudio` (automatic on the first
  `local` deploy) builds it from `/api/v0/models` (fallback `/v1/models`): heavy/fast via
  `tier_roles`, or one model per tier, plus extra models; or imports a file (`--models-file`,
  works offline). `configs/backends/local/backend.json` holds no models, only tier sampling;
  until the user chose, `lmstudio-models.example.json` (a real setup, also the test fixture)
  is used with a warning. The old `{heavy, fast}` layout is migrated on read.
- **Tests**: `python3 -m unittest discover -s codebase/tests -t codebase` (stdlib only, no
  opencode needed; never touch the real `~/.config/opencode`).
- Agent prompts are emitted as `"system": "{file:<abs>/configs/agents/<x>/prompt.md}"`.
  The braces matter. `{REPO}` in `configs/shared/*.json` becomes the checkout path, `{OC_CONFIG}` /
  `{OC_DATA}` opencode's config/data folders (`$XDG_CONFIG_HOME/opencode`, `$XDG_DATA_HOME/opencode`
  or the `~/.config`, `~/.local/share` fallbacks; `common.config_dir`/`data_dir`).

## opencode 2 specifics (verified on 2.2.6)

- No per-agent sampling: each tier's `temperature`/`top_p` becomes a model variant
  (`model#t0.6-p0.95`).
- `permissions` is an ordered list where the last match wins. External directories are
  *allowed* by default, so `external_directory * deny` must be the first rule (enforced).
  A `shell` rule `x *` also covers bare `x`. `~` is expanded in file and directory rules,
  but not in `shell` rules.
- Unknown fields are dropped silently, so `build.py` rejects opencode 1 keys.
- Skills: IDs come from folder names, and grouping folders are allowed
  (`skills/nf-core/<id>`). `GET /api/skill` in a one-shot `--standalone` call shows only
  built-ins, so `test-deployment` checks skills by capturing a real `opencode run` request against a
  local fake endpoint in a throwaway HOME.
- One-shot commands need `--standalone`. Start-up sometimes fails with "Location plugins
  did not finish activating", so retry (`common.run_opencode`/`opencode_json` do).
- For experiments use an isolated `HOME`/`XDG_*`: opencode 2 writes the shared
  `~/.local/share/opencode/opencode.db` (which also holds API keys).

## Commands

```bash
codebase/opencode-kit.py preview-configs              # validate everything, write generated/
codebase/opencode-kit.py deploy-configs kiconnect   # install to ~/.config/opencode + test
codebase/opencode-kit.py test-deployment [--live]
codebase/opencode-kit.py list-skills
codebase/opencode-kit.py check-cubi-digest --fetch
opencode debug agents --standalone          # resolved agents (model, variant, system text)
```

## Editing rules

- **Agent behaviour**: `configs/agents/<name>/prompt.md`. **Routing**: the table in
  `configs/agents/build/routing.json` is the only routing table (rendered into the build prompt
  at `<!-- opencode-kit:routing -->` with only the installed agents; prompt parts for one package go
  between `<!-- opencode-kit:if-package P -->` and `<!-- opencode-kit:end -->`). Adding an agent:
  `docs/adding-agents.md`.
- **Global rules**: `configs/instructions/general-work-rules.md` and the CUBI digest.
  Keep both short, since local models have small contexts. Don't duplicate between
  them or into prompts. Prompts get one-line pointers instead.
- These prompts should reflect the CUBI rules and the strict-validation rules
  (result-affecting changes ask first, strict checks, `ERROR:`
  messages naming file/record/expected/observed/fix, failure-path tests). Re-audit when
  those change.
- **CUBI digest**: never edit it from memory. Follow `docs/updating-cubi-rules.md`
  (`update-cubi-digest` generates the prompt with the KB diff), then `mark-cubi-digest-synced`.
- **Submodules** (`cubi-rules/knowledge-base.wiki`, `skills/bionemo-agent-toolkit`):
  external; never edit inside them. Move them with `opencode-kit.py update-git-submodules` and commit
  the new pin.
- **KI Connect models**: the deployments page needs a login. Use
  `GET https://chat.kiconnect.nrw/api/v1/models` with the key, and get context limits
  from the vLLM `max_model_len` error (`docs/kiconnect-models.md`).
- **LM Studio**: a model's `context` in the model set must equal the context length LM Studio
  loads it with (`docs/lmstudio-model-settings.md`). Keep `lmstudio-models.example.json` valid
  against `codebase/tests/data/` (the tests check it).
- Style: JSON with 2-space indent and a trailing newline. Markdown with Unix line endings.
  CUBI file names. Docs go in `docs/` and are linked from the README; config folders
  hold configs only.
