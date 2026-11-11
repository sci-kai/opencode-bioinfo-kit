---
name: data-provenance-manifest
description: 'Record and verify provenance and integrity: sha256/md5 checksum lists, manifest JSON with sources, versions, settings and recipe, download registry, copy records, a verify command, and README/regeneration notes for test-data repos. Use when producing, copying, downloading or releasing data files, or when results must be reproducible.'
---

# Provenance and integrity

## Purpose

Anyone can see where a file came from, with which settings, and whether it is unchanged.

## When to use

Building datasets, copying files between systems, downloading public data, shipping test data,
releasing a workflow. Not for atomic writes (`data-atomic-state-and-backup`).

## Steps

1. Choose the hash: sha256 for own data; md5 only when checking against md5 lists published by upstream (e.g. NCBI FTP).
2. Checksum list in the dataset root: `checksums.sha256` with `<hash>  <relative path>` lines (md5: `checksums.md5`). Add `verify` to the tool: recompute all, report mismatches and missing files, exit non-zero.
3. Manifest `<tool>_manifest.json` (sorted keys, UTC ISO timestamp with offset): per derived file, the recipe (source URL or path, source checksum, tool and version, settings) and own checksum. Rebuild only files whose recipe changed or that were modified; remove files the config no longer selects.
4. Downloads: store once under `<cache>/<host>/<path>`, resumable; `registry.json` keeps size, mtime, checksum, `verified`. Rehash only if size/mtime changed or `--verify` is set; on mismatch download again.
5. Copy steps: after copying, recompute the checksum of the copy; write a per-file record TSV (`source`, `target`, `sha256`, `bytes`, `status`). If the copy is intentionally modified (e.g. pseudonymized header), say so and record the checksum of the copy.
6. Transfers: use rsync, then verify with checksums on the target.
7. Versions: record `pyproject.toml` version (semver string), tool versions (collated `versions.yml` to MultiQC), schema pins, source release/commit and retrieval date (ISO). Keep `manifest.version`, `pyproject.toml` and `.nf-core.yml` in sync.
8. Test-data repositories: data only; README table (folder, content, how created); regeneration command pointing to the generator in the code repo; paths in sheets relative; license and citation of any public source (accession, DOI).
9. Datasets also get `dataset.json` (selection, sizes) and a `README.md` listing sources and settings.

## Checks before finishing

- `verify` passes on a clean dataset and fails after touching one byte.
- Manifest and README name every source with URL, version/release and date.
- Regeneration instructions run from a clean checkout.

## Pitfalls

- Mixing md5 and sha256 in one list without naming the file accordingly.
- Hashing multi-GB files on every run; use the registry.
- Recording a checksum of the source for a file that was modified.
