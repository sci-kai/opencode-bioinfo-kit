---
name: nf-core-migrate-topic-channels
description: 'Migrate modules and pipelines from versions.yml collection to Nextflow topic channels for version reporting (nf-core/tools ≥ 3.5.0, Nextflow ≥ 25.04.0). Use when updating to a topic-channel template or when a module still emits versions.yml.'
argument-hint: 'Module or pipeline to migrate'
user-invocable: true
---

# Migrate to Topic Channels

**Canonical guide:** <https://nf-co.re/docs/developing/migration-guides/update-pipelines>

## Requirements

- nf-core/tools ≥ 3.5.0
- Nextflow ≥ 25.04.0
- For module work: a clone of the modules repository the components come from

Check both versions first (`nf-core --version`, `nextflow -version`) — attempting this on older
versions produces confusing runtime errors rather than a clear failure.

## Module changes

**Standard (tool-wrapping) modules:**

1. Remove the `versions.yml` generation block from the script section.
2. Emit versions as a structured tuple on the `versions` topic:
   ```groovy
   tuple val("${task.process}"), val('<tool>'), eval('tool1 --version'), emit: versions_tool1, topic: versions
   ```
3. Auto-update the metadata: `nf-core modules lint <module-name> --fix`

**Constraint:** a topic value cannot come from an intermediate variable — `def tool_version =
'1.2.3'` then using `tool_version` will not work. Use the `eval()` form, or a hard-coded literal
where the version cannot be queried at runtime.

**Template-generated modules:** usually just add the topic to the existing emission —
`path "versions.yml", emit: versions` becomes the same declaration with `topic: versions`.

## Pipeline changes

1. Bring the pipeline to template version 3.5.0+ (`nf-core-template-sync-run`) — the template
   ships the channel-topic branching that separates file-based from tuple-based version outputs.
2. Add the topic-channel processing logic in the main workflow if the sync did not supply it.
3. Remove every direct reference to a module's versions output (`SAMTOOLS_SORT.out.versions`,
   `ch_versions = ch_versions.mix(...)`) — these no longer exist under topics:
   ```
   grep -rn "\.out\.versions" workflows/ subworkflows/ main.nf
   ```

## Testing

Regenerate snapshots after migrating, since the versions output shape changed:

```
nf-core modules test <module-name> --update
nf-test test --profile <backend> --update-snapshot
```

Review each snapshot diff — you are expecting version-channel restructuring and nothing else.

## Verification

- `nf-core pipelines lint` and `nf-core modules lint --all` clean.
- A `-profile test,<backend>` run completes and the software-versions section of the MultiQC report still lists every tool that ran.
- No `.out.versions` references remain.
- `CHANGELOG.md` notes the migration.

## Notes

- Migrate the whole pipeline in one coherent change. A half-migrated pipeline silently loses tools from the versions report, which is easy to miss because nothing fails.
