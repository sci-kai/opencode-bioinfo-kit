# Changelog

All notable changes to this toolkit. Versions follow [semantic versioning](https://semver.org);
`-dev` marks releases from the `dev` branch.

## [1.0.0-dev] - 2026-11-11

First versioned release, as a general toolkit for any user (previously one person's setup).

### Added

- `codebase/opencode-kit.py`: one entry point to install opencode 2, deploy and test the
  configuration, preview configs, manage agent packages and skills, keep the CUBI rules digest in
  sync with the knowledge base, and move the submodules. `--version` prints the toolkit version.
- Two backends from one set of agents: KI Connect NRW and a local LM Studio server.
- **LM Studio model sets**: choose any models the server offers: a heavy and a fast model, or one
  model per tier, plus extra models to switch to by hand. Per-model context, output limit and
  optional sampling. Import a hand-written set with `configure-lmstudio --models-file` (works
  offline), view it with `--show`, export it with `--export`. A real example set ships in
  `configs/backends/local/lmstudio-models.example.json`. Settings saved with the old
  heavy/fast layout are converted automatically.
- Per-user folder settings (`configure-directories`): conda, envs, scratch, temp and extra
  folders are asked once and stored outside the repository.
- Agent packages (core, nf-core, dev, bioinformatics, refdata) with a routing table rendered from the
  installed agents; specialists for Nextflow/nf-core, Python, data formats, test design,
  reference data, debugging and paper writing.
- Skills: nf-core and CUBI development skills, plus the BioNeMo agent toolkit (submodule).
- Optional `refdata` package: the `refdata` agent (renamed from `reference-data`) and the skill
  group `skills/refdata/` (8 skills: SEQC2/GIAB test data, truth-set benchmarking, offline
  transfer). The skill IDs now carry the `refdata-` prefix (`seqc2-*` -> `refdata-seqc2-*`,
  `benchmark-*` -> `refdata-benchmark-*`). It needs seqc2-toolkit, an external tool that is
  not included and must be installed separately.
- Test suite: `python3 -m unittest discover -s codebase/tests -t codebase` (stdlib only, no
  opencode needed, never touches the real `~/.config/opencode`).

### Security and robustness

- Folder settings refuse the home folder and its parents, parents of credential folders,
  system roots (also macOS `/private/...`) and names with glob characters. Folders behind
  symlinks get rules for both paths.
- Agents may read but not edit the opencode config folder (agent definitions placed there
  could override permissions), this toolkit's `configs/` and `codebase/`, or project-level
  opencode config. Consequence: develop this toolkit with another editor, not with opencode.
  `test-deployment` fails if agent definition folders appear in the config folder.
- `XDG_CONFIG_HOME` / `XDG_DATA_HOME` are honoured, as opencode does.
- Deploy validates everything before the first write; all writes are atomic; `--dry-run`
  writes nothing.
- Skill removal only touches skills the kit installed (checked names, paths inside the skills
  folder, folders with `SKILL.md`); a user's own folder in the way is moved to `backups/`.
  A broken upstream skill is skipped with a warning instead of blocking every deploy.
- Default temp folder is per user (`<system temp>/opencode-<user>`); the temp folder must be a
  real folder owned by the user and is set to mode 0700.
- A real `local` deploy stops when LM Studio is unreachable and no model set exists (the example
  set is only used by `preview-configs` and `--dry-run`); a changed server URL triggers a new
  choice; contexts below 32768 get a warning.
- Corrupt JSON files stop with an `ERROR:` naming the file and the fix; Ctrl-C/EOF abort
  cleanly; opencode calls have a bounded retry budget; the knowledge-base check works offline.
