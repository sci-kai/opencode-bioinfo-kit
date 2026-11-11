---
name: test-pipeline-asserts
description: 'Write pipeline-level nf-test assertions that check designed outcomes, not only snapshots: stable_path and stable_content with a .nftignore for volatile files, explicit count asserts tied to design.tsv, structure checks instead of content for path-bearing files, and tests for failed workflows (workflow.failed plus error text). Use on top of nf-core-nf-test when a pipeline test must prove behaviour.'
---

# Pipeline-level asserts

## Purpose

Make a pipeline nf-test prove that the output matches the designed outcome and that bad input fails clearly. For nf-test basics, commands and snapshot handling use `nf-core-nf-test`.

## When to use

- Writing `tests/default.nf.test` or a scenario test for a pipeline.
- A snapshot alone would hide wrong results, or volatile files make it unstable.
- Not for module-level tests (`nf-core-nf-test`).

## Steps

1. Success test skeleton:

   ```groovy
   then {
       def stable_path    = getAllFilesFromDir(params.outdir, relative: true, includeDir: true,
                              ignore: ['pipeline_info/*.{html,json,txt}', 'multiqc/multiqc_plots/**'])
       def stable_content = getAllFilesFromDir(params.outdir, ignoreFile: 'tests/.nftignore')
       assert workflow.success
       assertAll(
           { assert path("$outputDir/metrics.tsv").readLines().size() == 3 },   // as designed: E01..E02
           { assert snapshot(stable_path, stable_content).match() }
       )
   }
   ```
2. Add designed-outcome asserts from `design.tsv` (`test-synthetic-dataset`): counts, specific rows, status strings. Comment each with the design ID. Assert something must be absent too (`assert !text.contains('corrected value')`).
3. `tests/.nftignore`: list volatile files: dates in VCF headers (compare records instead), MultiQC data and plots, HTML reports, `pipeline_info/*`, tool run directories, indexes. For a file with absolute paths (validated sample sheet) assert structure (line count, header prefix), not content.
4. Strip the Nextflow version from versions files (`removeNextflowVersion`) so tests pass on several Nextflow versions.
5. Fix dates and seeds in `tests/nextflow.config` (e.g. `submission_date`, `reference_date`).
6. Failure test (recommended; not yet used in existing projects):

   ```groovy
   test("UC03 missing combined report fails") {
       when { params { input = "$projectDir/tests/data/generated/uc03.tsv"; outdir = "$outputDir" } }
       then {
           assert workflow.failed
           assert workflow.exitStatus != 0
           assert (workflow.stdout + workflow.stderr).any { it.contains('ERROR:') && it.contains('combined report') }
       }
   }
   ```
   If the message is only in `.nextflow.log`, read the log file instead. Never snapshot a failed run's work dir.
7. Tag tests (`pipeline`, `subworkflows_local`, `slow`) and run narrow: `nf-test test tests/default.nf.test --profile +conda`.
8. For tests that need an external tool (e.g. a submission client), tag them and let the runner skip them when the tool is missing, saying so in the report.

## Checks before finishing

- The test fails if you break the feature (mutate once and see it go red).
- Snapshot diff reviewed; each changed value explained.
- Run twice: second run passes without snapshot changes.

## Pitfalls

- Snapshotting everything: unstable, and reviewers stop reading it.
- Asserting only `workflow.success`: that proves nothing about the content.
