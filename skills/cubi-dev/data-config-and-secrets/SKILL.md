---
name: data-config-and-secrets
description: 'Lay out configuration, defaults and secrets for a project: config.example.yaml plus gitignored real file, n/a for unset values, <placeholder> templates for site IDs, site config outside the repo, .env for shared bash/Python paths, .gitignore entries. Use when adding a setting, API key, password, site identifier or path, or when real values risk entering git.'
---

# Config and secrets layout

## Purpose

Keep settings reviewable and reproducible while real secrets, site identifiers and machine paths
never reach git.

## When to use

Adding any setting, key, password, hostname, submitter/site ID, or absolute path. Not for sample
sheets (`data-samplesheet-schema`).

## Steps

1. Sort each value: default (commit), machine-specific (gitignored), secret or site ID (outside repo).
2. Human config as YAML. Commit `config/config.example.yaml` with comments, ISO dates in the header and `n/a` for unset values:
   ```yaml
   # Dates follow ISO 8601 (YYYY-MM-DD).
   paths:
     base_dir: n/a          # n/a = folder that contains config/
   api:
     service_key: n/a       # optional key; request at <url>
   ```
3. Gitignore the real file and runtime data:
   ```
   config/config.yaml
   /data/
   *.sqlite
   *.bak
   ```
4. Validate on load; reject unknown keys (pydantic `extra="forbid"`, or a JSON Schema with `additionalProperties: false`). Resolve relative paths against one documented base directory.
5. Site IDs and secrets: commit a template with `<placeholder>` values and a `description` saying "copy, fill in, never commit":
   ```json
   {"description": "Copy to a private location and pass with --site_config.",
    "submitterId": "<submitterId>", "centerId": "<centerId>"}
   ```
   Pass the real file by parameter; never default to a real path.
6. Placeholder guard: before writing any generated record, scan it for leftover `<...>` strings and abort listing their JSON paths.
7. Passwords: store only a salted hash (scrypt); signing keys in a gitignored file (e.g. `data/web_secret`), mode 600, rebuildable.
8. Shared bash + Python values only: `config/paths.env` with plain `KEY=value`, no interpolation, a comment per key; parse in Python with a 10-line reader, `source` in bash. Per-step params in `config/<step>/nf-params.json` + `run.config`.
9. Thresholds belong in a config file with a comment, not in code; the script errors if a needed value is missing.
10. Config edits by tools: round-trip YAML (ruamel) to keep comments, copy to `<name>.bak`, write atomically (`data-atomic-state-and-backup`).

## Checks before finishing

- `git status` and `git grep -n "<real-looking value>"` show no secret or real ID.
- The example file loads with the validator; the real file is ignored (`git check-ignore -v config/config.yaml`).
- Every key is documented in `docs/usage.md`.
- Instructions for agents mention: a `<submitterid>`-style value in data means the real value was withheld; use the config, never invent one.

## Pitfalls

- Hardcoded absolute paths or env vars in workflows: pass as params.
- Putting real IDs into test fixtures; use synthetic ones.
- `*.bak` or `*cache*` committed by accident: ignore them.
