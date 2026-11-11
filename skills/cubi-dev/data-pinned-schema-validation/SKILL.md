---
name: data-pinned-schema-validation
description: 'Vendor an external JSON Schema pinned by tag and sha256, build metadata templates that reference it, validate records before writing, and fail on unfilled placeholders. Use for regulatory/exchange metadata (e.g. a national exchange-format schema), schema upgrades, or when a validator must not silently weaken.'
---

# Pinned schema validation

## Purpose

Produce exchange records (JSON) that provably match one known schema version, and make a schema
update a deliberate, tested step.

## When to use

Generating or checking metadata against an external schema; bumping the schema; writing
templates. Not for pipeline input sheets (`data-samplesheet-schema`).

## Steps

1. Vendor the schema file in `assets/<name>-<tag>.json`. Never fetch at run time (offline HPC).
2. Record the pin in `assets/pins.json`:
   ```json
   {"description": "Pinned versions. Change only together with a tested release.",
    "schema_tag": "v1.2.1", "schema_url": "<raw URL at that tag>",
    "schema_file": "<schema>-v1.2.1.json", "schema_sha256": "<sha256>",
    "tool_x": "1.7.1", "python_min": "3.9"}
   ```
   Every script verifies the file's sha256 and tool versions at start and aborts on mismatch.
3. Templates in `assets/templates/<type>.json`: first key `$schema` set to the pinned URL; static values filled; per-case fields `""`; site IDs as `<placeholder>`. A test asserts all templates reference the pinned tag.
4. Fill templates from config and case data in one function; then (a) scan for leftover `<...>` strings and abort with their JSON paths, (b) validate against the schema, (c) write atomically.
5. Validator: use `jsonschema` if the environment allows. On servers without managed envs, a small stdlib validator is acceptable if it whitelists supported keywords (type, enum, required, properties, items, pattern, minimum, maximum, format date, if/then), treats annotations (`description`, `title`, `$id`, ...) as ignorable, and a unit test fails when the vendored schema uses any other keyword. The upstream tool validates again before submission; never skip it.
6. Error format: `<file>: <JSON path>: expected <rule>, found <value>`; collect all errors, then exit non-zero.
7. Upgrading the schema: new tag, new file, new sha256 in pins, update templates, run validator tests on old and new synthetic records, bump workflow minor/major version (`MAJOR` if outputs change), CHANGELOG entry. Keep the upstream URL in the docs.
8. Derived identifiers (e.g. hashed case IDs): document the exact rule in `docs/output.md` and implement it once.

## Checks before finishing

- Hash check fails when the schema file is altered (test it).
- Placeholder scan fails on a template with a leftover `<...>`.
- A synthetic invalid record fails with the path of the bad field.
- Documentation lists pins and the compatibility table.

## Pitfalls

- Copying the schema without its tag; later nobody knows the version.
- Validator that ignores unknown keywords and silently passes.
- Committing real submitter/site IDs into templates.
