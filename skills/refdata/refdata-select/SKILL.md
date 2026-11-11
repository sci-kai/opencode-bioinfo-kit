---
name: refdata-select
description: 'Choose the public reference sample (SEQC2 HCC1395/HCC1395BL, GIAB HG001-HG007, GIAB HG008), truth set version, reference build and test tier (T0/T1/T2, test/test_full/test_full_offline) for testing a workflow or tool. Use before preparing any reference test data or benchmark.'
---

# Select a reference dataset and test tier

Purpose: one decision record that names sample, data type, truth set, build, tier, size,
location and citation before anything is downloaded.

Use when a workflow/tool needs real data with a known answer. Not for synthetic edge cases
(T0, see `test-design`) or for patient data.

## Steps

1. **Read the project.** CLAUDE.md/AGENTS.md, `docs/testing.md`, `conf/test*.config`. Note the
   existing tiers, the input type (FASTQ, BAM, VCF), germline or somatic, WGS/WES/panel and
   the reference the pipeline uses (`--fasta`, `--genome`).
2. **Pick the sample** with this table:

   | Question | Dataset | Truth |
   |---|---|---|
   | Somatic SNV/indel, tumor/normal, WGS and/or WES, VCF or BAM input | SEQC2 HCC1395/HCC1395BL | SEQC2 v1.2.1 + `High-Confidence_Regions_v1.2.bed` |
   | Germline small variants (any platform) | GIAB HG002 (or HG001-HG007) | NISTv4.2.1, or HG002 v5.0q |
   | Germline SVs | GIAB HG002 | v5.0q `stvar` (GRCh38) |
   | Somatic, cross-platform WGS incl. long reads | GIAB HG008 | draft smvar V0.4 / SV-CNV V0.6 (verify latest) |
   | Somatic, WES/panel | SEQC2 only (HG008 has no WES) | SEQC2 v1.2.1 |
   | Annotation/reporting of somatic VCFs | SEQC2 MuTect2 VCF (WES IL_1) | none needed |

3. **Pick the build** and keep it for every file:
   - SEQC2: `GRCh38.d1.vd1` (GDC; `chr` names, decoys, HPV/viral contigs; 2,779 contigs).
   - GIAB GRCh38: `GRCh38_GIABv3_no_alt_analysis_set_maskedGRC_decoys_MAP2K3_KMT2C_KCNJ18.fasta.gz`
     (`ReferenceSamples/giab/release/references/GRCh38/`). Primary contigs equal GRCh38 but
     the contig sets differ; do not mix FASTA and truth from different sets.
   - GIAB GRCh37: no `chr`, `MT`. CHM13v2.0: only v5.0q, HG008 drafts, stratifications.
4. **Pick the tier**:

   | Tier | Data | Runs on | Example |
   |---|---|---|---|
   | T0 | synthetic | anywhere | `-profile test` in variantcomp |
   | T1 / `test` | one pair, one contig (chr21/chr22), BAM slices, <= ~150 MB | laptop, Pi, CI | `variantcomp_small.yaml`, remote chr21 |
   | T2 / `test_full` | one full sample (e.g. IL_1) | HPC or online | `*_test_full.yaml` |
   | `test_full_offline` | 1..all pairs, prepared beforehand | offline HPC | `*_offline.yaml` + `--pairs` |

5. **Pick the minimum selection** (SEQC2): one replicate per center (`replicates: [1]`);
   replicates of a center share DNA, kit and sequencer. Several centers show technical
   variability. One aligner/caller (bwa + muTect2) unless the tool compares callers.
   BAMs only if the tool reads alignments.
6. **Check field needs**: MuTect2 (GATK 3.8) has AD, AF but no FORMAT/DP (add with
   `vcf.format_dp`); Strelka only AU/CU/GU/TU tier counts; SomaticSniper DP4/BCOUNT.
7. **Estimate size**: `seqc2 plan <config>`; GIAB: `curl -sI <url>` for Content-Length.
   Full GRCh38.d1.vd1 FASTA is 3.2 GB; one SEQC2 BAM 10-160 GB.
8. **Write the decision** into the project's `docs/testing.md`: dataset, version, build,
   tier, size, location, citation, date checked.

## Checks before finishing

- Build of FASTA, truth VCF, regions BED and query are the same.
- The truth set covers the variant type and regions the tool calls (WES: truth ∩ targets).
- Licence/citation noted (see below).

## Citations and licences

- SEQC2: Fang et al. 2021 Nat Biotechnol 39:1151 (doi:10.1038/s41587-021-00993-6); Xiao
  et al. 2021 Nat Biotechnol 39:1141 (doi:10.1038/s41587-021-00994-5). Public NCBI data.
- GIAB: NIST data policy (<https://www.nist.gov/open/license>): acknowledge NIST, mark changes.
  Benchmark papers: Wagner et al. 2022 (v4.2.1); Dwarshuis et al. 2024 Nat Commun 15:9029
  (stratifications); HG008: Sci Data 2025 doi:10.1038/s41597-025-05438-2.
- nf-core/test-datasets (chr21 FASTA): MIT.

## Pitfalls

- Using HG008 for WES: no WES data exist.
- Comparing against SEQC2 truth outside the HC regions inflates false positives.
- SEQC2 is one cell-line pair: center/replicate pairs are pseudo-samples, not patients.
- HG008 is a draft benchmark: report it as such.
