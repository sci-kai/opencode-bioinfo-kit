---
name: python-port-from-r
description: 'Port an R (or other-language) script to Python without changing results: inventory behaviour, keep CLI and output layout, reproduce quirks such as NA handling and ID derivation, add equivalence tests on the same input, and document deviations. Use when replacing R scripts by stdlib or pandas Python, e.g. for production servers.'
---

# Port a script to Python, behaviour-equivalent

Purpose: replace the language, not the results. A silent change in output can reach a patient or a
published number.

## When to use / not to use

Use for a faithful port. A redesign or a threshold fix is a separate, result-affecting change: ask
first, one commit each (workspace rules apply).

## Steps

1. **Inventory the original.** List inputs, CLI arguments, defaults, outputs (names, columns, order, sorting, number formatting), checks and error texts, and quirks: `read.delim` treats only the literal `NA` as missing, factor ordering, 1- vs 0-based indices, rounding, locale-dependent sorting, hashing of IDs.
2. **Freeze reference output.** Run the R script on a small synthetic input (or an approved tiny slice) and keep the outputs outside the repo or as test fixtures. Never use real patient data as fixture.
3. **Keep the interface.** Same CLI, same checks, same output layout, so callers do not change (record this sentence in the docstring: "kept behaviourally equivalent: same CLI, same checks, same output layout"). Name the original: "Port of `<script>.R`".
4. **Choose dependencies by target.** Production server: stdlib only (`csv`, `json`, `argparse`, `pathlib`). Pipeline env: pandas allowed. Do not add a dependency just to mimic one R function; write a small helper with a docstring noting the R behaviour it mirrors (e.g. `as_missing`).
5. **Write the port** with `python-bin-script`; keep IDs derived identically (e.g. the same sha256 input string) so identifiers stay stable.
6. **Equivalence tests.** Run old and new on the same inputs, normalize volatile fields, diff record by record, and show the diff. Cover edge cases: empty input, missing column, NA values, whitespace, odd characters. A test per deviation.
7. **Document deviations** (anything not byte-identical, with reason) in the docstring, `CHANGELOG.md` and the commit message. Mark the change as AI-assisted the way the project does.
8. **Keep the R script until the diff is clean** and the user agrees to remove it.

## Example of a mirrored quirk

```python
NA_TOKEN = "NA"

def as_missing(value):
    """Mirror R's read.delim default: only the literal text 'NA' is missing."""
    return None if value == NA_TOKEN else value
```

Empty strings stay empty strings, as in the original; a test pins this.

## Checks before finishing

- Equivalence diff is empty, or every difference is listed and approved.
- Error behaviour matches (same inputs rejected, exit non-zero).
- Docs and workflow call sites updated; the old script is not silently left running.

## Pitfalls

- Floating-point formatting (`format`/`round` differences): compare numerically with a stated tolerance.
- Sorting differences from locale or stable vs unstable sort.
- Treating an R quirk as a bug and fixing it during the port.
