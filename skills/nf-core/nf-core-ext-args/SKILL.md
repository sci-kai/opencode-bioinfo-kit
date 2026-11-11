---
name: nf-core-ext-args
description: 'Configure module behaviour through the ext.* convention (ext.args, ext.args2/3, ext.prefix, ext.when, ext.use_gpu) in conf/modules.config instead of editing module code. Use when a tool needs different flags, output names, or conditional execution.'
argument-hint: 'Module name and the flags/behaviour to configure'
user-invocable: true
---

# The `ext.*` Convention

**Canonical guide:** <https://nf-co.re/docs/developing/components/ext-args>

## Why

A module's script embeds placeholders that the pipeline fills at runtime:

```groovy
script:
def args   = task.ext.args ?: ''
def prefix = task.ext.prefix ?: "${meta.id}"
"""
tool subtool $args $bam > ${prefix}.log
"""
```

Configuring `ext.args = '-T -K'` turns that into `tool subtool -T -K test.bam > test.log`.
**Editing a vendored module to hardcode a flag is always wrong** — it breaks updates and
reusability. Configure it instead.

## Available keys

| Key | Purpose |
|---|---|
| `ext.args`, `ext.args2`, `ext.args3` | Arguments appended to the first/second/third command in the module |
| `ext.prefix`, `ext.prefix2` | Output file name prefixes |
| `ext.when` | Boolean controlling whether the process runs at all |
| `ext.use_gpu` | GPU path selection (see `nf-core-gpu-module`) |

## Where it goes

`conf/modules.config`, in a `withName:` block:

```groovy
process {
    withName: 'TOOL_SUBTOOL' {
        ext.args = '-T -K'
    }
}
```

Use the fully qualified selector (`withName: '.*:ALIGN:SAMTOOLS_SORT'`) when the same module is
invoked from more than one subworkflow and needs different settings.

## Dynamic values

`ext.*` accepts a closure evaluated per task, with `meta`, `task`, and `params` in scope:

```groovy
ext.prefix = { "${meta.id}.sorted.bam" }

ext.args = { [
    params.umitools_extract_method ? "--extract-method=${params.umitools_extract_method}" : '',
    params.umitools_bc_pattern     ? "--bc-pattern='${params.umitools_bc_pattern}'"       : ''
].minus("").join(' ') }
```

The list/`minus("")`/`join(' ')` idiom is the standard way to assemble optional flags without
leaving stray whitespace.

## Verification

`ext.args` is not validated — a typo becomes a runtime tool error, or worse, is silently
accepted. After changing it:

1. Run the test profile and read the resolved command line in `work/<hash>/.command.sh` for the affected task — confirm the flags landed as intended.
2. Check `nf-core pipelines lint` still passes.
3. If a new `params.*` backs the argument, rebuild the schema (`nf-core pipelines schema build`) and document it in `docs/usage.md`.

## Notes

- Prefer `ext.args` over new pipeline parameters for anything that is genuinely tool-expert tuning; add a `params.*` only when a typical user needs to change it.
- `ext.when = false` is the clean way to disable a module conditionally — do not comment out the call in the workflow.
