---
name: data-atomic-state-and-backup
description: 'Implement crash-safe writes, state files, caches, backups, rotation and restore: tmp file + fsync + os.replace, sorted JSON state with lock file and UTC timestamps, SQLite snapshots, timestamped backups with keep-N and a safety copy before restore, idempotent re-runs. Use when a tool writes state, config, caches or backups, or after a half-written-file incident.'
---

# Atomic writes, state and backups

## Purpose

A crash, a second process or a re-run must never corrupt data or repeat work.

## When to use

Any code that writes a state/config/export file, keeps a cache, takes backups, or restores. Not
for checksum manifests (`data-provenance-manifest`).

## Steps

1. Atomic text/JSON write (stdlib):
   ```python
   def atomic_write_text(path, text):
       tmp = path.with_name(path.name + ".tmp")
       with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
           fh.write(text); fh.flush(); os.fsync(fh.fileno())
       os.replace(tmp, path)
   ```
   Tmp file in the same directory (same filesystem). Remove tmp on failure.
2. State file `<run_dir>/.<tool>-state.json`: `json.dumps(data, indent=2, sort_keys=True) + "\n"`; top-level `runid`, `steps`; each entry holds job ID, script, `submitted_at` as UTC ISO (`datetime.now(timezone.utc).isoformat(timespec="seconds")`). Serialize access with `fcntl.flock` on a sibling `.lock` file; load, change, save inside one context manager.
3. Completion: decide from real outputs on disk (expected files exist, non-empty, readable), not from marker files. A blocked step is retried on the next run; a finished step is never re-submitted.
4. Idempotence: re-running with unchanged inputs changes nothing; importing the same export twice is a no-op; offer `--dry-run`.
5. Edit in place only when unavoidable (config, case table): before the change copy to `<stem>_<YYYYMMDD>-<hhmmss>.<ext>` (or `<name>.bak` as one-step undo for config), then atomic write.
6. SQLite: one transaction per action, `PRAGMA synchronous=FULL`, busy timeout 30 s; snapshot with `sqlite3.Connection.backup()` into a tmp file, run `PRAGMA integrity_check`, `chmod 600` if it holds notes, then `os.replace`.
7. Backups: `<stem>_<YYYYMMDD>-<hhmmss>.<ext>` per kind (db, notes zip, portable JSON export); keep N newest per kind (default 14), user-saved named profiles never rotated; write to a dir other than the live data; never sync the live DB, sync snapshots. A failed automatic backup is logged, never stops the service.
8. Restore: refuse files that are not the expected format; first save the current file as `<stem>_<ts>_before-restore.<ext>`; replace atomically.
9. Portable export: JSON with `format`, integer `format_version`, sha256 of canonical content (sorted keys, checksum field removed). Import refuses newer versions, accepts older, supports `--dry-run`, merges by stable keys not internal IDs.
10. Cache: table `cache(key, stored, body)`; key = sha256 of canonical `[method, url, params, body]`; TTL per call; purge old rows at start; cache is rebuildable and gitignored; failure to write the cache must not fail the run.
11. Uploads/inputs: check in a tmp file first; an invalid file never replaces a good one; keep the previous as `.bak`.

## Checks before finishing

- Kill the process mid-write (test with an exception before `os.replace`): the old file is intact, no stray tmp.
- Two concurrent runs do not corrupt state.
- Restore works and can itself be undone.

## Pitfalls

- `.tmp` on another filesystem (replace becomes copy).
- Naive local timestamps in state files; use UTC with offset.
- Backups next to the live file inside a synced folder.
