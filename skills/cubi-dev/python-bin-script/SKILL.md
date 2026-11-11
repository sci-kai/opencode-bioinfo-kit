---
name: python-bin-script
description: 'Write an executable Python helper script for a workflow (bin/ or codebase/): shebang, INPUT/OUTPUT docstring, argparse, main() that only orchestrates, strict checks, summary counts, and the choice between a single script, sibling imports and a bin/<pkg>/ package with thin CLIs. Use when adding or restructuring a script that a Nextflow/Snakemake process or an operator calls.'
---

# Python script for bin/ or codebase/

Purpose: one script, one job, callable from a workflow process or by hand, testable without the
workflow engine.

## When to use / not to use

Use for helpers that parse, validate, decide, summarise or convert. Not for stand-alone tools with
subcommands (use `python-package-cli`), not for submit/readiness logic (`python-stdlib-orchestration`).
Genomic parsing rules and statistics belong to `bioinformatics-agent`; call a tool (bcftools, ...)
instead of writing code when one already does the job, and say so in the docstring.

## Steps

1. **Choose the structure.**
   - 1-3 scripts share code: one file each, importing helpers from a sibling script (VC: readers live in `check_reference.py`).
   - More than 3 share logic: package `bin/<pkg>/` (modules, `errors.py`, `cli.py` with a base parser) plus thin scripts `bin/<pkg>_<verb>_<noun>.py` of 30-110 lines. Tests add `bin/` to `sys.path` in `tests/python/conftest.py`.
   - File names use `_`, not `-`, so tests can import them. `chmod +x`.
2. **Write the module docstring first.**
   ```
   """<One-line purpose>.

   INPUT
     --input   <format, columns, types, 0- or 1-based>
   OUTPUT
     --output  <file, columns>
     --summary key<TAB>value counts (records_read, records_written, records_dropped_<reason>)
   Checks (an error stops the script with exit status 1)
     - <each check>
   Why a script: <tools considered and why they are not enough>
   """
   ```
   Add "Tested" and "Expected to work, untested" input lists when formats vary by tool version.
3. **Skeleton.**
   ```python
   #!/usr/bin/env python3
   import argparse
   import sys

   def parse_args(argv=None):
       parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
       parser.add_argument("--input", required=True, help="normalized VCF (tumor first)")
       parser.add_argument("--max-missing", type=float, default=0.1,
                           help="pipeline param max_missing: WARNING above this share")
       return parser.parse_args(argv)

   def main(argv=None):
       args = parse_args(argv)
       # 1. check inputs   2. process   3. write outputs   4. log summary
       return 0

   if __name__ == "__main__":
       sys.exit(main())
   ```
   Long hyphenated flags, help text on every flag, required inputs `required=True`, optional feature = omitted flag. Every threshold is a flag whose help names the pipeline param.
4. **Check inputs first** (existence, readability, non-empty, header/columns, ID present) with `python-validation-errors` messages, before any output is written.
5. **Process in small functions**, each with a docstring; one inline comment per block saying what the next lines do exactly, written for a newcomer reviewing the code. Add `# Design decision: … because …; rejected …` for every non-obvious choice and `# Assumption: …` where input properties are assumed; explain each check's error and each correction's rule. Constants in UPPER_CASE; tables as data (lists of tuples), not branches. Paths, URLs and thresholds come from the central config or CLI flags (defaults declared once at the top), never from inside functions.
6. **Write outputs atomically** (tmp file + `os.replace`) and log the summary with `python-provenance-checks`.
7. **Test** in `tests/python/test_<script>.py`: import the module for unit tests and run the script with `subprocess` for CLI behaviour (exit code, stderr text). Add synthetic fixtures, not real data.
8. Run `black <dirs>` and `ruff check <dirs>` with the project config.

## Checks before finishing

- `./bin/<script>.py --help` works and lists every flag with help.
- Each check has a test that asserts `ERROR:` and exit 1.
- The summary counts add up (read = written + dropped).
- No engine logic (no Nextflow variables) inside the script.

## Pitfalls

- Hyphenated file names cannot be imported; keep scripts importable.
- `sys.exit("ERROR: ...")` prints to stderr with exit 1: fine, but add a hint to fix.
- Do not hide a fallback default; log and count it.
- Logic hidden in the Nextflow module `script:` block instead of the script.
