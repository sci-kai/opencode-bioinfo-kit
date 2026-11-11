---
name: test-usecase-table
description: 'Write down use cases and requirements as docs/use-cases.md: an overview table (ID, situation, synthetic ID, expected result, test names), one section per use case, must-fail cases included, and test names that carry the use-case ID. Use when starting a feature, documenting tested behaviour, or mapping requirements to tests.'
---

# Use-case table

## Purpose

Make the supported (and rejected) situations explicit and traceable to tests.

## When to use

- A project has user-visible behaviour and no `docs/use-cases.md`.
- A feature adds, changes or rejects a situation.
- Not for internal unit-level behaviour; that stays in test docstrings.

## Steps

1. Collect situations from the requirements, the plan file, issues and the real-world cases (described without real identifiers). Include situations that must be rejected.
2. Create `docs/use-cases.md` with this header: it lists UC01..UCnn that the tool supports or must reject; each is covered by tests on synthetic data; all IDs are synthetic; where the test names live (pytest `tests/python/<file>::<function>`, nf-test test name) and any fixed dates from `tests/nextflow.config`.
3. Overview table:

   | UC | Situation | Synthetic ID | Expected result |
   |----|-----------|--------------|-----------------|
   | UC01 | WES, one approved run per sample | case-0500 | Submission folder and metadata are built |
   | UC03 | Several runs, no combined report | case-0129 | Fails with a named error |

4. One section per use case:
   - Situation: what is true about the data.
   - Input: synthetic ID, parameters.
   - Expected: files, values, error text, exit status.
   - Tests: exact `file::function` and nf-test names.
5. Name tests with the ID: `test_uc01_wes_single_run`, nf-test `"UC01 UC11 WES single run, fixed submission date"`. One test may cover several UCs.
6. Add the synthetic cases to the generator and `design.tsv` (`test-synthetic-dataset`).
7. For research code with requirements instead of use cases, keep an R-table (`R1..Rn`, text, plan section) and a decisions log (ID, date, decision, who decided); map each R to tests in a column.
8. Document tested inputs in user docs: which tools, versions and formats were tested, which are expected to work but untested, and the formal input requirements.
9. Update the table in the same commit as the feature (code, tests, docs, CHANGELOG).

## Checks before finishing

- Every UC row names at least one existing test; every test name resolves (`pytest --collect-only -q | grep uc01`).
- Must-fail cases are present and have the error text.
- No real identifiers anywhere.

## Pitfalls

- Table and tests drifting apart: grep the names in CI or before release.
- Use cases written as implementation notes: keep them in terms of the user's situation.
