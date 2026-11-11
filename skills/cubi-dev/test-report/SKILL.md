---
name: test-report
description: 'Write a faithful test report: which commands ran, on what data and machine, what passed, failed or did not run, and the exact command to run the missing parts elsewhere. Use at the end of any testing task, at version milestones, and before claiming that something works.'
---

# Test report

## Purpose

Tell the user exactly what was verified and what was not. Never claim a test that did not run.

## When to use

- Finishing a change, a milestone, or a review that involved tests.
- Not as a substitute for running the tests.

## Steps

1. Collect facts while testing: command, working directory, environment (conda env name), data (dataset name, synthetic or T1/T2, checksum or manifest), machine (e.g. Pi, aarch64), date.
2. Report per tier (`test-tier-plan`):

   | Check | Command | Data | Result | Note |
   |---|---|---|---|---|
   | pytest | `pytest -q` | generated | PASS 124 / FAIL 0 / SKIPPED 3 | 3 need `--network` |
   | nf-test | `nf-test test tests/default.nf.test --profile +conda` | synthetic | PASS | snapshot unchanged |
   | T1 | `-profile test_seqc2,conda` | SEQC2 small | NOT RUN | needs 8 GB RAM; run on laptop with the same command |

3. Use PASS, FAIL, SKIPPED, NOT RUN. Use XFAIL/XPASS only for tracked known issues.
4. Failures: paste the first error lines, the likely cause, and whether it is new (compare with the baseline).
5. Result-affecting changes: add the before/after comparison (`test-regression-compare`): counts of added, removed, changed records and the verdict on whether each is intended.
6. Unaffected steps: state that their outputs were checked unchanged, or that they were not checked.
7. List open gaps: untested use cases, untested tool versions, tiers not run, with the exact command for the machine that can run them.
8. At version milestones summarise what was done, what was tested, what is open (feeds the CHANGELOG and plan status).
9. Coverage: report it only if measured (`pytest --cov`); there is no fixed target in the existing projects, so do not invent one.

## Checks before finishing

- Every claim in your final answer appears in the table.
- No real identifiers, paths to real data or record contents in the report.
- Skipped and not-run items are visible, not buried.

## Pitfalls

- "Tests pass" without numbers.
- A run with zero collected or zero asserted tests reported as PASS.
- Reporting a stub run as a real run.
