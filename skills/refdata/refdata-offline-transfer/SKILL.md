---
name: refdata-offline-transfer
description: 'Prepare SEQC2/GIAB reference test data on a machine with internet and move it to an offline HPC: seqc2 fetch, checksums, relocatable samplesheets/params (config-base, pipelines_testdata_base_path), test_full_offline profile, transfer bundle and verification after the copy. Use when a test or benchmark must run without internet.'
---

# Move reference test data to an offline HPC

Purpose: the same md5-checked data and inputs on the HPC as on the preparing machine, with
no download during the run.

Use for `test_full_offline` / T2 runs and benchmarks on a cluster without internet. Not for
container images and pipeline code (hand to `nf-core-release`: `nf-core pipelines download`).

## Steps

1. **Choose the selection** (`refdata-select`): pairs, technologies, truth, annotation.
   SEQC2 config example `datasets/<workflow>_offline.yaml` with `access: local`.
2. **Disk on the preparing machine**: follow "Large data" in the global rules (mount check if `<SCRATCH_DIR>` is on a removable disk); `seqc2 plan <config>
   --pairs ...` for the total; `SEQC2_CACHE=<SCRATCH_DIR>/cache/seqc2`, dataset in
   `<SCRATCH_DIR>/data/seqc2/<name>/`.
3. **Fetch and verify**: `seqc2 fetch <config> --outdir <dir> --pairs IL_1,FD_1,NV_1`, then
   `seqc2 verify`. GIAB files: download plus `md5sum -c` against the published list.
4. **Write relocatable inputs**:
   - `seqc2 samplesheet <config> --outdir <dir> --pairs ... --profile <p>` with a profile
     using `paths: relative`, or
   - `--config-base '${params.pipelines_testdata_base_path}<name>'` so `params.config` resolves
     paths on the HPC (check the toolkit version supports it), or
   - run `seqc2 samplesheet` again on the HPC (absolute paths; the toolkit needs no network
     for a local dataset once the catalog is cached; verify with the version in use).
5. **Bundle**: the dataset folder (incl. `checksums.md5`, `README.md`, `dataset.json`),
   GIAB files with their md5 list, VEP cache or other resources the pipeline needs, and a
   short `RUN.md` with the exact commands. Do not include the toolkit cache.
   `tar -cf <name>_<YYYYMMDD>.tar <dir>`; write `sha256sum` of the tar.
6. **Transfer** (user does it if credentials are needed): `rsync -av --partial` or the tar.
7. **Verify on the HPC**: `sha256sum -c`, then `cd <dir> && md5sum -c checksums.md5` (or
   `seqc2 verify` if the toolkit is installed there).
8. **Run** (example):
   `nextflow run <pipeline> -profile test_full_offline,singularity --pipelines_testdata_base_path <dir>/ --outdir <out>`
   with offline containers (`NXF_OFFLINE=true`, Singularity cache from `nf-core pipelines download`).
9. **Bring results back**: summary tables and MultiQC report only; record pipeline version,
   dataset config, toolkit commit and truth version.

## Checks before finishing

- No path in samplesheet/params points to the preparing machine (`grep -n <SCRATCH_DIR>` and
  home paths in the generated files).
- Every file in the bundle is covered by a checksum.
- `RUN.md` lists resources the bundle does not contain (VEP cache, containers).

## Pitfalls

- `access: remote` datasets read URLs at run time: never use them offline.
- `samplesheet` refuses a folder built with another selection: use the same `--pairs` etc.
- Whole files are hard-linked from the cache, or symlinked when the cache is on another file
  system: check with `find <dir> -type l`; use `tar -h`/`rsync -L` or the bundle holds
  dangling links.
- Hard-coded HPC paths in the pipeline repo break CUBI rules: pass them as params.
