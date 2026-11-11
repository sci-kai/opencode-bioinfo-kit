---
name: nf-core-template-sync-repair
description: 'Repair a broken or polluted nf-core TEMPLATE branch by resetting it to the initial template commit and re-syncing. Use when template syncs conflict with the whole pipeline, when pipeline code has leaked into TEMPLATE, or when a sync PR shows an implausible diff.'
argument-hint: 'Optional: pipeline repository name'
user-invocable: true
---

# nf-core Template Sync — Repair a Broken TEMPLATE Branch

**Canonical guide:** <https://nf-co.re/docs/developing/template-syncs/fix-broken-template-branch>

Read the guide before running any step here — this skill force-pushes and rewrites branch
history, so verify against the docs rather than acting from memory.

## Symptoms that mean the branch is broken

- The sync PR diff contains pipeline-specific code, not just template files.
- Every file appears as new/changed in the sync diff.
- Conflicts were previously resolved through the GitHub web interface on `TEMPLATE` (the usual cause: it commits the *merged* state onto `TEMPLATE`, which must only ever hold vanilla template code).

## ⚠️ Destructive-action guardrail

Step 4 rewrites remote history irreversibly. **Never run the force-push yourself.** Prepare
everything up to it, verify the reset commit is correct, then hand the exact command to the
user for confirmation and manual execution. This project's rules already forbid the agent
running `git push` at all — that applies with extra force here.

## Procedure

1. Work on a fresh clone of the canonical repository, not on a working copy with local state:
   - `git clone <repo-url>` ; `cd <pipeline-name>`
2. Find the original template commit:
   - `git checkout TEMPLATE`
   - `git log --reverse`
   - Identify the first commit, message like `initial template build from nf-core/tools, version <X.Y>`. Record its hash and show it to the user before continuing.
3. Reset the branch locally to that commit:
   - `git reset --hard <commit-hash>`
4. **User-run step:** `git push origin TEMPLATE --force` — present this command, state plainly that it overwrites remote history, and wait for the user to run it.
5. Re-sync to the current template:
   - `git checkout dev`
   - `nf-core pipelines sync`
6. Refresh any fork that still holds the old `TEMPLATE`:
   - `git branch -D TEMPLATE`
   - `git remote add upstream <upstream-repo-url>`
   - `git fetch upstream TEMPLATE`
   - `git checkout --track upstream/TEMPLATE`
   - (force-push of the fork's `TEMPLATE`: again a user-run step)
7. Open a PR from the repaired `TEMPLATE` toward `dev` and resolve conflicts locally, per `nf-core-template-sync-merge`.

## Verification

- `git log TEMPLATE --oneline` shows only template-build/sync commits, no pipeline feature commits.
- `git merge-base dev TEMPLATE` resolves successfully.
- A fresh `nf-core pipelines sync` produces a diff containing only template files.

## Notes

- Every collaborator and fork holding the old `TEMPLATE` must delete and re-track it; list who needs to do that in your report.
- Prevention: resolve template conflicts locally on a merge branch, never in the GitHub web editor on `TEMPLATE`.
