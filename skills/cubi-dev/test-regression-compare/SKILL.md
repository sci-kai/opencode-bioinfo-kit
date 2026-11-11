---
name: test-regression-compare
description: 'Compare outputs before and after a change on the same input: run both versions, normalise volatile fields (dates, command lines, run times), diff tables and VCF records record by record, show the differences, and confirm only the intended records changed. Use for every result-affecting change such as a tool update, template sync, filter or threshold change.'
---

# Regression comparison

## Purpose

Show that a change altered only what it was meant to alter.

## When to use

- Tool or container version bumps, template syncs, changed thresholds, refactors of result code.
- Not for new features without a previous output (use `test-pipeline-asserts`).

## Steps

1. Fix the input: the same synthetic or T1 data, same parameters, same seed. Record pipeline commit (add `-dirty` if uncommitted), tool versions and data checksum.
2. Run the baseline (old revision, e.g. `dev`) and the candidate into separate run folders under the scratch area, e.g. `runs/<YYYYMMDD>_<suite>_<label>/`. Never overwrite the baseline.
3. Normalise volatile content before diffing:
   - VCF headers: drop dates and tool command lines (`bcftools view -H` compares records only).
   - TSVs: sort by key columns; drop run-time columns.
   - Ignore HTML, plots, logs; compare indexes and `pipeline_info/` by presence only.
4. Compare record by record: file lists first, then per file `diff <(sort a) <(sort b)`, or pandas `merge` on the key with `indicator=True`. Count added, removed, changed records per file.
5. Classify every difference: intended (expected by the change), unintended, or noise. Explain each intended one in one line.
6. Show the differences to the user (counts and a few examples, no sensitive content). Check the unaffected steps: their outputs must be identical.
7. Exit status: the comparison tool exits non-zero if anything differs, so it can be scripted.
8. Record the result in the test report (`test-report`): baseline, candidate, data, counts, verdict.

## Checks before finishing

- Same input and parameters verified for both runs (manifest compared).
- Zero unexplained differences, or each one named.
- The baseline run folder still exists.

## Pitfalls

- Comparing after tool updates without pinning: version drift looks like a regression.
- Differences hidden by over-aggressive normalisation: list what you normalised.
- Reading record contents of real data into context: use counts and headers only; real data stays out of fixtures.
