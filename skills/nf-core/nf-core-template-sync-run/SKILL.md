---
name: nf-core-template-sync-run
description: 'Run an nf-core template sync manually with `nf-core pipelines sync`. Use when the pipeline is behind the current nf-core/tools template, when the automated sync PR never appeared, or when a sync must be triggered on a non-nf-core (e.g. CUBI-internal) pipeline repository.'
argument-hint: 'Optional: target branch (default `dev`) and whether to open a pull request'
user-invocable: true
---

# nf-core Template Sync — Manual Run

**Canonical guide:** <https://nf-co.re/docs/developing/template-syncs/overview> and
<https://nf-co.re/docs/developing/template-syncs/manual-sync>

Read the guide before acting if any step below is ambiguous for this repository — the docs are
the source of truth, this skill is the checklist. Follow it in order; do not improvise a
git-only "manual merge" of template files.

## How template sync works

Each pipeline repository carries a `TEMPLATE` branch holding the unmodified nf-core template.
`nf-core pipelines sync` regenerates the template on that branch at the current tools version
and merges it toward your working branch, so the diff you resolve contains only template
changes, never your pipeline code. This only works if `TEMPLATE` shares git history with `dev`
— `nf-core pipelines create` sets that up; pipelines created any other way need
`nf-core-template-sync-bootstrap` first.

## Preconditions

- Active conda environment providing `nf-core` and `nextflow` (hand off to `conda-agent` if missing).
- Working tree clean (`git status` shows no uncommitted changes) — a sync creates a merge and will not be untangleable from unrelated edits.
- You know the current `nf-core --version`; the sync targets *that* template version.

## Procedure

1. Confirm the `TEMPLATE` branch exists and shares history:
   - `git branch -a | grep TEMPLATE`
   - `git merge-base dev TEMPLATE` — if this errors with "no merge base", stop and run `nf-core-template-sync-bootstrap` instead.
2. Check out the branch to sync into (nf-core convention is `dev`):
   - `git checkout dev`
3. If you work on a fork, track the upstream `TEMPLATE`:
   - `git remote add upstream <upstream-repo-url>`
   - `git checkout --track upstream/TEMPLATE`
   - `git checkout dev`
4. Run the sync:
   - `nf-core pipelines sync`
   - For a repository where you want the result as a PR instead of a local merge:
     `nf-core pipelines sync --dir <pipeline-dir> --from-branch dev --pull-request --username <github-username> --github-repository <repo-url>`
5. Resolve the resulting merge locally. Prefer the `TEMPLATE` version of a hunk by default; keep your own version only where the pipeline genuinely customises that file, and note each such case.
6. After conflicts are resolved, re-run linting: `nf-core pipelines lint`. Template syncs routinely change lint expectations, so a sync is not finished until lint is clean.
7. Run the test profile before considering the sync complete: `nextflow run . -profile test,<docker|singularity|conda> --outdir <tmp-outdir>`.

## Verification

- `git log --oneline -1 TEMPLATE` shows a commit at the current tools version.
- No conflict markers remain: `git grep -n '<<<<<<<' -- . | grep -v '^docs/'` returns nothing.
- `nf-core pipelines lint` passes.
- A `-profile test` run completes.

## Notes

- Never resolve template-sync conflicts through the GitHub web editor on the `TEMPLATE` branch — that is exactly what corrupts it (see `nf-core-template-sync-repair`).
- CUBI pipelines are workflow repositories with more than one push target; do not assume a single `origin`. Never push — report the branch and let the user push.
- Files intentionally excluded from the template are declared in `.nf-core.yml`; if a sync keeps reintroducing something you deliberately removed, fix `.nf-core.yml` rather than deleting it again each sync.
