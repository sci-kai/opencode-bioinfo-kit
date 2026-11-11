---
name: refdata-seqc2-dataset-prepare
description: 'Download and build a SEQC2 (HCC1395/HCC1395BL) dataset folder with seqc2-toolkit: dataset config, seqc2 plan/fetch/verify, md5-checked cache, VCF/BAM/reference/truth/GENCODE/GIAB stratification files. Use when a workflow test needs SEQC2 data on disk or as remote URLs.'
---

# Prepare a SEQC2 dataset with seqc2-toolkit

Purpose: a reproducible, md5-checked SEQC2 dataset folder (or a remote dataset description)
from a small YAML config.

Use for SEQC2 somatic data. Not for GIAB (the toolkit has none: see `refdata-benchmark-germline-giab`,
`refdata-benchmark-somatic-hg008`). For CI-sized slices continue with `refdata-seqc2-downsample-testset`.

## Steps

1. **Check the toolkit version.** `git -C <seqc2-toolkit checkout> branch`,
   `seqc2 --version`, `seqc2 --help`. Options such as `access: remote`, `--pairs/--centers/
   --technologies/--replicates`, the `vcf:` section, `data.reference_plain` and
   `params.config` may exist only on a feature branch (at writing: `feat-remote-access`).
2. **Environment.** `conda env create -f envs/seqc2-toolkit.yaml` (python, samtools,
   bcftools, htslib, nextflow; installs the package with pip -e). Activate it.
3. **Write the config** (`datasets/<workflow>_<tier>.yaml`); everything left out is default
   (WGS IL_1, bwa + muTect2, VCF, reference, truth v1.2.1, genome-wide):

   ```yaml
   access: local              # remote: nothing downloaded, samplesheet holds URLs
   select:
     technologies: [WGS, WES] # NS centers: WGS only
     pairs: [IL_1]            # or centers: [IL, FD, NV] + replicates: [1]
     aligners: [bwa]          # bwa | bowtie | novo
     callers: [muTect2]       # muTect2 | strelka | somaticSniper
   data:
     vcf: true
     bam: false               # true / list of pairs; 10-160 GB each unless sliced
     reference: true          # GRCh38.d1.vd1, 3.2 GB (or only subset.contigs)
     target_bed: true         # WES: Agilent S07604624 v6+UTR, written as merged BED3
     truth: v1.2.1            # v1.2.1 | v1.2 | false
     gencode: false           # e.g. 46
     giab: []                 # homopolymer, tandem_repeat, segmental_duplication,
                              # low_mappability, all_difficult (GIAB stratifications v3.5)
   vcf:
     sample_order: null       # e.g. [NORMAL, TUMOR] for tools indexing samples by position
     format_dp: false         # add FORMAT/DP = sum(AD): MuTect2 3.8 records have none
   ```

4. **Disk.** follow "Large data" in the global rules (mount check if `<SCRATCH_DIR>` is on a removable disk) and, if available, `export SEQC2_CACHE=<SCRATCH_DIR>/cache/seqc2`
   and `--outdir <SCRATCH_DIR>/data/seqc2/<name>`. No scratch folder or not mounted: stop for anything above a
   few hundred MB and report `df -h /`.
5. **Plan.** `seqc2 catalog` (what the server has), then `seqc2 plan <config>`: files, sizes,
   cache state, total to download. Report the size before fetching.
6. **Fetch.** `seqc2 fetch <config> --outdir <dir> [--pairs IL_1,FD_1,NV_1]`. It downloads
   only missing files (resumable), checks md5 against the server lists (VCF, BAM, BAI, GIAB),
   builds bgzipped/indexed VCFs, subsets, BAM slices, and writes `dataset.json`,
   `checksums.md5`, `README.md`, `seqc2_manifest.json`. Re-running rebuilds only changed
   recipes and removes deselected outputs.
7. **Verify.** `seqc2 verify <config> --outdir <dir>` (exit 1 on a changed/missing file).
   Header checks only: `bcftools view -h <vcf> | grep -c '^##contig'`, `bcftools query -l <vcf>`
   (expect `TUMOR`, `NORMAL`), `samtools quickcheck bam/*.bam`.
8. **Use the same selection options** for `fetch` and `samplesheet`; `samplesheet` stops if
   the folder was built with another selection.

## Layout produced

```
reference/GRCh38.d1.vd1[_<contigs>].fa[.gz] (+ .fai, .gzi)
bed/S07604624_Covered_human_all_v6_plus_UTR_hg38.bed
vcf/<pair>_<technology>.<aligner>.<caller>.vcf.gz (+ .tbi)
bam/<pair>_<tech>_<T|N>.bam (+ .bai), bam/bam_regions.bed
truth/high-confidence_sSNV|sINDEL_in_HC_regions_v1.2.1.vcf.gz, High-Confidence_Regions_v1.2.bed
annotation/gencode.v<rel>.basic.annotation.gtf.gz, annotation/giab/GRCh38/<release path>
dataset.json, checksums.md5, README.md, seqc2_manifest.json
```

(Check the exact BAM file names in the built folder; they have differed from the README.)

## Checks before finishing

- `seqc2 verify` clean; size of the folder reported (`du -sh`).
- The reference, truth, target BED and GENCODE files have **no upstream md5** (only recorded
  in the cache registry); say so in the provenance note.
- Citation (Fang 2021, Xiao 2021) in the dataset README.

## Pitfalls

- HTTPS errors (`curl: (77)`) with conda curl: the toolkit uses Python downloads; pass
  `--ca-bundle` or set `SSL_CERT_FILE` if needed.
- `access: remote`: VCFs are plain gzip, not indexed, and contain all contigs; the workflow
  must filter to `{contigs}` and accept plain gzip; BAM slices are not possible.
- Mixing WES-only and WGS-only center selections (NS has no WES) stops with an error.
