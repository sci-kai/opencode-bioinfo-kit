---
name: nf-core-institutional-profile
description: 'Write, test, or fix an institutional Nextflow config profile (nf-core/configs style) for an HPC cluster: file structure, executor/scheduler settings, container and module setup, documentation, and testing. Use when configuring pipelines for a specific compute environment.'
argument-hint: 'Cluster/profile name and its scheduler and container engine'
user-invocable: true
---

# Institutional Config Profiles

**Canonical guides:** <https://nf-co.re/docs/developing/institutional-profiles/overview>,
`.../configuration`, `.../file-structure`, `.../testing`, `.../troubleshooting`, and
`.../outside-nf-core` for profiles that stay in-house.

Read the relevant page before writing the config — cluster profiles are shared infrastructure
and a wrong resource limit affects everyone using it.

## Gather first

Do not guess any of these; ask the user or read the cluster documentation:

- scheduler/executor (`slurm`, `sge`, `lsf`, …) and the queue/partition names with their time and memory limits
- container engine available (`singularity`/`apptainer`, `docker`, `conda`) and whether the compute nodes have internet access
- shared cache locations for container images and conda environments
- scratch/work filesystem path and any quota
- maximum CPUs/memory/time a single job may request

## Typical structure

```groovy
params {
    config_profile_description = '<Cluster> cluster profile provided by nf-core/configs.'
    config_profile_contact     = '<name> (<@github-handle>)'
    config_profile_url         = '<cluster docs url>'
    max_memory                 = <N>.GB
    max_cpus                   = <N>
    max_time                   = <N>.h
}

process {
    executor      = 'slurm'
    queue         = '<partition>'
    maxRetries    = 2
}

singularity {
    enabled    = true
    autoMounts = true
    cacheDir   = '<shared cache path>'
}
```

Add `cleanup`, `scratch`, and executor throttling (`executor.queueSize`,
`executor.submitRateLimit`) where the cluster requires them.

## Strict syntax

New and updated configs must be strict-syntax compliant — see `nf-core-migrate-strict-syntax`.
No bare variables, no functions, no `if` statements, no `switch`; use params, ternaries,
`.call()` closures, and `System.getenv()`.

## Documentation

An institutional profile needs a matching documentation page describing prerequisites (module
loads, cache setup, required environment variables), a working example command, and known
limitations. Undocumented profiles are unusable by anyone but their author.

## Testing

1. Syntax: `nextflow config -profile <name>` and inspect the resolved values.
2. Real run: execute an nf-core pipeline's test profile on the cluster —
   `nextflow run nf-core/<pipeline> -profile test,<name> --outdir <scratch-outdir>`.
3. Confirm jobs actually reach the scheduler with the intended resources (`squeue`/`sacct` or the equivalent), not just that the pipeline started.

## Verification

- Resolved config matches intent: diff `nextflow config -profile <name>` before and after.
- A test-profile run completes on the target cluster.
- Documentation page exists and the example command is the one you actually ran.

## Notes

- Offline/air-gapped clusters need pre-staged container images and conda environments; the CUBI hints knowledge base (`~/.config/opencode/cubi-kb/hints-kb-agents-instructions.md`) documents the offline conda setup — check it before improvising.
- For a CUBI-internal profile that will not be contributed to nf-core/configs, follow the same structure anyway and read the "nf-core/configs outside nf-core" page for how to load it.
