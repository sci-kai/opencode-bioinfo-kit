---
name: nf-core-migrate-strict-syntax
description: 'Make Nextflow config and pipeline code compliant with strict syntax (default from Nextflow 26.04): replacing bare variables, functions, if-statements, switch statements, and env access. Use when strict-syntax warnings appear or before adopting Nextflow 26.04+.'
argument-hint: 'Config file or pipeline to migrate'
user-invocable: true
---

# Migrate to Nextflow Strict Syntax

**Canonical guide:** <https://nf-co.re/docs/developing/migration-guides/strict-syntax>

Strict syntax is enabled by default from Nextflow 26.04. It restricts what may appear in config
files, in exchange for far better error messages. Institutional/HPC config files are usually the
biggest offenders.

## Checking compliance

**Language server (preferred):** open the repository in VS Code with the Nextflow extension —
diagnostics and hover hints flag every violation.

**Command line:**

```bash
echo "workflow{}" > main.nf
NXF_VER=26.02.0-edge nextflow run main.nf -c conf/<your_config>.config
```

No warnings or errors means the config is already compliant.

## Common fixes

**Simple variables** — replace bare variable declarations with parameters:

```groovy
params.variable_name = <value>
```

Add custom parameters to the nf-schema `ignoreParams` list so validation does not warn about them.

**Dynamic variables** — a closure that is immediately called:

```groovy
params.random_var = {
    if (something == true) {
        return 'not_random'
    } else {
        return 'random'
    }
}.call()
```

The trailing `.call()` is required; without it the parameter holds a closure, not a value.

**If-statements** — Groovy ternary:

```groovy
process.executor = params.slurm ? 'slurm' : 'local'
```

**Switch statements** — rewrite as a closure-wrapped if/else chain, same `.call()` pattern.

**Environment variables** — wrap in `System.getenv()`:

```groovy
scratch = "/scratch/${System.getenv('USER')}"
```

**Functions** — there is no clean replacement (nf-schema conflicts with the available options).
Reimplement the logic inline at each call site inside a closure. If a function is called in many
places, flag the duplication to the user rather than silently fanning it out.

## Verification

- The `NXF_VER=26.02.0-edge` check above produces no warnings.
- The config still *works*: run a real pipeline with it (`-profile <your_profile>` on a test pipeline), not just the syntax check — a syntactically valid config can still resolve to the wrong values after this kind of rewrite.
- Compare resolved values before and after: `nextflow config -profile <profile>` on both revisions and diff the output.
- `nf-core pipelines lint` clean.

## Notes

- Migrate one config/profile at a time and verify each; a bulk rewrite of an institutional config is very hard to review.
- Test against a real nf-core pipeline before merging changes to a shared institutional config — other people's runs depend on it.
