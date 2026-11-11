---
name: refdata-benchmark-somatic-seqc2
description: 'Measure somatic SNV/indel recall and precision of a caller or pipeline against the SEQC2 HCC1395 truth set (v1.2.1, High-Confidence_Regions_v1.2.bed) with som.py or rtg vcfeval, restricted to confident regions and targets, stratified by GIAB regions and VAF. Use when validating somatic calls on SEQC2 data.'
---

# Benchmark somatic calls against the SEQC2 truth set

Purpose: recall/precision per technology and variant type that can be compared with
published SEQC2 numbers.

Use for SEQC2 HCC1395/HCC1395BL calls on GRCh38.d1.vd1. Not for HG008 (`refdata-benchmark-somatic-hg008`)
or germline (`refdata-benchmark-germline-giab`).

## Inputs

- Truth (verify the latest release on the FTP first): `release/v1.2.1/`
  `high-confidence_sSNV_in_HC_regions_v1.2.1.vcf.gz`, `high-confidence_sINDEL_in_HC_regions_v1.2.1.vcf.gz`,
  `High-Confidence_Regions_v1.2.bed` under
  `https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/seqc/Somatic_Mutation_WG/`.
  v1.2.1 = v1.2 calls intersected with the HC regions (v1.2 left 113 SNVs and 297 indels in
  excluded pads). Superset files (`sSNV.MSDUKT.superSet.v1.2.vcf.gz`) hold lower-confidence
  calls: useful to classify FPs, not as truth.
- Size (verify by counting): about 39,500 SNVs and 2,000 indels (secondary source).
- Reference: `GRCh38.d1.vd1.fa` (+ `.fai`; rtg needs `rtg format -o ref.sdf`).
- Query: tumor/normal VCF of the same reference. WES: target BED (merged BED3).

## Steps

1. **Fetch truth** with the toolkit (`data.truth: v1.2.1`, see `refdata-seqc2-dataset-prepare`) or
   download plus a recorded checksum (no upstream md5 for truth files: record sha256).
2. **Check consistency**: contig names/lengths of query header vs `.fai`
   (`bcftools view -h q.vcf.gz | grep '^##contig'`), `bcftools query -l` for sample names.
3. **Normalise query and truth** the same way:
   `bcftools norm -m -any -f ref.fa -Oz -o q.norm.vcf.gz q.vcf.gz && bcftools index -t q.norm.vcf.gz`.
   Keep PASS only for the main numbers (`bcftools view -f PASS`); report all-calls separately.
4. **Regions**: `regions = HC_regions ∩ targets` for WES (`bedtools intersect` or
   `bcftools`-friendly merged BED). For cross-technology comparisons use the intersection of
   all targets.
5. **Run one tool, record its version**:
   - som.py (hap.py package, verify flags with `som.py --help`):
     `som.py truth_snv_indel.vcf.gz q.norm.vcf.gz -r ref.fa -f HC.bed -R targets.bed -o out/somc --normalize-all`
     (`-f` = confident regions: FPs counted only inside; `-R` restricts everything).
   - rtg vcfeval (sample names via `bcftools query -l`; verify `--sample` syntax):
     `rtg vcfeval -b truth.vcf.gz -c q.norm.vcf.gz -t ref.sdf --bed-regions regions.bed --squash-ploidy --sample ALT,TUMOR -o out/vcfeval`
     (`--squash-ploidy` because somatic GTs are not diploid genotypes; `ALT` for a
     sample-less truth VCF).
   - Concatenate SNV + indel truth (`bcftools concat -a`) or run them separately; report
     SNV and indel separately either way.
6. **Stratify**: GIAB stratifications v3.5/v3.6 GRCh38 (homopolymers, tandem repeats,
   segdups, low mappability, all difficult) via `bcftools view -R` on TP/FP/FN outputs, and
   VAF bins (<5 %, 5-10 %, 10-20 %, >20 %) of query FORMAT/AF or AD.
7. **Write a TSV**: technology, pair, caller, type, regions, TP, FP, FN, recall, precision, F1,
   tool+version, truth version, date.

## Checks before finishing

- Recall/precision of a WGS bwa+MuTect2 run is in the range published by Fang/Xiao 2021
  (verify against the paper); far off means a build, region or normalisation error.
- The numbers state the region set; no FP counted outside HC regions.
- Counts summed over strata equal the totals.

## Pitfalls

- MuTect2 (GATK 3.8) VCFs: no FORMAT/DP, AD 0,0 and AF=`nan` occur: compute VAF from AD and
  count undefined VAF separately.
- Strelka/SomaticSniper lack AF/AD: VAF strata need tier counts or DP4.
- Low-VAF and subclonal calls: separate DNA aliquots differ; low-VAF discordance is not
  automatically a caller error.
- AmpliSeq-panel truth is biased (designed on candidate calls) and over-estimates recall.
- Some SEQC2 VCFs are plain gzip: recompress (`bcftools view -Oz`) before indexing.
- Different callers per technology mix sequencing and caller effects.
