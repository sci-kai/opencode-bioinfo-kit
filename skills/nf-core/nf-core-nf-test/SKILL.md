---
name: nf-core-nf-test
description: 'Write, run, and maintain nf-test tests for nf-core modules, subworkflows and pipelines: test skeletons, required assertions, snapshot generation and deliberate snapshot updates, tags, profiles, and stub tests. Use for any testing task on Nextflow code.'
argument-hint: 'Component or pipeline to test, and the container backend (docker/singularity/conda)'
user-invocable: true
---

# nf-test for nf-core

**Canonical guides:** <https://nf-co.re/docs/developing/testing/overview>,
<https://nf-co.re/docs/developing/testing/assertions>,
<https://nf-co.re/docs/developing/testing/advanced>

## Non-negotiables

- Every new or changed module/subworkflow has a working test under its `tests/` directory.
- **A test run that produced no assertions is not a pass.** Read the actual output.
- Never regenerate a snapshot to make a red test go green without first explaining *why* each changed value changed.

## Running

```
nf-test test <path/to/main.nf.test> --profile <docker|singularity|conda>
nf-test test --tag <tag>                     # narrow by tag
nf-core modules test <name>                  # modules repository only
nf-core subworkflows test <name>             # modules repository only
```

Run the narrowest scope that covers the change; only widen when the change is pipeline-level.
Pipeline-level changes additionally need a smoke run:
`nextflow run . -profile test,<backend> --outdir <tmp-outdir>`.

Snapshots are created on first run and must be committed with the code. Refresh deliberately:
`nf-test test ... --update-snapshot` (or `nf-core modules test <name> --update`), after review.

## Minimum assertions

```groovy
then {
    assertAll(
        { assert process.success },
        { assert snapshot(process.out).match() }
    )
}
```

If a full `process.out` snapshot is not stable, keep at minimum:

```groovy
{ assert process.success },
{ assert snapshot(process.out.versions).match("versions") }
```

plus real assertions on the outputs you care about. `process.out` covers all output channels,
named and index-based.

## Stable vs unstable outputs

nf-test fingerprints files by MD5, so anything containing a timestamp, a path, a thread count,
or a random seed will produce an unstable snapshot. For those, assert properties instead:

```groovy
// file exists
assert file(process.out.interop[0][1].find { file(it).name == "IndexMetricsOut.bin" }).exists()

// content contains something specific
assert path(process.out.log.get(0).get(1)).readLines().any { it.contains('/LIBS/GUID') }
```

Other useful forms: line counts, `.contains()` on channel collections, and indexing
(`out.bam.get(0).get(1)` — index 0 is the emitted item, index 1 the file next to the meta map).

## Configuration inside tests

Set params and process config in the test itself:

```groovy
config './nextflow.config'
params {
    outdir = "$outputDir"
}
```

with `withName:` selectors in `tests/nextflow.config` to exercise specific `ext.args` values.

## Coverage expectations

- At least one realistic case, plus the meaningful variants (single-end **and** paired-end for read-based modules).
- A `-stub` test for modules whose real execution is too heavy for CI.
- Use the minimal shared test data rather than adding new large fixtures.

## Debugging a failing test

`println` inside the `then` block before `assertAll` to inspect values; check
`.nf-test/tests/<hash>/work/.../.command.err` and `.command.sh` for the real tool error. Remove
debug output before committing.

**Privacy hard rule:** test inputs and outputs are FASTQ/BAM/CRAM/VCF files. Diagnose from
`.command.err`, exit codes, file sizes, and `samtools`/`bcftools` metadata commands — never read
record content into your context, and never paste it into a snapshot review.

## Verification

- The test actually fails when the code is wrong (sanity-check a new test at least once).
- Snapshot file committed alongside the code change.
- `nf-core modules lint <name>` also passes — lint checks test presence and structure.
