---
name: nf-core-module-update
description: 'Update vendored nf-core modules/subworkflows to newer upstream versions with `nf-core modules update`, and manage local modifications with `nf-core modules patch`. Use when bumping a tool version, refreshing all vendored components, or when a module needs a pipeline-specific change.'
argument-hint: 'Module name, or `--all` to refresh everything'
user-invocable: true
---

# Update and Patch Vendored Components

**Canonical reference:** the nf-core tools CLI (`nf-core modules update --help`) and
<https://nf-co.re/docs/developing/pipelines/adding-modules>

## Updating

1. Always preview before applying:
   - `nf-core modules update --preview <tool>/<subtool>`
   - `nf-core modules update --preview --all` for a full refresh
2. Apply:
   - `nf-core modules update <tool>/<subtool>`
   - `nf-core subworkflows update <name>` for subworkflows
3. Read the diff (`git diff modules/`) for interface changes, not just version bumps: changed input tuple shape, renamed output channels, new required inputs, versions-emission changes. Any of these means the calling workflow must be updated in the same change.
4. Update `conf/modules.config` if the tool's CLI flags changed — `ext.args` values are not validated and will silently fail at runtime.
5. Re-run tests and refresh snapshots deliberately: `nf-test test --profile <backend>`, then `--update-snapshot` **only** after you have confirmed each changed output is an intended consequence of the update.

## Patching (pipeline-specific modifications)

Editing a vendored module in place makes it drift silently and breaks the next update.

1. Make the edit in `modules/nf-core/<tool>/<subtool>/main.nf`.
2. Record it as a patch: `nf-core modules patch <tool>/<subtool>` — this writes a `.diff` and registers it in `modules.json`.
3. On a later update, the CLI reapplies the patch and tells you if it no longer applies; resolve that then, not by re-editing untracked.
4. Before patching, consider whether the change belongs upstream (`nf-core-module-create` / a PR to nf-core/modules) or can be expressed as `ext.args` — a patch is the last resort, not the first.

## Verification

- `nf-core modules lint <name>` clean for every touched component.
- `modules.json` `git_sha` values updated for exactly the intended components: `git diff modules.json`.
- Existing patches still listed and applying: `nf-core modules list local`.
- Pipeline `-profile test,<backend>` run completes.
- `CHANGELOG.md` records the version bump.

## Notes

- Update one component (or one coherent group) per commit; a bulk `--all` update that breaks something is very hard to bisect otherwise.
- After bumping a tool version, check whether `CITATIONS.md` or the methods description text needs the version updated too.
