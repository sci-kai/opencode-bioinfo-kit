---
name: test-tier-plan
description: 'Plan how a project is tested: tiers T0 (synthetic), T1 (small real slice), T2 (full data on HPC), the exact commands per tier, the pre-commit check list, and what to do when a tier cannot run on the current machine (Raspberry Pi, offline HPC). Use at project start, when adding a feature that needs new tests, or before reporting test results.'
---

# Test tier plan

## Purpose

Give every project one written answer to "what runs where, on which data, with which command".

## When to use

- Starting a workflow or tool, or adding a feature that needs tests.
- A test cannot run on the local machine and you must say so and hand over a command.
- Not for nf-test syntax (use `nf-core-nf-test`) or for data download (use `refdata`).

## Steps

1. Read CLAUDE.md, README and `tests/`; note the machine limits (aarch64, no Docker, little RAM, offline HPC).
2. Write a tier table into `docs/testing.md`:

   | Tier | What | Data | Where | Command |
   |---|---|---|---|---|
   | T0 | pytest of `bin/`, module and subworkflow nf-tests, pipeline on synthetic data | generated | anywhere | `pytest`; `nf-test test --tag subworkflows_local --profile +conda` |
   | T1 | pipeline on a small real slice (e.g. chr22 of SEQC2) | test-data repo | laptop / Pi | `nextflow run . -profile test_seqc2,conda` |
   | T2 | full data | full dataset | HPC | `nextflow run . -profile test_full,singularity` |

3. Name the data source per tier and how it is regenerated (see `test-synthetic-dataset`). Test data repos hold data only; generators stay with the code.
4. Define the pre-commit checklist and put it in CLAUDE.md. For Nextflow repos:
   `scripts/check_syntax.py` (or `nextflow lint`), `nf-core pipelines lint`, the relevant `nf-test test`, `pytest`, `black` + `ruff check`, and a `-stub` run when real data cannot run locally.
   For stdlib orchestration repos without tests: `python3 -m py_compile <files>`, `bash -n <scripts>`, and the tool's `--dry-run`.
5. Keep tiers fast: small per-label resources in `tests/nextflow.config`, shared conda cache for nf-test, micromamba where available. Measure and note the run time of each tier.
6. Define when each tier is required: T0 on every commit, T1 before merging into `dev`, T2 before a release.
7. For anything that could not run locally, write the exact command for the machine where it can, in the test report (`test-report`).

## Checks before finishing

- Every tier has a command that works as written.
- The checklist names tools that exist in the project environment.
- No tier needs production paths or real sample data.

## Pitfalls

- A T1 dataset that grows past a few hundred MB: keep it in a separate repo with checksums.
- aarch64 hosts: biocontainer images are often amd64 only; use the conda profile there.
- `-stub` passing does not prove tool behaviour; report it as a stub run.
