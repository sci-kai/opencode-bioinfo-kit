---
name: nf-core-branch-master-to-main
description: 'Rename a pipeline default branch from master to main, including the template sync merge, repository-wide reference updates, and the commands collaborators must run. Use when a repository still uses `master`.'
argument-hint: 'Repository name'
user-invocable: true
---

# Rename `master` to `main`

**Canonical guide:** <https://nf-co.re/docs/developing/pipelines/master_to_main>

## Step 1 — rename on the remote (user-run, web UI)

This is the user's action, not the agent's. Present it as instructions:

1. Open the repository on GitHub with the `master` branch selected.
2. **Branches** → in the **Default** section, the three-dot menu next to `master` → **Rename branch**.
3. Rename to `main` and confirm. Save the instructions GitHub shows for contributors.

CUBI pipelines commonly have more than one push target — the rename must be done on **every**
remote the repository publishes to, not just one.

## Step 2 — local repository

```bash
git fetch upstream
git config --global init.defaultBranch main
git config --global init.defaultBranch          # verify it now prints "main"
git switch dev
nf-core pipelines sync
git switch -c default-branch-change
git merge TEMPLATE
```

Resolve any merge conflicts from the sync.

## Step 3 — update references

Search the repository for `master` and update the ones that refer to *this* repository's branch
— CI workflow triggers, badge URLs, raw-content links, documentation, `nextflow.config`
defaults:

```bash
grep -rn "master" --exclude-dir=.git .
```

Leave links pointing at *external* repositories' `master` branches alone.

Then:

```bash
nf-core pipelines lint
git add -A && git commit -m "Change default branch to main"
```

Open a PR against `dev`. (Do not push — hand the push command to the user.)

## Step 4 — collaborator instructions

Include these in your report so the user can forward them; everyone with a clone or fork runs:

```bash
git branch -m master main
git fetch origin
git branch -u origin/main main
git remote set-head origin -a
```

## Verification

- `nf-core pipelines lint` passes.
- CI triggers fire on `main` (check the workflow files' `on: push/pull_request` branch lists).
- No stale `master` references remain: re-run the grep.
- A `-profile test,<backend>` run completes.
