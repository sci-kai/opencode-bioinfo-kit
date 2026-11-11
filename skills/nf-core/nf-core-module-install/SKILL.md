---
name: nf-core-module-install
description: 'Install an nf-core module or subworkflow into a pipeline with `nf-core modules install` / `nf-core subworkflows install`, including checking whether it already exists and verifying modules.json. Use when adding an existing nf-core component to this pipeline.'
argument-hint: 'Component name, e.g. `fastqc`, `samtools/sort`, or subworkflow `bam_stats_samtools`'
user-invocable: true
---

# nf-core Component Install

**Canonical guide:** <https://nf-co.re/docs/developing/pipelines/adding-modules>

Installing is only half the job — wiring the component into the pipeline is
`nf-core-module-wire-in`. Run that next unless the user asked for the install alone.

## Preconditions

- Run from the pipeline repository root (where `nextflow.config` and `modules.json` live).
- Conda environment providing `nf-core` is active.
- Never copy component files in by hand from another repository — the CLI writes `modules.json` bookkeeping that hand-copying silently omits.

## Procedure

1. Check whether the component already exists before installing anything:
   - `nf-core modules list local` and `grep -n "<name>" modules.json`
   - `ls modules/nf-core/<tool>/<subtool>`
   - If present, stop and report that instead of reinstalling.
2. Confirm the component exists upstream and get its exact path:
   - `nf-core modules list remote | grep -i <tool>`
   - `nf-core subworkflows list remote | grep -i <name>` for subworkflows.
3. If it does **not** exist upstream, do not hand-write it here: switch to `nf-core-module-create`, and confirm with the user whether it should be a local module (`modules/local/`) or contributed upstream.
4. Install:
   - `nf-core modules install <tool>/<subtool>`
   - `nf-core subworkflows install <name>`
   - For a non-nf-core remote, see `nf-core-custom-remote` (`--git-remote`, `--branch`).
5. Note the `include` statement the CLI prints — it is the exact syntax to paste into the workflow.

## Verification

- `modules/nf-core/<tool>/<subtool>/` exists with `main.nf`, `meta.yml`, `environment.yml`, and `tests/`.
- `modules.json` has a new entry with a pinned `git_sha`.
- `git status` shows no unintended changes to other components — in particular, no previously patched module was overwritten.
- `nf-core modules lint <tool>/<subtool>` is clean.

## Notes

- If this repository carries `.diff` patch files for vendored modules, an install/update can clobber them; check `modules/nf-core/<tool>/<subtool>/*.diff` and re-apply with `nf-core modules patch` rather than editing files directly.
- Commit the install as its own small commit (`Install <tool> module`) before wiring it in, so the vendored code and your integration stay separable.
