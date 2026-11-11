---
name: data-format-choose
description: 'Choose the storage format and rules for a kind of information (config, sample sheet, output table, record, state, cache, backup, log, report, genomic file). Use when starting a new project or file type, or when a format choice is disputed. Holds the full format decision table and the default for every known contradiction between projects.'
---

# Choose a data format

## Purpose

Give every kind of information one format with one rule, so projects stay consistent and tools
(nf-schema, pandas, grep, git diff) work without conversion. Prefer general-purpose,
text-based formats over binary ones.

## When to use

New project, new file type, a reviewer asks "why this format", or a project mixes formats.
Not for deciding how to validate (see `data-samplesheet-schema`, `data-pinned-schema-validation`).

## Steps

1. Read the project's CLAUDE.md/docs. An established project convention wins; if you deviate,
   record the decision (what, why, date) in the docs.
2. List the kinds of information the change touches.
3. Look each up in the table below and apply the rule.
4. Check the contradiction defaults below when two conventions collide.
5. Record the choice in `docs/usage.md` or `docs/output.md`.

## Decision table

| Kind of information | Format | Rule |
|---|---|---|
| Human config, app defaults | YAML | Commented `config.example.yaml` committed, real file gitignored; `n/a` for unset; unknown keys rejected |
| Shared bash + Python paths/thresholds | `KEY=value` `.env` | Only when both read the same file; no interpolation; one file per scope |
| Nextflow params | `params.yaml` / `nf-params.json` + `.config` | One per step in `config/<step>/` |
| Pins, site settings, column maps | JSON with a `description` key | Vendored; sha256-pinned where external |
| Sample sheets | TSV | Header with `sample`; `n/a` empty; paths relative to sheet; nf-schema + cross-row script; publish validated copy |
| Output and audit tables | TSV with header | `NA` missing numbers, `.` missing names/alleles; ISO dates; 4-digit floats; each column documented |
| Per-file check report | TSV `key`,`value` | One row per message; `status` first |
| Records exchanged with others | JSON + JSON Schema | `$schema` in the file; validate before write |
| Run/orchestration state | JSON, sorted keys, indent 2, final newline | Atomic write, lock file, UTC ISO timestamps; completion from real outputs |
| App data store | SQLite | One transaction per action, integrity check, snapshot with the online backup API |
| HTTP/API cache | SQLite key to body | Key = sha256 of canonical request; TTL; rebuildable; gitignored |
| Download cache | files + `registry.json` | Size, mtime, checksum, verified flag |
| Portable export | JSON | `format`, integer `format_version`, sha256 of canonical content; read older, refuse newer |
| Backups | timestamped copies | `<stem>_<YYYYMMDD>-<hhmmss>.<ext>`; keep-N; safety copy before restore |
| Integrity list | `checksums.sha256` (md5 only if upstream publishes md5) | `verify` command recomputes |
| Logs | `.log`, rotating or cumulative | Run header with timestamp and run ID |
| Reports | MultiQC HTML main report, datavzrd tables, zip bundle | Self-contained, works offline |
| Genomic | VCF bgzip + `.tbi`/`.csi`; BAM + `.bai`/`.csi`/`.crai`; BED headerless TSV; FASTA + `.fai` | BED 0-based half-open, VCF 1-based; no index columns in sheets (use or create the index) |
| Documentation | Markdown | `README.md`, `docs/usage.md`, `docs/output.md` |

Never: `.toml` except `pyproject.toml`; `.ipynb` as workflow code; Excel as a pipeline output.

## Defaults where projects contradict

- Sheets: TSV, CSV only by recorded project decision or vendor format (Illumina). Outputs are always TSV.
- Empty: `n/a` in sheets/configs; `NA`/`.` in output tables, documented per column.
- Checksums: sha256 for own data, md5 only when matching upstream md5 lists.
- Timestamps in state/provenance: UTC ISO with offset. File names: `YYYYMMDD` or `YYYYMMDD-hhmmss`.
- Completion: from real outputs, not `.done` markers.
- Backup naming: prefix-and-timestamp, not `.bak` suffix chains; `<name>.bak` is allowed as a one-step undo for a config edit.

## Checks before finishing

- Each kind has exactly one format, listed in the docs.
- Deviations from the table are recorded with a reason.
- No format here is replaced by Excel, `.csv` or `.toml` without a recorded decision.

## Pitfalls

- A vendor format (Illumina CSV) is not a reason to use CSV elsewhere.
- JSON for config people edit by hand loses comments; use YAML there.
- Do not sync a live SQLite file; sync snapshots.
