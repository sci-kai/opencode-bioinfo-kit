---
name: refdata-benchmark-somatic-hg008
description: 'Benchmark somatic SNV/indel (and SV/CNV) calls on the GIAB HG008 pancreatic tumor/normal pair against the NIST draft benchmarks (smvar V0.4, SV-CNV V0.6 at writing; verify latest) with aardvark, rtg vcfeval or hap.py; covers data location, BED choice, VAF filtering and draft-status caveats. Use when testing a somatic pipeline on HG008 WGS data.'
---

# Benchmark somatic calls against GIAB HG008 (draft)

Purpose: cross-platform somatic WGS validation with an assembly-based truth.

Use for HG008 WGS (Illumina, Element, Ultima, PacBio, ONT, ...). Not for WES/panels (no HG008
WES data) and not as a final clinical validation: the benchmark is a draft.

## Facts (verify before use; listing checked 2026-11-09)

- Samples: HG008-T (PDAC cell line, mixture of cells; passage 23 used for the benchmark),
  HG008-N-P (normal pancreas), HG008-N-D (normal duodenum). Female. ATCC CRL-3734.
- Data: `https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/data_somatic/HG008/Liss_lab/`
  (one folder per center/platform/date) and `README_HG008.md` one level up.
- Benchmarks: `.../Liss_lab/analysis/`
  - `NIST_HG008-T_somatic-smvar_DraftBenchmark_V0.4-20261006/` (also V0.3): `GRCh38/`,
    `GRCh37/`, `CHM13v2/` (GRCh37/CHM13 lifted over), `README.md`, `checksums.md5`.
    GRCh38 files: `HG008-T_somatic_smvar_benchmark_v0.4_GRCh38_tumorvariants.vcf.gz`
    (recommended), BEDs `..._GRCh38_all.bed` (default), `..._nogermlineinterference.bed`,
    `..._nogermlinewithin50bp.bed` (strictest).
  - `NIST_HG008-T_somatic-stvar-CNV_DraftBenchmark_V0.6-20261006/` for SV/CNV.
- Scope: clonal/truncal somatic SNVs and small indels only. README advises removing calls
  below about 5-10 % VAF before or after comparison.
- Licence: NIST data policy (acknowledge NIST, mark changes). Cite Sci Data 2025
  (doi:10.1038/s41597-025-05438-2) and the preprint doi:10.64898/2026.05.01.722316.

## Steps

1. **Read the current README** of the newest `DraftBenchmark` folder; note version, passage,
   file names, recommended tool and BED. Record the date.
2. **Disk**: follow "Large data" in the global rules (mount check if `<SCRATCH_DIR>` is on a removable disk); HG008 BAM/FASTQ are tens to hundreds of GB: estimate
   with `curl -sI`, prefer existing aligned BAMs or region slices
   (`samtools view -b -M -L regions.bed -X <bam-url> <bai-url>`).
3. **Download** benchmark VCF + BED + `checksums.md5`; `md5sum -c`; provenance README.
4. **Match the build**: GRCh38 benchmark with a GRCh38 reference of the same contig set as
   the calls (check `##contig` vs `.fai`).
5. **Filter the query**: PASS, somatic only, VAF >= threshold (default 0.05; also report
   0.10): `bcftools view -f PASS -i 'FORMAT/AF[<tumor_idx>:0]>=0.05'` (adapt to the caller's
   fields).
6. **Compare** (verify flags with `--help`):
   - aardvark (tested by NIST): `aardvark compare` with reference, truth VCF/sample,
     query VCF/sample, `--regions ..._GRCh38_all.bed`, output dir.
   - rtg vcfeval: `--squash-ploidy --bed-regions ..._GRCh38_all.bed`, sample via `--sample`.
   - hap.py `--engine vcfeval` works similarly per the README.
7. **Curate**: inspect a sample of FP/FN positions (counts and coordinates, IGV for reads);
   representation differences of somatic variants on top of germline variants are common.
8. **Report** recall/precision per type, BED variant, VAF threshold, platform; label
   "HG008 draft benchmark V0.x".

## Checks before finishing

- Results state benchmark version, BED, VAF threshold, platform, tool version.
- Lifted-over GRCh37/CHM13 results flagged as less reliable.

## Pitfalls

- Germline-to-reference reversions cannot appear as somatic on a linear reference.
- Centromeres and segdups are excluded where the normal assembly is not unique.
- Subclonal homopolymer indels and some subclonal SNVs are missing: FPs there may be true.
- The full multi-sample VCF holds unvalidated germline genotypes: not a germline truth.
- Different passages of HG008-T (`other_passages/`) differ in subclones.
