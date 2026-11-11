---
name: python-validation-errors
description: 'Implement strict input validation and error/log messages in Python: ERROR/WARNING/INFO prefixes on stderr, exit codes, messages that name file, record, expected, observed and fix, collect-then-report validators, an error class with run_cli wrapper, and failure tests. Use whenever a script reads inputs, sheets or config and must fail early.'
---

# Strict validation and error messages

Purpose: an error is better than a wrong result. A user must be able to fix the problem from the
message alone, without reading code.

## When to use

Any script reading sample sheets, config, VCF/BED/tables, or manually maintained files. Check all
inputs before writing any output.

## Message format

`ERROR: <file>: <what is wrong> (expected <X>, found <Y>); <how to fix>`

Example: `ERROR: sheet.tsv: line 4: tumor_id 'TUMOR1' not found (samples in the VCF: TUMOR, NORMAL); check tumor_id in the sample sheet`.

Prefixes `ERROR:`, `WARNING:`, `INFO:` go to stderr. Exit codes: 0 ok, 1 error, 2 blocked / not ready
(missing prerequisite, used by orchestration). Never print a traceback for an expected failure.

## Steps

1. **Pick the mechanism.**
   - Simple script: `sys.exit(f"ERROR: ...")` (stderr, exit 1).
   - Several scripts or a package: an exception class carrying the parts, plus a wrapper:
     ```python
     class ToolError(Exception):
         def __init__(self, message, *, file=None, record=None, expected=None, observed=None, fix=None):
             parts = [message]
             for key, val in (("file", file), ("record", record), ("expected", expected),
                              ("observed", observed), ("fix", fix)):
                 if val is not None:
                     parts.append(f"{key}: {val!r}" if key == "observed" else f"{key}: {val}")
             super().__init__(" | ".join(parts))

     def run_cli(main):
         try:
             main()
         except ToolError as err:
             logging.getLogger("tool").error("ERROR: %s", err)
             sys.exit(1)
     ```
     `setup_logging(verbose)` logs to stderr with `%(asctime)s %(levelname)s %(message)s`, datefmt `%Y-%m-%dT%H:%M:%S`. With `logging` keep the `ERROR:` text prefix so output is greppable.
   - Sheet validation: an error collector with `warn()`, `error()`, `report_and_exit_on_error()`: print all warnings, then all errors, then `N problem(s) found, see above. Fix the sheet and run again.`, exit 1. Use it when many rows can be wrong at once.
2. **Order of checks:** file exists and readable, not empty, header present and delimiter right, required columns, removed/unknown columns (removed: error with "use X instead"; unknown: WARNING), then per-row checks with line numbers (header is line 1), then cross-row checks (duplicates, pairs).
3. **Strip and normalise** whitespace in manually maintained tables before checking; report each automatic fix (see `python-provenance-checks`, corrections table).
4. **Fallbacks:** if a fallback is intended (AF used when AD is missing) log `INFO:` once with the count and write the count to the summary; never fall back silently.
5. **Switches:** a check that can be disabled by a param turns its errors into `WARNING:`; the default stays strict.
6. **Tests:** one test per check; use `pytest.mark.parametrize` over (mutation, expected message fragment); assert exit code != 0 and the `ERROR:` fragment in stderr; add a test that valid input passes with no WARNING.

## Checks before finishing

- Every message names the file and, where possible, the record/line and the fix.
- No bare `raise ValueError("bad")` or `assert` for user input.
- stdout carries only data; diagnostics are on stderr.

## Pitfalls

- Reporting only the first error when the user must run again for each; collect.
- Catching `Exception` broadly and hiding the cause.
- Messages that print real IDs in logs shared outside the project; check what a message exposes.
