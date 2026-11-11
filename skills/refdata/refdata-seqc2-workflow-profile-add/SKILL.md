---
name: refdata-seqc2-workflow-profile-add
description: 'Add a seqc2-toolkit workflow profile (YAML) that turns a SEQC2 dataset into the samplesheet, params.yaml/params.config and extra files of a new workflow, with accepts/requires checks, local and remote variants and a pytest. Use when a new pipeline should be tested on SEQC2 data via seqc2 samplesheet/run.'
---

# Add a seqc2-toolkit workflow profile

Purpose: everything workflow-specific stays in one profile; the toolkit stays generic.

Use when a pipeline needs SEQC2 inputs. Not for pipeline code (`nextflow`/`nf-core-*`).

## Steps

1. **Read the pipeline's input contract**: `assets/schema_input.json` (columns, required,
   patterns), `nextflow_schema.json` (params), which FORMAT fields it reads (AD, AF, DP),
   whether it needs bgzip+index, sample order, BAMs, target BED.
2. **Check the toolkit version** (`seqc2 --version`, branch): `params_remote`,
   `files_remote`, `params.config` and `--config-base` may be branch-only.
3. **Write the profile** (`src/seqc2_toolkit/profiles/<name>.yaml` to ship it, or any path
   passed with `--profile path.yaml`):

   ```yaml
   name: mypipeline
   description: one line for 'seqc2 profiles'
   pipeline: <org>/<repo>          # nextflow run target (or --pipeline)
   revision: dev                   # -r (or --revision)
   nf_profile: conda               # -profile (or --nf-profile)
   accepts: {callers: [muTect2], technologies: [WGS, WES]}  # fields the pipeline needs
   requires: [vcf, reference]      # dataset content needed
   paths: relative                 # relative: folder can be moved/committed; absolute
   samplesheet:
     file: samplesheet.csv         # follow the pipeline's format (CUBI default .tsv)
     rows: vcf                     # vcf: per VCF | pair: per pair x technology | bam: per BAM
     missing: n/a
     columns:
       sample: "SEQC2_{pair}_{tech}"
       vcf: "{vcf}"
       tumor_bam: "{tumor_bam}"
   params:
     input: "{samplesheet}"
     fasta: "{reference}"
     truth_vcf: "{truth_snv}"
   params_remote:                  # replaces params for access: remote; null drops one
     recompress_vcf: true
   files:                          # extra files: relative path -> template text
     known.csv: |
       name,variants,regions
       seqc2_truth,{truth_snv};{truth_indel},{truth_regions}
   files_remote: {known.csv: null}
   ```

   Variables: per row `pair, center, replicate, technology, tech, library_type, aligner,
   caller, vcf, tumor_bam, tumor_bai, normal_bam, normal_bai, tumor_id, normal_id,
   target_bed` (rows bam: `role, bam, bai`); per dataset `dataset, dataset_dir, workdir,
   samplesheet, pairs, first_pair, all_bams, access, contigs, reference, reference_fai,
   target_bed_wes, truth_snv, truth_indel, truth_regions, gencode_gtf, giab_<name>`.
   An empty variable gives `missing` in a column, drops a param, and is an error in a file.
   Check the list in the toolkit README of the version in use.
4. **Render and inspect**: `seqc2 samplesheet <dataset.yaml> --profile <name> --outdir <dir>`;
   read the generated samplesheet/params (they hold paths, not genomic records).
5. **Dry run**: `seqc2 run <dataset.yaml> --profile <name> --pipeline <path> --dry-run`, then a
   real run on a T1 dataset; extra nextflow args after `--`.
6. **Test**: add a case to `tests/test_profiles.py` (renders with a fake `dataset.json`,
   checks columns, `accepts`/`requires` errors, remote variant); `pytest`, `black`, `ruff`.
7. **Pipeline side** (hand to `nextflow`/`nf-core-testing`): `conf/test*.config` with
   `includeConfig '../assets/seqc2/test/params.config'` or `--pipelines_testdata_base_path`.
8. Document the profile in the toolkit README and CHANGELOG.

## Checks before finishing

- `seqc2 profiles` lists it; shipped profile loads in `test_shipped_profiles_load`.
- Samplesheet validates against the pipeline schema (nf-schema run or `-stub`).
- Remote and local variants both render, or `accepts` excludes the unsupported one.

## Pitfalls

- MuTect2 3.8 VCFs: no FORMAT/DP, AF can be `nan`; pipelines reading DP need
  `vcf.format_dp: true` in the dataset; position-indexed sample filters need `sample_order`.
- Remote VCFs are plain gzip with all contigs: pipeline must recompress and filter.
- Strelka/SomaticSniper lack AD/AF: restrict `accepts.callers` instead of failing later.
- Do not add workflow-specific code to the toolkit; extend the template variables only when
  generic.
