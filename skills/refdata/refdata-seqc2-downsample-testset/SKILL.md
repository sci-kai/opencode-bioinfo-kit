---
name: refdata-seqc2-downsample-testset
description: 'Build a small, committed SEQC2 test set (T1 / -profile test or test_seqc2) for CI, laptops or a Raspberry Pi: contig subset, remote BAM windows restricted to targets, fixed-seed read subsampling, truth subset, provenance and a test-data repository layout. Use when a pipeline needs real SEQC2 data under ~150 MB.'
---

# Downsample SEQC2 to a CI-sized test set

Purpose: real tumor/normal data that runs end to end in minutes, with variants inside the
slice, reproducible from a config.

Use for T1 tests. Not for full validation (T2, `refdata-seqc2-dataset-prepare`) or for edge cases
(synthetic T0 data, `test-design`).

## Steps

1. **Decide what the test must exercise**: technologies (WGS+WES), pairs (usually 1-3, e.g.
   IL_1, FD_1, NV_1 for center variability), BAM-dependent features (coverage, read evidence).
2. **Choose the contig.** chr22 (local slices, as in variantcomp T1) or chr21 (an online
   chr21 FASTA from nf-core/test-datasets exists with identical sequence, for remote tests).
3. **Choose BAM windows** where the test has signal: 1-2 windows of 1 Mb with the most PASS
   calls of the chosen pair and truth records. Count with header-free commands only:
   `bcftools view -H -f PASS -r chr22:23000000-24000000 <vcf> | wc -l`.
4. **Write the config** (example from variantcomp, about 150 MB for 3 pairs x 2 technologies):

   ```yaml
   select: {technologies: [WGS, WES], pairs: [IL_1, FD_1, NV_1],
            aligners: [bwa], callers: [muTect2]}
   data: {bam: true, gencode: 46,
          giab: [homopolymer, tandem_repeat, segmental_duplication, low_mappability, all_difficult]}
   subset:
     contigs: [chr22]
     bam_windows: ["chr22:23000000-24000000", "chr22:50000000-50818468"]
     bam_targets: true        # only WES targets + padding inside the windows
     bam_padding: 100
     bam_subsample: 0.5       # fraction of read pairs, seed 42 (fixed)
   ```

5. **Build** with `seqc2 plan`, `seqc2 fetch --outdir <testdata-repo>/seqc2/small`,
   `seqc2 verify`. BAM slices are read remotely (`samtools view -M -L regions -X bam bai`):
   no full BAM download.
6. **Write workflow inputs** into the same folder: `seqc2 samplesheet <config> --profile <p>
   --outdir <dir>` (profile with `paths: relative`, so the folder can be moved or committed).
7. **Place the data.**
   - <= ~10 MB: commit into the pipeline (`tests/data/` or `assets/`).
   - larger: separate test-data repo (data only, e.g. `workflow-nxf-<name>-testdata/seqc2/small/`),
     referenced by `params.pipelines_testdata_base_path` with a sibling-checkout fallback.
   - Remote (`access: remote`): commit only the generated samplesheet/params into
     `assets/seqc2/test/` and `includeConfig` its `params.config` (`--config-base
     '${projectDir}/assets/seqc2/test'`).
8. **Hand the test profile** (`conf/test_seqc2.config` or `conf/test.config`, nf-test) to
   `nf-core-testing` / `nextflow`: small `resourceLimits`, labels with <= 1 GB.
9. **Document** in `docs/testing.md` and the test-data README: config name, toolkit commit,
   windows, seed, size, citation.

## Checks before finishing

- `du -sh` of the folder, excluding caches; no leftover download folders (`.downloads/`) or
  `.part` files committed.
- Truth subset and VCF subset are on the same contig(s); the slice contains PASS calls and
  truth records (counts, not content).
- VCF headers still list all 2,779 contigs while the FASTA has one: intended for testing a
  reference check; otherwise trim the header with `bcftools reheader`/`view` after review.
- `seqc2 fetch` again does nothing (manifest up to date).

## Pitfalls

- `bam_windows` outside `subset.contigs` stops the build.
- Without `bam_targets`, WGS slices of 1 Mb grow quickly; keep `bam_subsample` for size.
- Recall on a slice is not comparable with published numbers; T1 checks function, not accuracy.
- Old test-data READMEs may name scripts that were replaced by the toolkit; update them.
