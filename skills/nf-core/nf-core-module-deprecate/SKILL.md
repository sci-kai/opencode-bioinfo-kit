---
name: nf-core-module-deprecate
description: 'Deprecate an nf-core module or subworkflow upstream, or cleanly remove one from a pipeline with `nf-core modules remove`. Use when a component is superseded, unmaintained, or no longer used by the pipeline.'
argument-hint: 'Component name, and whether to remove from this pipeline or deprecate upstream'
user-invocable: true
---

# Deprecate or Remove a Component

**Canonical guide:** <https://nf-co.re/docs/developing/components/deprecating-components>

Two different operations — pick the right one:

## A. Remove a component from *this* pipeline

Use when the pipeline stopped using it. The component stays available upstream.

1. Find every reference first: `grep -rn "TOOL_SUBTOOL" workflows/ subworkflows/ conf/ main.nf`
2. Remove the `include` statement and the call from the workflow.
3. Remove its `withName:` block from `conf/modules.config`, and any `params.*` that only existed for it (then rebuild the schema — `nf-core pipelines schema build`).
4. `nf-core modules remove <tool>/<subtool>` — never `rm -rf` the directory; the CLI also updates `modules.json`.
5. Update `CITATIONS.md`, `docs/usage.md`, `docs/output.md`, the methods description text, and `CHANGELOG.md`.
6. `nf-core pipelines lint`, then a `-profile test,<backend>` run.

Verification: `grep -rn "TOOL_SUBTOOL" .` returns nothing outside `CHANGELOG.md`; `modules.json` no longer lists it.

## B. Deprecate a component upstream (nf-core/modules)

Components are **never deleted** upstream — private repositories and other platforms may still
reference them. Mark them deprecated instead.

1. In `main.nf`, add the deprecation message and make the process fail loudly:
   ```groovy
   def deprecation_message = """WARNING: This module has been deprecated.
   Please use nf-core/modules/path/to/new/module
   Reason: <why this module is no longer fit for purpose>
   """
   process OLD_MODULE {
     script:
       assert false: deprecation_message
   }
   ```
2. In `meta.yml`, add `deprecated: true` (this is what marks it deprecated in the nf-core registry and tooling).
3. Rewrite the nf-test: empty the setup block and assert the failure instead of success:
   ```groovy
   then {
     assertAll(
       { assert process.failed },
       { assert process.errorReport.contains("WARNING: This module has been deprecated.") }
     )
   }
   ```
4. Always name the replacement component in the message — a deprecation without a migration path is incomplete.
5. `nf-core modules lint <name>`, run the test, open the PR upstream.

## Notes

- If the pipeline is *using* a component that just got deprecated upstream, the fix is to migrate to the named replacement (`nf-core-module-install` + `nf-core-module-wire-in`), not to pin the old `git_sha`.
