---
name: data-output-docs
description: 'Document pipeline and tool outputs: a numbered per-step output tree, typed column tables per file, missing-value and coordinate conventions, report entry points, and a usage page with pins and compatibility. Use when a step adds or changes an output file or column, or when docs/output.md is missing or out of date.'
---

# Output documentation

## Purpose

Every file a run writes is findable, and every table column has a name, type and meaning.

## When to use

Any change to outputs; release preparation. Not for README prose or paper methods (`paper-writing`).

## Steps

1. `docs/output.md` starts with conventions:
   | Type | Meaning |
   |---|---|
   | int | integer; `pos` 1-based, BED `start` 0-based and `end` exclusive |
   | float | decimal, 4 digits; `NA` if undefined |
   | text | free text or label; missing is `.` for names/alleles |
   Also: BED headerless TSV, TSV with one header, ISO dates, `YYYYMMDD` in file names.
2. Show the output tree in a code block, one folder per step, numbered in run order when per-case (`1_collect_case_data/ ... 8_...`); say which folders appear only under which parameter. Mark `<placeholders>` (`<sample>`, `<YYYYMMDD>`).
3. Overview list and a table "folder -> tools" (with CITATIONS.md link).
4. Per section: `<details markdown="1"><summary>Output files</summary>` with the file list, then a column table (name, type, meaning). For key/value reports list every key.
5. Name the entry point: main report (MultiQC HTML), table browser (datavzrd `index.html`), start page, and the zip bundle for sending.
6. Document derived identifiers, rules lists (e.g. correction rule names) and which files are copies versus working files.
7. `docs/usage.md`: every param and input with default, a pins/compatibility table (component, pin, note), tested inputs (tool, version, data), stage/normal-workflow steps, and the format decisions that deviate from CUBI defaults.
8. Keep `CHANGELOG.md` in step: each feature lists new/changed files and columns.
9. Generate column lists from code where possible (a test compares the documented header with the written one).

## Checks before finishing

- `diff` between actual output tree of a test run and the documented tree shows no undocumented file.
- Each documented table header equals the written header (test).
- Links resolve; no real identifiers in examples.

## Pitfalls

- Documenting intent rather than what the code writes.
- Mixed missing-value markers inside one table without saying which column uses which.
- Forgetting step folders that exist only under a flag.
