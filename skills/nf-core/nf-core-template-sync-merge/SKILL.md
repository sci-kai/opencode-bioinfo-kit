---
name: nf-core-template-sync-merge
description: 'Review and merge an automated nf-core template-update pull request ("Important! Template update for nf-core/tools vX.Y.Z"), including resolving major conflicts locally. Use when a template sync PR is open and needs to be integrated.'
argument-hint: 'Optional: PR number or template/tools version'
user-invocable: true
---

# nf-core Template Sync — Merge the Automated PR

**Canonical guide:** <https://nf-co.re/docs/developing/template-syncs/merge-automated-pull-requests>

Read the guide if a step is unclear for this repository. Follow the steps in order.

## When to use

- A PR titled "Important! Template update for nf-core/tools v\<version\>" is open.
- The pipeline needs the newest template but the automated PR has conflicts.

## Decision: web or local

- **Few, small conflicts** → resolve on the GitHub PR page, request review once CI passes.
- **Many or structural conflicts** → resolve locally with the procedure below. Do this whenever more than a handful of files conflict; the web editor is error-prone here.

## Procedure (local resolution)

1. Add the upstream remote if it is not present:
   - `git remote add upstream <upstream-repo-url>`
2. Create a dedicated merge branch off your working branch:
   - `git checkout -b merging-template-updates`
3. Pull the template branch into it:
   - `git pull upstream TEMPLATE`
4. List the conflicts:
   - `git status` — everything under "Unmerged paths".
5. Resolve each file. Default to the `TEMPLATE` version; keep the pipeline's version only where the file is genuinely customised for this pipeline, and record which files those were so the same decision can be repeated next sync.
6. Commit and push the branch:
   - `git commit -m "Merge changes from nf-core template"`
   - Do **not** run `git push` yourself — report the branch name and the exact push command for the user to run.
7. Open a PR from this branch to `dev`. Merge it with a **regular merge, not a squash** — squashing breaks the shared history that future syncs depend on.
8. The original automated PR closes by itself once this is merged.

## Verification

- No conflict markers remain: `git grep -n '<<<<<<<'` returns nothing.
- `nf-core pipelines lint` passes.
- A `-profile test,<backend>` run completes.
- CI on the PR is green before requesting review.

## Notes

- Squash-merging or rebasing a template merge destroys the merge base and makes the *next* sync conflict with the entire template. Always a plain merge commit.
- If the merge produces an implausible diff (whole files appearing as new, every line changed), suspect line-ending drift and retry with `-Xignore-space-at-eol`, or check whether the `TEMPLATE` branch is broken (`nf-core-template-sync-repair`).
- CHANGELOG: add an entry noting the template version the pipeline was synced to.
