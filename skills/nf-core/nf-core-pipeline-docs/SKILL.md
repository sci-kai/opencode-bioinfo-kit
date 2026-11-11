---
name: nf-core-pipeline-docs
description: 'Keep nf-core pipeline documentation in sync with the code: README, docs/usage.md, docs/output.md, CITATIONS.md, CHANGELOG.md, and the automated MultiQC methods description text. Use whenever pipeline behaviour, parameters, outputs, or tool set change.'
argument-hint: 'What changed in the pipeline'
user-invocable: true
---

# Documentation and Citation Sync

**Canonical guides:** <https://nf-co.re/docs/developing/documentation/style-guide> and
<https://nf-co.re/docs/developing/components/automated-methods-text>

Documentation is part of the implementation, not a follow-up. Go through every file below; if
one genuinely needs no change, say so explicitly rather than skipping it silently.

## Files

| File | Update when |
|---|---|
| `README.md` | User-visible behaviour changed; keep example commands and links to `docs/usage.md` / `docs/output.md` accurate |
| `docs/usage.md` | New/changed parameters, defaults, required-ness, input expectations (samplesheet columns, file types, reference resources) — with at least one realistic command example |
| `docs/output.md` | New/changed output paths and file patterns, and how outputs feed MultiQC; delete descriptions of outputs that no longer exist |
| `docs/README.md` | A docs page was added or removed |
| `CITATIONS.md` | A new tool, algorithm, or external workflow component was added — canonical citation text plus a DOI/URL you verified resolves |
| `CHANGELOG.md` | Every feature, fix, parameter, output, and dependency bump |

## Automated methods description text

The MultiQC report ends with an "*\<pipeline\> Methods description*" section, generated from:

- `assets/methods_description_template.yml` — the MultiQC-compatible template holding run metadata and the nf-core/Nextflow citations, with `"${tool_citations}"` and `"${tool_bibliography}"` placeholders;
- `subworkflows/local/utils_nfcore_<pipeline>_pipeline/main.nf` — the functions `toolCitationText()` and `toolBibliographyText()` that fill those placeholders conditionally on the parameters used.

To add a tool: extend `toolCitationText()` with the conditional sentence, add the matching
`<li>` entry to `toolBibliographyText()`, and make sure the two lines assigning
`meta["tool_citations"]` and `meta["tool_bibliography"]` are uncommented — they ship commented
out in the template and the section stays empty until they are enabled.

Locate the subworkflow path in the repository rather than assuming the pipeline name; every
citation added here must also exist in `CITATIONS.md`.

## Consistency rules

- Parameter names, types, and defaults in docs must match `nextflow.config` and `nextflow_schema.json` **exactly**. Regenerate parameter docs with `nf-core pipelines schema docs` rather than writing them by hand.
- Never document an input, output, or parameter that is not implemented.
- Keep the tool list consistent across `CITATIONS.md`, the methods text, `README.md`, and any workflow diagram.

## Verification

- `nf-core pipelines lint` (it checks for several of these files and their contents).
- Every link and DOI added actually resolves.
- `grep -rn "<removed-param>" docs/ README.md` returns nothing after a removal.
- A `-profile test` run's MultiQC report contains the methods section with the expected citations.
