---
name: refdata-benchmark-germline-giab
description: 'Benchmark germline small variants (and SVs) against GIAB HG001-HG007 (NISTv4.2.1) or HG002 v5.0q with hap.py + vcfeval engine and GIAB genome stratifications (v3.5/v3.6), truvari for SVs; includes downloads, md5, reference choice and WES restriction. Use when validating a germline caller or pipeline on GIAB samples.'
---

# Benchmark germline calls against GIAB

Purpose: GA4GH-style recall/precision/F1 per variant type and genome context.

Use for germline calls on GIAB samples. Not for somatic (`refdata-benchmark-somatic-seqc2`,
`refdata-benchmark-somatic-hg008`). seqc2-toolkit has no GIAB germline support: download directly.

## Facts (verify versions on the FTP before use)

- Base: `https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/`
  - `NA12878_HG001/`, `AshkenazimTrio/HG002_NA24385_son/` (+ HG003, HG004),
    `ChineseTrio/` (HG005-HG007), `genome-stratifications/`, `references/`.
- Small variants: `NISTv4.2.1/GRCh38/HG00x_GRCh38_1_22_v4.2.1_benchmark.vcf.gz` +
  `..._benchmark_noinconsistent.bed` or `..._benchmark.bed` (check names in the folder).
- HG002 v5.0q (Q100 assembly-based): `v5.0q/HG002_GRCh38_v5.0q_smvar.vcf.gz` +
  `.benchmark.bed`; `..._stvar.*` for SVs; also GRCh37 and CHM13v2.0; `checksum.md5`.
  Other HG002 sets: CMRG_v1.00 (medically relevant genes), TandemRepeats_v1.0, chrXY_v1.0.
- Stratifications: `genome-stratifications/v3.6/GRCh38@all/` (v3.5 used in the original
  projects); md5 list `GRCh38-genome-stratifications-md5s.txt`; a TSV index of all BEDs for
  hap.py ships in the folder (verify name).
- Reference: `references/GRCh38/GRCh38_GIABv3_no_alt_analysis_set_maskedGRC_decoys_MAP2K3_KMT2C_KCNJ18.fasta.gz`.
  GRCh37: no `chr` prefix.
- Raw reads (FASTQ/BAM) per platform under `ReferenceSamples/giab/data/` (verify).

## Steps

1. **Disk and size**: follow "Large data" in the global rules (mount check if `<SCRATCH_DIR>` is on a removable disk); data to `<SCRATCH_DIR>/data/giab/<sample>/<version>/`.
   Check sizes with `curl -sI`. Stratification tarball about 1.3 GB; per-file download is smaller.
2. **Download** VCF, `.tbi`, BED, README, md5 list; `md5sum -c` against the published list;
   write a `README.md` with URLs, version, date, md5.
3. **Reference check**: query called on the same build; compare `##contig` lines with the
   `.fai`; fix only `chr` naming (`bcftools annotate --rename-chrs`), never lengths.
4. **Regions**: benchmark BED; WES/panel: `bedtools intersect -a benchmark.bed -b targets.bed`
   (targets padded as the caller used them). Report the region size.
5. **Run hap.py** (container or conda `hap.py`; verify flags with `hap.py --help`):

   ```bash
   rtg format -o ref.sdf ref.fa
   hap.py truth.vcf.gz query.vcf.gz -f regions.bed -r ref.fa -o out/HG002 \
       --engine vcfeval --engine-vcfeval-template ref.sdf \
       --stratification strat.tsv --pass-only --threads 4
   ```

   `strat.tsv`: `name<TAB>path` per stratification BED (absolute or relative to the TSV).
6. **SVs**: `truvari bench -b HG002_GRCh38_v5.0q_stvar.vcf.gz -c query_sv.vcf.gz
   --includebed HG002_GRCh38_v5.0q_stvar.benchmark.bed -o out/truvari --passonly`
   (add `truvari refine` for complex regions; verify version-specific options).
7. **Report** from `*.summary.csv` / `*.extended.csv`: SNP/INDEL x ALL/PASS, recall,
   precision, F1, per stratification (all_difficult, low mappability, homopolymers, segdups,
   tandem repeats), tool versions, truth version, regions.

## Checks before finishing

- METRIC.Recall/Precision for the `*` (whole region) row match the summary.
- Truth and query sample are the same individual (HG002 query vs HG002 truth).
- Number of truth variants inside regions is plausible (non-zero for WES).

## Pitfalls

- Mixing GRCh38.d1.vd1 (SEQC2/GDC) FASTA with GIAB no-alt truth: works for primary contigs
  only; keep one reference per run.
- v4.2.1 excludes difficult regions that v5.0q includes: v5.0q recall is lower by design.
- hap.py without vcfeval engine mis-matches complex representations.
- Never benchmark outside the benchmark BED.
