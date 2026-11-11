---
name: test-failure-paths
description: 'Write tests for the failure behaviour of scripts and pipelines: every input check gets a test for missing, unreadable, empty or malformed files, missing columns and unexpected IDs, asserting the ERROR text and a non-zero exit code. Use whenever a check, validation or error message is added or changed.'
---

# Failure-path tests

## Purpose

Make sure bad input stops the run with a clear `ERROR:` and a non-zero exit, never with a wrong but plausible result.

## When to use

- You add or change an input check, validator or error message.
- You review a change and no failure test exists for it.
- Not for flaky infrastructure failures (use `debug-agent`).

## Steps

1. List the checks: grep the code for `sys.exit`, `raise`, `error`, `ERROR`. Each one needs a test.
2. Cover the standard failure classes per input:
   - file missing; file unreadable (chmod 000, skip as root); file empty
   - malformed content (truncated line, wrong delimiter, bad header)
   - missing required column; unknown or duplicated ID
   - values out of range or in the wrong format (dates, positions)
   - ambiguous state that the script refuses to guess (e.g. unclear tumor/normal)
3. Function level: `with pytest.raises(Exception, match="expected text")`. Match on the part of the message that names the file, record and expected versus observed value.
4. Script level (CLI): run as a subprocess and assert both exit code and stderr.

   ```python
   proc = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
   assert proc.returncode == 1
   assert "ERROR:" in proc.stderr and "missing column 'sample'" in proc.stderr
   ```
   Also assert that no output file was written when the script failed.
5. Pipeline level: use `workflow.failed` and a log check (see `test-pipeline-asserts`), or a `must-fail` scenario with `error_contains` (see `test-scenario-suite`).
6. Put must-fail cases in the use-case table next to the success cases (`test-usecase-table`).
7. Also test the correctable case: input with a fixable defect must be corrected, listed in the corrections table, and the corrected value must not appear in the issues table.

## Checks before finishing

- Each error message is asserted at least once, with exit code.
- A success-path twin exists for every failure test (same input, defect removed), so the test cannot pass for the wrong reason.
- Error messages name file, record, expected, observed and a fix.

## Pitfalls

- Asserting only `returncode != 0`: any crash then passes. Assert the message.
- Weakening a check to make a test green. Ask the user first.
- Matching the whole message: tests then break on harmless rewording; match the stable part.
