---
name: data-samplesheet-schema
description: 'Design and validate a sample sheet: TSV (CSV only by recorded decision or vendor format), sample column, n/a for empty, paths relative to the sheet, per-column nf-schema JSON Schema with pattern/errorMessage/meta, cross-row checks in a Python script, validated copy published. Use when adding or changing a pipeline input sheet or its schema_input.json.'
---

# Sample-sheet schema

## Purpose

One predictable, validated input sheet per workflow, with errors a biologist can act on.

## When to use

New or changed `assets/schema_input.json`, a new input sheet (samples, known variants,
strata), or sheet errors. Not for genomic content checks (`bioinformatics-agent`).

## Steps

1. Format: TSV with `.tsv`, header row, `sample` column, no whitespace in column names, values with spaces double-quoted, `n/a` for empty. If the project records CSV as a decision (or the format is vendor-defined), keep it and state this in `docs/usage.md`.
2. Layout: row-oriented by default; EAV (`sample`, `key`, `value`) only for long values, pivot downstream with `pivot_table()`.
3. Paths: relative to the sheet's directory, resolved by the pipeline; no index-file columns (use `.tbi`/`.bai` next to the file or create it).
4. Write `assets/schema_input.json` (draft 2020-12):
   ```json
   {"$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://raw.githubusercontent.com/<org>/<repo>/main/assets/schema_input.json",
    "title": "<repo> pipeline - params.input schema",
    "description": "Relative paths resolve against the sheet's directory; empty or 'n/a' marks an empty optional field.",
    "type": "array",
    "items": {"type": "object",
      "properties": {
        "sample": {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_.-]*$",
                   "errorMessage": "sample must be given and use only A-Z a-z 0-9 _ . -",
                   "meta": ["sample"]},
        "technology": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$", "meta": ["technology"]},
        "vcf": {"type": "string", "format": "file-path", "exists": true, "pattern": "^\\S+\\.vcf\\.gz$"}},
      "required": ["sample", "technology", "vcf"]}}
   ```
   Every property gets a pattern or enum plus an `errorMessage`.
5. Wire it with nf-schema `samplesheetToList(params.input, "assets/schema_input.json")`; the param is declared with `schema` in `nextflow_schema.json` (via `nf-core pipelines schema build`).
6. Cross-row rules (unique sample+technology, exactly one truth technology, tumor_id != normal_id, all rows reference the same genome build) go in `bin/<pipeline>_check-sheets.py`, which reads the sheet and prints `ERROR: <file>: row <n>: <field>: expected <x>, found <y>; fix: <hint>` and exits non-zero.
7. Treat `n/a` and empty as empty in both layers; do not let `n/a` reach tools as a path.
8. Publish the validated, path-resolved copy to `pipeline_info/samplesheet_validated.tsv`.
9. Provide a tiny valid example (synthetic IDs) in `assets/` and one failing example per rule for tests.

## Checks before finishing

- Example sheet passes; each failing example fails with the intended message.
- Docs list every column, allowed values, whether required.
- No real sample names in committed sheets.

## Pitfalls

- Regex on sample IDs that later breaks file names; allow only the CUBI file-name set.
- Embedding cross-row logic in the schema; keep it in the script.
- Absolute paths in committed sheets.
