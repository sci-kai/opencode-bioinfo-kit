---
name: data-raw-to-normalized-tables
description: 'Turn a manually maintained table (Excel/CSV from a client or colleague) into clean TSV without touching the original: column map with aliases, normalization rules, a corrections table, an issues table, encoding fallback, strict assertions. Use when a pipeline reads a hand-edited sheet with typos, odd whitespace, mixed date formats or marker characters.'
---

# Raw to normalized tables

## Purpose

Make errors in hand-maintained tables visible, correctable and auditable instead of silently
fixed or silently propagated.

## When to use

A pipeline starts from an Excel/CSV that people edit. Not for machine-generated tables with a
schema (`data-samplesheet-schema`). Privacy: design from headers, code and synthetic rows; never open the real table.

## Steps

1. Treat the raw file as immutable and read-only; never save into it. Read `.xlsx` with openpyxl `read_only=True, data_only=True`, in one normalization step that emits TSV.
2. Column map in `assets/<table>_columns.json`:
   ```json
   {"description": "Column map and format rules (source of truth).",
    "header_search_rows": 10,
    "columns": {"sample_name": {"aliases": ["Name", "Sample name"], "kind": "text", "mandatory_header": true},
                "sample_date": {"aliases": ["Date"], "kind": "date"}}}
   ```
   Match headers after removing line breaks, NBSP, surplus whitespace, case-insensitive. A missing mandatory header stops the run with the headers found.
3. Encoding: read bytes, try `utf-8-sig`, then `cp1252` with a warning; write UTF-8, `newline=""`, Unix line endings. Reject or escape tabs/newlines inside TSV cells.
4. Normalization rules, each with a stable name: whitespace trimmed, zero-width/special spaces removed, mojibake fixed, dash unified, prefix added/removed, uppercased, Excel serial to date, percent scaled, date to `YYYY-MM-DD`, value mapped (controlled vocabulary), marker character removed into its own flag column.
5. Three outputs, always:
   - `<table>_normalized.tsv`: `row` (source row) then canonical columns, plus `invalid_fields`; invalid cells emptied.
   - `<table>_corrections.tsv`: `row`, `column`, `header`, `original`, `corrected`, `rules`.
   - `<table>_issues.tsv`: `row`, `column`, `header`, `value`, `severity`, `message`.
6. Issues are anything needing a manual fix: unreadable date, duplicate key, columns that disagree, date before birth/collection, value outside vocabulary. Message names what is wrong and what to do.
7. Downstream steps read only the normalized table and refuse rows with issues in the fields they need (strict assertions: fail with file, row, column, expected, observed).
8. Selection tables (`<YYYYMMDD>_<what>.tsv`) are derived from the normalized table, dated with `--reference_date` or today.
9. Add a unit test per rule on synthetic rows, including the marker characters and typos known from past incidents.

## Checks before finishing

- Raw file checksum unchanged after a run.
- Every correction has a rule name; every rule appears in `docs/output.md`.
- Re-running gives identical output.

## Pitfalls

- Auto-correcting ambiguous values (guessing a date format); report as an issue instead.
- Losing the source row number; users need it to fix the sheet.
- Logging real values; keep reports in the run output, not in git or chat.
