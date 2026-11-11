---
name: nf-core-meta-map
description: 'Design and handle nf-core meta maps correctly: channel tuple shape, meta.id and meta.single_end, propagating and joining metadata, and why custom keys belong in ext.args. Use when writing module inputs/outputs, building input channels from a samplesheet, or debugging channel-shape mismatches.'
argument-hint: 'Optional: the module or channel in question'
user-invocable: true
---

# Meta Maps

**Canonical guide:** <https://nf-co.re/docs/developing/components/meta-map>

## Shape

A meta map is a Groovy map travelling in a tuple next to the file(s) it describes:

```groovy
[ [id: 'test', single_end: false], sample1_R1.fastq.gz ]
```

Modules declare it as the first tuple element:

```groovy
input:
tuple val(meta), path(reads)
```

and use it for tagging and naming:

```groovy
tag "${meta.id}"
def prefix = task.ext.prefix ?: "${meta.id}"
```

## Standard keys

Only two are standardised across nf-core:

| Key | Meaning |
|---|---|
| `meta.id` | Unique identifier for the file group (typically the sample name) |
| `meta.single_end` | Sequencing library layout, for pipelines handling paired-end data |

There are no other required key names. Pipelines may carry additional keys (`strandedness`,
`lane`, `patient`, …), but a **published module must not depend on them**.

## The rule that keeps modules reusable

Any module behaviour that depends on a non-standard meta key must be routed through
`ext.args` in the pipeline's `conf/modules.config`, not read from `meta` inside the module:

```groovy
withName: 'TOOL_SUBTOOL' {
    ext.args   = { meta.strandedness == 'reverse' ? '--reverse' : '' }
    ext.prefix = { "${meta.id}.sorted" }
}
```

The closure is evaluated per task with `meta` in scope, so the pipeline supplies the logic and
the module stays generic.

## Practical guidance

- Build meta maps once, where the samplesheet is parsed, and propagate them — do not reconstruct them mid-pipeline.
- `meta.id` must be unique across the run; when merging per-lane into per-sample, derive a new `id` explicitly and keep the mapping traceable.
- Join channels on the meta map (or on `meta.id`), never on emission order — order is not guaranteed.
- When a module changes tuple cardinality, every caller must change with it in the same commit.

## Debugging channel-shape mismatches

Add a temporary `.view()` at the failing point, run the test profile, read the printed tuple
shape, then remove the instrumentation. Do not leave `.view()` calls in committed code.

**Privacy hard rule:** `.view()` on a channel prints file *paths* and metadata, which is fine —
never print or read file *contents* for FASTQ/BAM/CRAM/VCF, and be careful that sample
identifiers in metadata are not personally identifying.
