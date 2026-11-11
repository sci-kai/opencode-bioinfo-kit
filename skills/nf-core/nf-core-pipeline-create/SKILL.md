---
name: nf-core-pipeline-create
description: 'Scaffold a new pipeline from the nf-core template with `nf-core pipelines create`, including CUBI metadata defaults, .nf-core.yml template feature selection, and first-run verification. Use when starting a new Nextflow pipeline.'
argument-hint: 'Pipeline name and one-line description'
user-invocable: true
---

# Create a New nf-core Pipeline

**Canonical guides:** <https://nf-co.re/docs/developing/pipelines/template-files> and
<https://nf-co.re/docs/developing/overview>

## Preconditions

- Conda environment with `nf-core` and `nextflow` active.
- Agreed pipeline name (lowercase, no punctuation), description, and whether it is a CUBI-internal pipeline or intended for nf-core.
- Confirm with the user before creating anything if the target directory already contains a repository.

## Procedure

1. Scaffold:
   ```
   nf-core pipelines create \
     --name <NAME> \
     --description "<DESC>" \
     --author "<Your Name>" \
     --version v1.0.0dev \
     --outdir . \
     --organisation core-unit-bioinformatics
   ```
   Do **not** let the tool create or push a GitHub repository automatically — remote setup is a manual, user-owned step.
2. Review `.nf-core.yml`: it records the repository type and which template features were skipped. Deselecting a feature here (rather than deleting its files later) is what keeps future template syncs clean.
3. Confirm the `TEMPLATE` branch exists — `git branch -a` — since automatic template syncing depends on it. If the pipeline was created some other way, run `nf-core-template-sync-bootstrap`.
4. Set the CUBI remotes. Pipeline repositories are workflow repositories under the CUBI Dev-process and normally use **both** the `github` and `githhu` push targets — do not assume a single `origin`. Configure the remotes, but never push: hand the push commands to the user.
5. Adjust `nextflow.config` `manifest {}` and the `params` block to real values; rebuild the schema afterwards with `nf-core pipelines schema build`.
6. Establish the branch structure: `main` (releases) and `dev` (integration); all work happens on `feat-<short-desc>` or `issueNN-<short-desc>` branches off `dev`. Never commit directly to `main` or `dev`.

## Verification

- `nf-core pipelines lint` passes on the fresh scaffold.
- `nextflow run . -profile test,docker --outdir <tmp-outdir>` completes.
- `git log` shows the initial template commit and a `TEMPLATE` branch pointing at it.
- `.nf-core.yml` reflects the intended feature set.

## Notes

- Install real functionality via `nf-core-module-install` + `nf-core-module-wire-in`; do not hand-write processes into `main.nf` when an nf-core module exists.
- Keep `README.md`, `docs/usage.md`, and `docs/output.md` truthful from the start — the template ships placeholder text that must not survive into a release.
