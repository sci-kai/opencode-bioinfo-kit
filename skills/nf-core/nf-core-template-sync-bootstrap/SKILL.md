---
name: nf-core-template-sync-bootstrap
description: 'Retrospectively set up nf-core template syncing for an existing pipeline that was not created with `nf-core pipelines create` — builds the orphan TEMPLATE branch and merges it into dev. Use when a pipeline has no TEMPLATE branch or its TEMPLATE shares no history with dev.'
argument-hint: 'Pipeline name and its current version (e.g. `1.3dev`)'
user-invocable: true
---

# nf-core Template Sync — Retrospective Setup

**Canonical guide:** <https://nf-co.re/docs/developing/template-syncs/set-up-pipeline-sync>

Read the guide before starting. This is a one-off, high-impact operation on a repository's
history; work through it step by step rather than from memory.

## When to use

- `git branch -a | grep TEMPLATE` finds nothing.
- `git merge-base dev TEMPLATE` fails with "no merge base" (unrelated histories).
- A pipeline was hand-written or migrated in and now needs to ride the nf-core template.

## Preconditions

- Conda environment with `nf-core` available.
- You have read the pipeline's `nextflow.config` `manifest {}` block — you must reproduce **exactly** the same name, description, author, and version when regenerating the template, or the merge will be far larger than necessary.

## Phase 1 — build the TEMPLATE branch

1. Clone into a scratch directory, not the working checkout:
   - `mkdir <temp-dir>` ; `cd <temp-dir>` ; `git clone <repo-url>` ; `cd <pipeline-name>`
2. Create an empty orphan branch:
   - `git checkout --orphan TEMPLATE && git rm -rf '*'`
   - `git status` must report nothing to commit.
3. Regenerate the pipeline from the current template, answering the prompts with the *exact* values from the existing `nextflow.config`:
   - `nf-core pipelines create --no-git`
   - If the pipeline already has releases, pass the matching version: `nf-core pipelines create --no-git --version <1.3dev>`
4. Move the generated tree to the repository root:
   - `mv nf-core-<pipeline-name>/* .`
   - `mv nf-core-<pipeline-name>/.[!.]* .`
   - `rmdir nf-core-<pipeline-name>`
5. Commit:
   - `git add .`
   - `git commit -m "Initial template commit"`
6. Publishing the branch (`git push --set-upstream origin TEMPLATE`) is a **user-run step** — prepare it, do not execute it.

## Phase 2 — merge TEMPLATE into the pipeline

1. `git checkout dev`
2. `git checkout -b template_merge`
3. `git merge TEMPLATE --allow-unrelated-histories`
   - If entire files show up as new, retry with `-Xignore-space-at-eol`.
4. Resolve every conflict. Take the template version for infrastructure files (CI workflows, `.github/`, `docs/` scaffolding, `nextflow_schema.json` structure); keep the pipeline version for actual workflow logic and its real parameters.
5. `git commit -m "Merge vanilla TEMPLATE branch into pipeline"`
6. Open a PR from `template_merge` to `dev`; merging it enables future automatic syncs.

## Verification

- `git merge-base dev TEMPLATE` resolves.
- `nf-core pipelines lint` passes on the merged branch.
- A `-profile test,<backend>` run completes.
- A subsequent `nf-core pipelines sync` produces a small, template-only diff.

## Notes

- Record in the PR body which template version was used as the base, so the next sync's diff is interpretable.
- Do not squash this merge — future syncs depend on the merge base surviving.
