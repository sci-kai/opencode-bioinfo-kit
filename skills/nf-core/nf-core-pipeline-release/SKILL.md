---
name: nf-core-pipeline-release
description: 'Run the full nf-core pipeline release procedure: pre-release checks, version bump, release lint, CHANGELOG finalisation, dev→main release PR, the GitHub release, and the post-release bump back to the next dev version. Use when releasing or preparing to release a pipeline version.'
argument-hint: 'Target version, e.g. `1.2.0`'
user-invocable: true
---

# Pipeline Release Procedure

**Canonical guide:** <https://nf-co.re/docs/developing/pipelines/release-procedure> — read it
before starting; a release has irreversible public steps and the doc is the authority.

Versions are strictly numeric and follow semantic versioning: `1.2.0`, never `v1.2.0`, never
`1.0.1rc`. Check the CUBI semantic-versioning rules (`~/.config/opencode/cubi-kb/rules-kb-agents-instructions.md`) as well — for CUBI-internal
pipelines they take precedence over the nf-core community-specific steps below.

## Phase 1 — pre-release checks (on `dev`)

- [ ] Outstanding bug reports triaged; milestone items either done or moved.
- [ ] `nf-core pipelines lint` passes on `dev`, and CI is green.
- [ ] Software dependencies updated where feasible (`nf-core modules update --preview --all` to see what is stale).
- [ ] `test_full` has completed successfully.
- [ ] `CHANGELOG.md` covers every addition and fix, and credits contributors' GitHub handles.
- [ ] First release only: repository description finalised, "under development" wording removed from README and repo description.

## Phase 2 — version bump PR (into `dev`)

1. Branch off `dev`.
2. `nf-core pipelines bump-version <1.2.0>` — never edit version strings by hand.
3. Update versions the tool cannot reach: pipeline diagrams, tutorials, figures, embedded example commands. `grep -rn "<old-version>" .` to find them.
4. `nf-core pipelines lint --release` — the stricter release ruleset. Must pass.
5. Set the version number **and the release date** in the `CHANGELOG.md` entry.
6. Open the PR into `dev`, get it reviewed and merged. (Never push — hand the commands to the user.)

## Phase 3 — release PR (`dev` → `main`)

1. Open the PR from `dev` to `main`. CI requirements differ for this PR type; wait for green.
2. Reviews: at least two people, at least one external/neutral to the pipeline's development. A first release additionally needs a core/maintainers team review. For nf-core pipelines, requests go through the `#release-review-trading` Slack channel — and reciprocating a review there is part of the process.
3. First release only: ask a core team member to lift the "Block releases" repository ruleset.
4. Finalise `CHANGELOG.md` (any late changes, correct date), then merge into `main`.

## Phase 4 — make the release

Create the GitHub release: title and body from the `CHANGELOG.md` entry, tag exactly the version
in the code (`1.2.0`, **not** `v1.2.0`).

## Phase 5 — post-release

Automatic: website update, `test_full` AWS megatest, social announcements, Zenodo DOI.

Manual:
- Verify the megatest ran and results appear as expected.
- First release only: request the DOI in the `main` branch `nextflow.config` manifest, the DOI badge and citation section in `README.md`, and the default branch switch from `dev` to `main`.
- Announce in the pipeline's channel.

## Phase 6 — open the next development version

1. Sync `dev` with `main`.
2. `nf-core pipelines bump-version <1.3.0>dev` (CUBI repos: `<1.3.0>-dev`, and update `pyproject.toml` in the same commit — a version bump is its own commit)
3. Add a new `CHANGELOG.md` section for the next version.
4. Update versions in non-automated files again.
5. Refresh snapshots: `nf-test test tests/ --profile=+<docker|singularity|conda>`
6. PR into `dev`.

## Agent guardrails

- **Never** create the GitHub release, merge the release PR, or push a tag yourself. Prepare everything, then present the exact commands/steps for the user to execute.
- Report the checklist state honestly: name every unchecked box rather than describing the release as ready.
- A release with failing CI, unlinted code, or an incomplete CHANGELOG is not ready — say so plainly instead of proceeding.
