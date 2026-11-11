---
name: nf-core-pipeline-lint
description: 'Run nf-core linting (pipelines/modules/subworkflows, plus prettier/prek formatting) and iteratively fix every error and warning until it passes cleanly, including managing legitimate lint exceptions in .nf-core.yml. Use after any Nextflow change and before any release.'
argument-hint: 'Optional: scope (whole pipeline, or a specific module/subworkflow)'
user-invocable: true
---

# Lint Until Clean

## Commands

```
nf-core pipelines lint                  # whole pipeline
nf-core pipelines lint --release        # stricter, required before a release
nf-core modules lint <tool>/<subtool>   # one module
nf-core modules lint --all              # every vendored module
nf-core subworkflows lint <name>
nf-core pipelines schema lint           # nextflow_schema.json
prettier -w .                           # formatting (or the repo's configured formatter/prek hooks)
```

## Procedure

1. Run the broadest applicable lint and **read the full output**, not just the summary line.
2. Fix errors first, then warnings. Fix them at the source:
   - Schema complaints → `nf-core pipelines schema build`, never a hand edit of `nextflow_schema.json`.
   - Module structure/metadata complaints → fix `meta.yml`/`main.nf`; some are auto-fixable with `nf-core modules lint <name> --fix`.
   - Formatting complaints → run the formatter rather than hand-aligning.
   - Missing docs/CHANGELOG entries → write them; do not silence them.
3. **Re-run the linter after every fix pass.** One fix routinely surfaces or masks another.
4. Repeat until clean, or until a genuine blocker (a missing external dependency, a spec ambiguity only the user can resolve). Do not stop after a single pass and do not report success without a clean re-run whose output you read.

## Legitimate exceptions

Some warnings are intentional for a given pipeline (a deliberately customised template file, a
local module that cannot follow an upstream convention). Record those in `.nf-core.yml` under
the lint section, with a comment stating why. Rules:

- An exception needs a stated reason, and the user's agreement if it is not obviously mechanical.
- Never add an exception to hide a real problem you could fix.
- Never disable a whole lint category to silence one instance.

## Verification

- A final `nf-core pipelines lint` run reports zero errors, and every remaining warning is either explained or declared in `.nf-core.yml`.
- `nf-core modules lint --all` clean for vendored components.
- The formatter produces no further changes (`git diff` empty after re-running it).
- Lint-driven changes did not break tests: re-run the relevant `nf-test` and a `-profile test` run.

## Notes

- Lint output changes after a template sync; a sync is not finished until lint is clean again.
- If the tool version differs from CI's, a rule may exist locally but not remotely (or vice versa) — report the `nf-core --version` you linted with.
