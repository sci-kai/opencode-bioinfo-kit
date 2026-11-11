# Coding, data and testing standards

Defaults for new code and data. Inside an
existing project, its own CLAUDE.md/AGENTS.md and established conventions win; where a
project deviates (e.g. CSV sample sheets), record the decision in its docs. Details and
procedures: subagents `python-dev`, `data-formats`, `test-design` and the
`cubi-dev` skills.

## Code (any language)

* **Central configuration.** Paths, URLs, hosts, file-name patterns, thresholds and resource locations live in central config files (`config/*.yaml`, pipeline params, a `.env` shared by bash and Python) and are passed in. No absolute paths or URLs buried inside functions or modules; unavoidable defaults are declared once, at the top of the file or in one constants module, with a comment saying where to override them. A missing required value stops with `ERROR:`, never a silent guess.
* **Review comments for generated code.** Code written by an agent is commented so a newcomer can review it: what each block does and why; for each check, which error it catches and what the user should do; for each correction or normalisation, what was wrong and which rule fixed it; for each non-obvious choice, a `# Design decision:` comment with the reason and the rejected alternative; for each assumption about input data, an `# Assumption:` comment. Plain words over jargon; explain tool flags on first use.

## Python

* Workflow helpers: one executable script per job in `bin/` (`#!/usr/bin/env python3`, argparse, `main()` only parses and orchestrates). More than ~3 scripts sharing logic: a package `bin/<pkg>/` plus thin CLI scripts. Stand-alone tools: src-layout package with `pyproject.toml` entry point, subcommands, `--version`, `--dry-run`.
* Module docstring: purpose, INPUT/OUTPUT (columns, types, 0-/1-based coordinates), checks that stop the script, and why a script (tools considered). Docstring per function; inline comment per block saying what it does exactly.
* Style: black + ruff (`E,F,W,I,B,UP`), line length 100, Python ≥ 3.10 unless the target server needs older; type hints in packages. Script file names with `_` so tests can import them.
* Thresholds and rules live in config files or documented params, never as unexplained constants. Stdlib-only where scripts run on production servers without managed envs.
* Environments: conda `envs/<name>.yaml` (conda-forge, bioconda, exact pins for tools); never `.venv`.

## Data

* Sample sheets: TSV with a `sample` column, `n/a` for empty, paths relative to the sheet; CSV only by recorded project decision or vendor format. Validate per column with a JSON Schema (nf-schema) and cross-row rules in a script; publish the validated copy.
* Config: YAML (commented example committed, real file gitignored, `n/a` for unset); JSON for exchanged records, pins and schemas; `KEY=value` `.env` only when bash and Python read the same file. Secrets and site IDs never in git: `<placeholder>` templates, real values from config outside the repo.
* Output tables: TSV with header, documented column by column in `docs/output.md`; missing numbers `NA`, missing names/alleles `.`; ISO dates; positions 1-based, BED 0-based half-open.
* Raw/client files are immutable: write normalized copies plus a corrections table (every automatic fix, with rule) and an issues table.
* Integrity: sha256 for own files, md5 where upstream publishes md5; a manifest records sources, versions, settings and checksums; a verify command recomputes them.
* Writes are atomic (tmp + `os.replace`); state files are sorted JSON with UTC ISO timestamps; completion is derived from real outputs, not marker files. Backups: `<stem>_<YYYYMMDD>-<hhmmss>.<ext>`, rotated, never next to live data when it is synced.

## Testing

* Tiers: T0 synthetic edge-case data (unit + script + nf-test, runs anywhere); T1 small real slice (SEQC2/GIAB, laptop/Pi); T2 full data (HPC). Name what could not run and give the exact command.
* Synthetic data comes from a generator script with fixed seeds and a `design.tsv` stating the intended outcome of every case; test data repos hold data only, generators stay with the code.
* Every input check has a failure test (missing/unreadable/empty/malformed file, missing column, unexpected ID): assert the `ERROR:` text and the non-zero exit.
* Use cases: `docs/use-cases.md` table (ID, situation, synthetic ID, expected result, test names), including must-fail cases; test names carry the use-case ID.
* Result-affecting changes: run before/after on the same input, normalize volatile fields, diff record by record, show the diff.
