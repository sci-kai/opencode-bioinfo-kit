---
name: python-stdlib-orchestration
description: 'Write stdlib-only orchestration scripts for production servers: idempotent submit/readiness logic with a locked atomic JSON state file, readiness judged from real outputs, pre-submission input checks, --dry-run and --force, blocked status with exit code 2, and a bash-and-Python shared KEY=value config. Use for scripts that submit jobs or hand over results step by step.'
---

# Stdlib-only orchestration script

Purpose: one command an operator can re-run safely. It submits what is ready, leaves the rest alone,
and says why (e.g. an orchestration script around a commercial tool).

## When to use / not to use

Use on servers without managed environments (PBS/HPC front ends, handover hosts). Use only the
standard library. Not for data transformation (put that in `bin/` scripts).

## Steps

1. **Layout:** `codebase/NN-verb-noun.py` entry point; helpers in `codebase/orchestration/_paths.py`, `_steps.py`, `_state.py` (underscore = internal). The entry point inserts the helper dir into `sys.path` with `# noqa: E402`. Use `from __future__ import annotations`; type hints, dataclasses and `Enum` are expected here.
2. **Shared config:** `config/paths.env` as flat `KEY=value` lines (no quoting tricks) so bash `source` and Python read the same file. The parser skips blank and `#` lines. Only the location of the config itself may be a hard-coded default; every entry point accepts `--workdir`.
3. **Step definitions as data:** a dataclass per step (name, script, prerequisite check, input checks). Status enum: `COMPLETE`, `SUBMITTED`, `READY`, `WAITING`, `BLOCKED`.
4. **Readiness from real outputs:** check the prerequisite's output files on disk (exist, non-empty, expected names). No marker files, no scheduler-side dependency chains: a failed step leaves dependants unsubmitted.
5. **Input checks before submit:** every path in the step's sample sheet exists and is readable; ambiguous or missing inputs make the step `BLOCKED` with the file named. Blocked is retried on the next run and never recorded as submitted.
6. **State file** `<run_dir>/.orchestration-state.json`: step, job id, script, UTC ISO timestamp. Write sorted JSON with indent 2 and trailing newline, atomically (`tmp.replace(path)`), under `fcntl.flock` on a separate lock file via a context manager, so two invocations cannot double-submit.
7. **Flags:** `--dry-run` prints the same status report without submitting or writing anything; `--force` resubmits a step whose prerequisites are met despite a previous submission, never one that completed successfully, and never cancels earlier jobs. Without `--force` a failed job is not resubmitted.
8. **Report and exit code:** print one line per step (status + detail); exit 0 when nothing is blocked, 2 when any step is `BLOCKED`, 1 for errors.
9. **Tests:** temp run dirs with fake outputs; test each status, re-run idempotency (second run submits nothing), blocked case, `--dry-run` leaves no files, concurrent lock if feasible. Fake the scheduler call (`qsub`) by injecting a function.

## State helper sketch

```python
@contextlib.contextmanager
def locked_state(run_dir, runid):
    """Load state under an exclusive lock, yield it, save it back on exit."""
    with (run_dir / ".orchestration-state.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = _load(run_dir / ".orchestration-state.json", runid)
        yield data
        _save(run_dir / ".orchestration-state.json", data)  # tmp file + replace
```

## Checks before finishing

- Running twice in a row changes nothing the second time.
- `--dry-run` output equals the real run's report.
- No import outside the standard library (`python -I -c "import ..."` in a bare interpreter).

## Pitfalls

- Never relax an existence/readability/ambiguity check to make a run pass; report it.
- Hard-coded paths other than the bootstrap default and the intentionally self-contained server scripts.
- Writing state before the submission succeeded.
