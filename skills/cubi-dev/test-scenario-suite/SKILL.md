---
name: test-scenario-suite
description: 'Build a scenario suite for a pipeline in a separate test project: a YAML matrix of scenarios (params plus expected outcome and checks), small and full suites, site configs, a runner that writes one run folder per run with a manifest and summary, and the outcomes PASS, FAIL, XFAIL, XPASS. Use for feature and regression testing of a pipeline revision on reference data without touching production.'
---

# Scenario suite

## Purpose

Run one pipeline revision through many parameter sets and check each against an expected outcome, then compare revisions.

## When to use

- Several feature sets (defaults, production parameters, filters, expected failures) must be verified before a release or template update.
- Not for module tests (nf-test) or unit tests (pytest).

## Steps

1. Create a test project `project-<pipeline>-tests` (project-repo rules apply; prepared data, caches and `runs/` are gitignored):

   ```
   config/datasets/<name>.yaml     sources, md5, sample order, pairs
   config/suites/small.yaml        small data (laptop/Pi); full.yaml inherits all small scenarios
   config/sites/<site>.yaml|.config  executor, container backend, resource limits
   scripts/<runner>.py             prepare-data, run, compare (+ verify)
   scripts/envs/<runner>.yaml      conda env
   tests/                          pytest of the runner itself
   ```
2. Suite file: a header documenting the keys, `default_expect` applied to every success scenario, then scenarios:

   ```yaml
   scenarios:
     defaults_wes:
       params: {input: wes_samples.tsv}
       expect: {success: true, files: {"results/*.tsv": 1}}
     fail_missing_bed:
       params: {input: wes_samples.tsv, tmb: true}
       expect: {success: false, error_contains: "Need to specify bedfile"}
     known_issue_x:
       expect: {xfail: "issue #12"}
   ```
3. Include expected-failure scenarios for each guard in the pipeline (missing input, missing required parameter).
4. Outcomes: PASS (ran as expected and all checks passed), FAIL (unexpected status or failed check), XFAIL (known issue still present), XPASS (known issue gone: remove the `xfail`). The runner exits 1 on any FAIL or XPASS.
5. Run folder `runs/<YYYYMMDD>_<suite>_<site>_<label>[-<commit>]/` with `manifest.json` (pipeline commit, `-dirty` marker, Nextflow version, dataset manifest md5, runner version, profile source), `summary.md` and `.json` (Scenario, Outcome, Checks ok n/m, Duration, Note), and per scenario `params.json`, `stdout.txt`, `nextflow.log`, `status.json`, `results/`, `normalized/`. Support `--scenarios a b` and `--resume`.
6. Run two revisions and compare them (`test-regression-compare`). Test the runner with pytest.
7. Document how to add a scenario: add an entry, run it with `--scenarios <name>`, commit the suite file.
8. Offline HPC: pre-fetch images and plugins, state this in the README.

## Checks before finishing

- Each scenario has an `expect`; each failure scenario has `error_contains`.
- The summary says which pipeline revision, data and site were used.

## Pitfalls

- Reading error text from stdout only; also search `nextflow.log`. A summary line such as "message not found in the log" means the guard changed, not necessarily that it broke.
- Scenarios that need real production parameters: read them from the production repo at run time with data paths replaced; never copy secrets.
