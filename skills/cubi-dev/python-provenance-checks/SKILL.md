---
name: python-provenance-checks
description: 'Make Python tools traceable: version pins and runtime checks, sha256/md5 checksums, manifests and caches that skip unchanged files, a verify command, summary tables of records read/kept/dropped with reasons, dated outputs, and a corrections/issues table for raw input. Use when output must be reproducible or auditable, e.g. diagnostics and test-data builders.'
---

# Provenance and reproducibility in code

Purpose: from an output file anyone can tell what went in, which versions and settings were used,
what was dropped and why, and whether the files are still intact.

## Steps

1. **Version.** `__version__` string in the package (or `pyproject.toml`); `--version` flag in the base parser; compare versions as integer tuples when the standard library only is allowed (no `semver` package there), otherwise use `semver`.
2. **Pins file** (`assets/pins.json`): tool and Python versions, sha256 of schemas/reference tables. At start call `check_runtime(pins)`; on mismatch raise the validation error with expected and observed (see `python-validation-errors`). A pin `3.1` accepts `3.1.x`.
3. **Checksums.** `sha256_of(path)` reading in 1-8 MB chunks. Use sha256 for own files and md5 only where upstream publishes md5. Verify after copying files and name both digests in the error.
4. **Manifest / registry** (JSON, sorted keys): per file size, mtime (ns), checksum, source URL, recipe/settings used. Skip re-hashing when size and mtime are unchanged unless `verify=True`. Write the manifest after every output so an interrupted run keeps it. A `verify` command recomputes and exits 1 on any CHANGED/MISSING.
5. **Summary counts.** Every filtering/transforming script writes `--summary` as a two-column TSV `key<TAB>value`: `records_read`, `records_written`, `records_dropped_<reason>`, per-source counts, fallback counts. Read must equal written plus dropped; assert that in a test. Also log them as `INFO:` lines to stderr. Feed them to the report (MultiQC tables in Nextflow).
6. **Mark outputs.** Put a header marker when a result is degraded (e.g. `##tool_vaf=unavailable`), so later steps report NA instead of guessing.
7. **Dates.** ISO 8601; filenames `YYYYMMDD_<name>`; timestamps `datetime.now(timezone.utc).isoformat(timespec="seconds")`. Make "today" a parameter (`--today`) so a run can be reproduced.
8. **Raw input is immutable.** Write a normalized copy plus a `corrections.tsv` (row, column, old, new, rule) and an `issues.tsv` (row, severity, message). Every automatic fix has a rule name.
9. **Workflow versions.** In Nextflow modules the script's `--version` output goes into `versions.yml`.

## Skeleton

```python
def sha256_of(path, chunk_size=8 * 1024 * 1024):
    """sha256 hex digest of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()

def write_summary(path, counts):
    """Write key<TAB>value counts in a stable order, atomically."""
    tmp = Path(str(path) + ".tmp")
    tmp.write_text("key\tvalue\n" + "".join(f"{k}\t{v}\n" for k, v in counts.items()))
    os.replace(tmp, path)
```

## Checks before finishing

- Re-running with the same input gives identical outputs (normalize volatile fields: timestamps, paths).
- Summary counts reconcile; a test covers it.
- `verify` detects a modified file (test: edit a byte in a temp copy).

## Pitfalls

- Hashing large files on every run; use the size+mtime shortcut.
- Wall-clock dates inside outputs that break snapshot tests; parameterise them.
- Logging sensitive values (IDs, submitter codes) in manifests; hash or omit them.
