# CUBI Rules — Condensed Reference

Operational digest of the CUBI knowledge base "rules" category. This is what you need for
day-to-day decisions; it is not the full wiki. For anything not covered here in enough detail
(tech-talk articles, hint/troubleshooting articles, or the full text of a rule below), read the
source file directly rather than guessing — see "Where to look for more" at the bottom.

## Git: branches, remotes, history

- Constant branches: `main` (production releases only, never push/rebase/rename/delete; emergency fixes only, with a post-mortem) and `dev` (central development branch, never push directly, never merge *into* another branch except fast-forwarding into `main`).
- `prototype` branch: only for the very earliest "nothing works yet" stage of a new repo; delete it once `dev` takes over.
- Feature/tool-repo work: branch off `dev`, name `feat-<short-desc>`. Issue fixes: `issueNN-<short-desc>`. Project-repo analysis work: `analysis-<short-desc>` (may live much longer).
- One branch per unit of work. Clean up commit history with `git rebase --interactive dev` before merging. Delete the branch everywhere after merge.
- History in `main`/`dev` must stay linear: rebase-and-merge or fast-forward only — never a merge commit or squash commit on `main`/`dev`. Sole exception: nf-core `TEMPLATE` sync merges.
- Remotes: `github` (org `core-unit-bioinformatics`) and `githhu` (HHU-GitLab, group `cubi`); a combined remote named `all` pushes to both. Workflow/tool repos and the knowledge base use both remotes; CUBI project repos (sample-specific/internal) use `githhu` only. When in doubt, GitLab only. github is the primary platform for issues/PRs when both are configured.
- Workflow repos assume only Linux: no hardcoded paths/env vars, no runtime downloads, no project-specific data transforms.

## Naming

- Workflow repos: `workflow-[system]-[short-desc]` (`system`: `smk`=Snakemake, `nxf`=Nextflow, `cwl`, `wdl`). Project repos (2025+): `project-[short-desc]` (no type prefix).
- Files: `a-z0-9` standard, `A-Z` only for names/IDs; `-` within a context (dates), `_` between contexts (`SAMPLE1_dataA`), `.` only for format (`.vcf.gz.tbi`). No whitespace or other special characters.
- Python/Snakemake code follows PEP8 (black/snakefmt).

## File types & repo content

- `.py` (`#!/usr/bin/env python3`), `.R` (`#!/usr/bin/env Rscript`): executable, no workflow-engine coupling. `.sh` discouraged (prefer Python/Snakemake; if used: `#!/usr/bin/env bash`, executable); no raw `.awk` (wrap in bash). `Snakefile`/`.smk`, `.nxf`, `.def` (Apptainer). `.ipynb` never replaces a workflow script.
- Config: `.yaml` preferred, `.json` ok; `.toml` only for `pyproject.toml`. Tables: `.tsv`; `.csv` strongly discouraged. Docs: `.md`, readmes named `README.md`.
- No Windows line endings except verbatim client-supplied raw files under `annotations/raw`.
- Never commit programmatically generated results, except verbatim client-supplied documents and small look-up result tables (project repos, see below).

## Project repository layout (project repos, not workflow repos)

- Initialise with `cubitools git`; add the CUBI metadata files (`update_metadata.py`). Main readme: `README.md` (preferred, concise: contact/client, purpose, data, pointers) or `docs/README.md`.
- Standard subfolders: `annotations/{raw,export,norm}` (`README.md` names the raw source; raw is never edited; export unchanged to plain text → norm, each step scripted), `samples/` (authoritative sample sheets; one copy per infrastructure, named explicitly), `config/` (authoritative run configs, identifiable names like `config/<workflow>/run-config.yaml`), `docs/` (with `README.md`; subfolders such as `meetings/`, `methods/`, `milestones/`), `codebase/<analysis-name>/` (per-analysis code incl. its `scripts/`, `notebooks/`, `envs/`; root `notebooks/` and `scripts/` are deprecated).
- Analysis code is developed on an `analysis-` branch. Small look-up result tables (TSV) may be committed to `codebase/<analysis-name>/results`, described in `docs/milestones/<analysis-name>.md`. Configs of generic workflows go to `config/`, never `codebase/`.
- Merge to `main`: annotations, sample sheets and docs immediately; configs after a successful run; `codebase/` at milestones and when an analysis is complete (`git cherry-pick` if needed). The README documents every analysis and lists all active branches.

## Sample sheets

- Every workflow takes a sample sheet. TSV (`.tsv`), ASCII, header row with a `sample` column; no whitespace in column names; quote values containing spaces; no empty fields — use `n/a`.
- Layout: one row per sample, or EAV (`sample`, `key`, `value`). Input paths may be a folder, a file, a `.fofn`, or a comma-separated mix.

## Versioning & dates

- Semver `MAJOR.MINOR.PATCH` as a string; `v` prefix optional. Qualifiers `-dev`, `-dirty`, `-ptyp` (e.g. `0.2.0-dev`, tag `v0.2.0-dev`). Workflows: removed features, changed semantics, or tool updates that change output = MAJOR. Python: parse/compare with `semver`.
- ISO 8601 only: `YYYY-MM-DD`, `YYYYMMDD` in filenames, 24 h `hh:mm:ss`, `YYYY-MM-DDTHH:MM:SS`. UTC offset only if strictly needed; no other time-zone notation.

## External (third-party) pipelines

- Adopt only if: fits the data/methods (e.g. UMI handling); runs offline on HPC (containers/pre-downloadable resources); usable docs; real QC reports; reference/engine version via config; stable versions + CHANGELOG; clear open license.
- Integrate: fork the release branch only; keep upstream license notices; add CUBI license/citation/`pyproject.toml` (upstream + own version; `cubi/` on name clash); credit upstream authors; mark new/modified files MIT → CUBI license.

## Where to look for more

- Full rule text: `~/.config/opencode/cubi-kb/rules-kb-agents-instructions.md`.
- Tech-talk articles (nf-core setup, Nextflow config, minimap2, SVIM, conda-pack, etc.): `~/.config/opencode/cubi-kb/tech-kb-agents-instructions.md`.
- Hints/known-issue articles (offline conda, GPU-in-containers, IGV, matplotlib, thinkpad quirks, etc.): `~/.config/opencode/cubi-kb/hints-kb-agents-instructions.md`.
- These are not preloaded into every agent's context to keep it small and precise — read the specific file when a task actually needs that level of detail (the `debug-agent` subagent does this routinely; any agent can).
