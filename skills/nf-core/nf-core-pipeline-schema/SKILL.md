---
name: nf-core-pipeline-schema
description: 'Add, change, or remove a pipeline parameter and regenerate nextflow_schema.json with `nf-core pipelines schema build/docs/lint`. Use for any params change — nextflow_schema.json must never be hand-edited.'
argument-hint: 'Parameter name, type, default, and what it controls'
user-invocable: true
---

# Pipeline Parameters and Schema

`nextflow_schema.json` is a **generated file**. If you are about to open it in an editor for
anything other than reading, stop and use the CLI.

## Procedure

1. Make the change where it actually belongs — the `params { }` block in `nextflow.config`:
   - add the parameter with a sensible default (`null` if genuinely required from the user),
   - keep naming consistent with existing parameters (snake_case, no abbreviations that aren't already used).
2. Wire it into behaviour, normally through `ext.args` in `conf/modules.config` (see `nf-core-ext-args`) rather than by branching in workflow code.
3. Regenerate the schema:
   ```
   nf-core pipelines schema build
   ```
   This walks you through the new/changed entry interactively: set the **type**, **description**, **help text**, whether it is **required**, `enum` values where the input is constrained, and `format` (`file-path`, `directory-path`, `path`) for anything that is a path — the format is what gives users an early, readable validation error instead of a mid-run crash.
4. Regenerate parameter docs: `nf-core pipelines schema docs`
5. Validate: `nf-core pipelines schema lint`
6. Document it in `docs/usage.md` with at least one realistic command example, and add a `CHANGELOG.md` entry.

## Removing a parameter

Delete it from `nextflow.config`, remove every reference (`grep -rn "params.<name>" .`), rebuild
the schema, and note the removal in `CHANGELOG.md` — a removed parameter is a breaking change
for users and must be visible in the release notes.

## Verification

- `nf-core pipelines schema lint` clean and `nf-core pipelines lint` clean.
- `git diff nextflow_schema.json` shows only the intended entry — a huge diff means the schema was regenerated with a different tools version; check `nf-core --version` before committing it.
- Parameter names/types/defaults in `docs/usage.md` match the schema exactly.
- A `-profile test` run still validates: pass the new parameter once explicitly and once omitted, to confirm the default and any required-ness behave as intended.

## Notes

- Never document a parameter that is not implemented, and never implement one that is not in the schema — the two must not drift.
- Parameters that only exist to pass a flag to one tool are usually better expressed as `ext.args`; add a real parameter only when a typical user needs to change it.
