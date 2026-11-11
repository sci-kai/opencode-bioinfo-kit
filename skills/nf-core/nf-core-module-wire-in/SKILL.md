---
name: nf-core-module-wire-in
description: 'Wire an installed nf-core module into the pipeline end to end: include statement, channel plumbing, versions, conf/modules.config publishing and ext.args, parameters and schema, MultiQC, docs and citations. Use after installing or creating a module, or when a module is installed but not actually called.'
argument-hint: 'Module name and where it should run in the workflow'
user-invocable: true
---

# Wire a Module Into the Pipeline

**Canonical guide:** <https://nf-co.re/docs/developing/pipelines/adding-modules>
(plus <https://nf-co.re/docs/developing/components/ext-args> for `ext.args`)

A module that is installed but not called, or called but not published/documented, is an
unfinished change. Work through every step; state explicitly if one genuinely does not apply.

## Procedure

1. **Include** the module in the narrowest owning workflow or subworkflow, using the exact `include` line printed by `nf-core modules install`:
   - `include { TOOL_SUBTOOL } from '../modules/nf-core/tool/subtool/main'`
2. **Call** it where it belongs in the workflow, matching the module's declared input cardinality (check `meta.yml` inputs — do not guess the tuple shape).
3. **Versions**: mix the module's version output into the pipeline's versions channel. If this pipeline is on the topic-channel template (tools ≥ 3.5.0), versions arrive via the `versions` topic and must *not* be referenced as `TOOL_SUBTOOL.out.versions` — see `nf-core-migrate-topic-channels`.
4. **Publishing and arguments** in `conf/modules.config` — add a `withName:` block for the module setting `publishDir` (output subdirectory and file patterns) and any `ext.args`/`ext.prefix`:
   ```groovy
   withName: 'TOOL_SUBTOOL' {
       ext.args   = '-T -K'
       ext.prefix = { "${meta.id}.sorted" }
       publishDir = [ path: { "${params.outdir}/tool" }, mode: params.publish_dir_mode, pattern: "*.bam" ]
   }
   ```
   Never edit the module's `main.nf` to hardcode a flag — that is what `ext.args` exists for.
5. **Parameters**: if the module's behaviour must be user-configurable, add a `params.*` default in `nextflow.config` and reference it through a closure: `ext.args = { "--option ${params.option}" }`.
6. **Schema**: after any parameter change, regenerate — `nf-core pipelines schema build`, then `nf-core pipelines schema docs`, then `nf-core pipelines schema lint`. Never hand-edit `nextflow_schema.json`.
7. **MultiQC**: if the module emits QC-relevant output, route it into the MultiQC input channel and check whether MultiQC natively supports the format. If it does not, ask the user whether to build a custom MultiQC table/plot — do not silently leave the output unreported.
8. **Documentation** (see `nf-core-pipeline-docs`): `docs/usage.md` (new params/inputs, one realistic command), `docs/output.md` (new output paths), `CITATIONS.md` (tool citation + resolving DOI/URL), `CHANGELOG.md`, `README.md` if user-visible behaviour changed, and the methods-description text if the tool should be cited in reports.
9. **Format and lint**: `prettier -w .` (or the repo's configured formatter), then `nf-core pipelines lint`.
10. **Test**: `nf-test test` for the touched slice, then a pipeline smoke run `-profile test,<docker|singularity|conda>`.

## Verification

- The module actually appears in a `-profile test` run's process list — not just in the source.
- Outputs land under the intended `publishDir` path.
- `nf-core pipelines lint` clean, schema lint clean, nf-test passing.
- Docs, citations and CHANGELOG updated, or each explicitly justified as not applicable.

## Notes

- Privacy hard rule: test runs produce FASTQ/BAM/CRAM/VCF outputs. Verify them by existence, size, `samtools quickcheck`/`flagstat`, `bcftools stats` or header-only views — never read record content into your context.
- Keep the integration in one cohesive commit separate from the vendored module install.
