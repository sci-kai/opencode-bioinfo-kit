---
name: test-synthetic-dataset
description: 'Design and generate synthetic or scrambled test data: a seeded generator script plus a design.tsv that states the intended outcome of every edge case, deliberate defects, size limits, and where generators and data live (data in a separate repo, code with the workflow). Use when a feature needs test inputs and real data must not be used.'
---

# Synthetic test dataset

## Purpose

Produce tiny, regenerable inputs where every case has a known, written-down expected outcome.

## When to use

- A new feature or check needs input; real data is private or too large.
- You need edge cases that real data rarely contains.
- Not for reference datasets such as SEQC2/GIAB (use `refdata`).

## Steps

1. List the edge cases from the requirements or use cases (`test-usecase-table`): one case per behaviour, plus deliberate defects the pipeline must detect or fix.
2. Write the generator `tests/synthetic/make_<name>_data.py` (executable, argparse `--outdir`, `--seed` default fixed). Use `random.Random(seed)`, never global random state, so output is reproducible byte for byte except for dates.
3. Keep it small: kilobases for references, tens of records, a few samples. Target well under 10 MB for anything committed.
4. Write `design.tsv` from the same data structure that creates the records, so they cannot drift. Columns:

   | id | case | input_file | position_or_row | intended_outcome | expected_in_output |
   |---|---|---|---|---|---|
   | E01 | MNV vs split SNVs | S1_wes.vcf.gz | chr1:1200 | matched by haplotype only | TP |

5. Add deliberate defects as named cases: missing header lines, wrong contig length, swapped columns, duplicated records, trailing whitespace in a table cell, a truncated date, an empty field. Mark each as `must_fail` or `must_fix`.
6. For tables that come from real sources: scramble or anonymise (shuffle values, replace IDs with synthetic ones like `500-26`), keep the structure and the typical errors. Document which inconsistencies are by design.
7. Storage: generator and tests in the code repo; bulky data in a separate `<name>-testdata` repo that holds data only, with `README.md` (how it was made, licence, citation) and `checksums.md5`. Paths in sample sheets are relative to the sheet. Alternatively generate on demand into `tests/data/generated` (gitignored).
8. Reference `design.tsv` IDs in test comments and asserts (`# E06: extra allele at a TP position`).
9. Check: run the generator twice and compare; validate files with the proper tools (`bcftools view -h`, `samtools quickcheck`, `faidx`), header-only.

## Checks before finishing

- Each design row has an assert somewhere (`test-pipeline-asserts` or pytest).
- No real identifiers, names, dates of birth or paths in the data or in `design.tsv`.
- The generator runs on the project environment without network access.

## Pitfalls

- Data that has to be edited by hand: not regenerable.
- Random data without fixed seed: flaky snapshots.
- Only success cases: add the must-fail ones.
