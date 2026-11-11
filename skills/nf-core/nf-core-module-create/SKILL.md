---
name: nf-core-module-create
description: 'Create a new nf-core module or subworkflow from scratch with `nf-core modules create` / `nf-core subworkflows create`, including main.nf, meta.yml, environment.yml, container directive and nf-test. Use when a needed tool has no upstream nf-core component, or when contributing a new component to nf-core/modules.'
argument-hint: 'Tool name (and subtool), plus whether it is local-only or for upstream contribution'
user-invocable: true
---

# Create an nf-core Module or Subworkflow

**Canonical guides:**
<https://nf-co.re/docs/developing/components/creating-components> and the tutorial chapters at
<https://nf-co.re/docs/developing/tutorials/writing-nf-core-modules/1-introduction>

Read the relevant chapter when a convention is unclear — module structure is strictly linted
and guessing costs more than looking it up.

## Step 0 — decide local vs upstream

- **Upstream (nf-core/modules):** the tool is generally useful. Work in a fork/clone of `nf-core/modules`, on a branch named after the component. `nf-core modules test` and the contribution flow only work in a modules repository, not inside a pipeline.
- **Local (`modules/local/`):** the tool is pipeline-specific, wraps in-house code, or cannot be published. Same file structure and same linting standard — "local" is not an excuse for a non-conforming module.

Ask the user which one is intended if the request does not say.

## Preconditions

- Nextflow ≥ 21.04, nf-core/tools ≥ 2.7, `nf-test`, and a container engine (docker/singularity) or conda — all inside the conda environment.
- Confirm the component does not already exist: `nf-core modules list remote | grep -i <tool>`, plus a check of open PRs/issues on nf-core/modules for upstream work.

## Procedure

1. Branch: `git checkout -b <component-name>`
2. Scaffold:
   - `nf-core modules create` (or `nf-core modules create <tool>/<subtool>`)
   - `nf-core subworkflows create` for subworkflows
   This generates `environment.yml`, `main.nf`, `meta.yml`, `tests/main.nf.test`.
3. **`main.nf`** — work through every `TODO` the generator left, and remove each TODO comment once resolved:
   - `tag "${meta.id}"`, `label` a standard resource label.
   - Inputs as `tuple val(meta), path(...)` — see `nf-core-meta-map`.
   - `def args = task.ext.args ?: ''` and `def prefix = task.ext.prefix ?: "${meta.id}"`; every optional flag goes through `$args`, never hardcoded.
   - Emit versions (topic channel form on tools ≥ 3.5.0 — see `nf-core-migrate-topic-channels`).
   - Provide a `stub:` block producing empty outputs and the version.
4. **`environment.yml`** — pin the tool with a bioconda/conda-forge channel prefix and an exact version. One tool plus its dependencies; do not bundle unrelated tools.
5. **Container directive** — generate Docker and Singularity URIs via Seqera Containers; see `nf-core-container-uri` for the exact directive syntax and its formatting rules.
6. **`meta.yml`** — complete every field: description, keywords, tools (with `homepage`, `documentation`, `doi`/`licence`), and a full description + pattern for each input and output channel. Lint fails on omissions here.
7. **`tests/main.nf.test`** — see `nf-core-nf-test`. Minimum: process success plus a versions snapshot; add real output assertions and, where the data supports it, both single-end and paired-end cases.
8. **Lint** until clean: `nf-core modules lint <name>` / `nf-core subworkflows lint <name>`.
9. **Test**: `nf-core modules test <name>` (modules repository only) or `nf-test test modules/local/<name>/tests/main.nf.test --profile <docker|singularity|conda>` for a local module.

## Verification

- Lint clean, tests pass, snapshot file committed.
- No `TODO` strings remain: `grep -rn "TODO" <component-dir>`.
- The stub path runs: `nf-test test ... --profile docker` with `-stub` where applicable.

## Notes

- GPU-capable tools: read `nf-core-gpu-module` before writing the container/accelerator logic.
- Do not create a module whose only difference from an existing one is a fixed argument — configure it via `ext.args` instead.
