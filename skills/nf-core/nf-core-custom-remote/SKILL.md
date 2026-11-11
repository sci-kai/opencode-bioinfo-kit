---
name: nf-core-custom-remote
description: 'Install, update, or list nf-core modules and subworkflows from a custom or private git remote (e.g. an institution's own (e.g. GitLab) modules repository) using --git-remote/--branch and .nf-core.yml org_path. Use when components do not come from nf-core/modules.'
argument-hint: 'Remote URL, branch, and component name'
user-invocable: true
---

# Custom / Private Module Remotes

**Canonical guide:** <https://nf-co.re/docs/developing/components/custom-remotes>

## When to use

- The pipeline consumes modules from an in-house/institutional modules repository.
- `modules.json` shows a remote other than `https://github.com/nf-core/modules.git`.
- A module install must come from a private GitLab/GitHub repository.

## Flags

- `--git-remote <url>` — repository to fetch components from.
- `--branch <name>` — branch to use (defaults to the remote's default branch).
- `--no-pull` — skip pulling remote changes (offline work, or to avoid a slow refresh).

Both flags go **before** the subcommand:

```
nf-core modules --git-remote git@gitlab.com:<org>/<modules-repo>.git install fastqc
nf-core subworkflows --git-remote git@gitlab.com:<org>/<modules-repo>.git --branch subworkflows install bam_stats_samtools
```

The same flags apply to `list`, `update`, `remove`, `lint`, and `patch` — use them consistently,
or the CLI will look the component up against nf-core/modules and report it as missing.

## Repository layout

If components live in a subdirectory (`modules/<org-folder>/TOOL/SUBTOOL`), declare it in
`.nf-core.yml` so the CLI resolves paths without prompting:

```yaml
org_path: <org-folder>
```

## Authentication

Private remotes rely on your existing local git configuration — SSH key or credential helper.
Configure and test git access first (`git ls-remote <url>`); the nf-core CLI does not prompt for
credentials and will simply fail. Never embed a token in a command, a config file, or the
session command log.

## Verification

- `modules.json` records the correct `git_url` and `branch` for the component.
- `nf-core modules --git-remote <url> list local` shows the expected set.
- A `-profile test` run resolves the module.

## Notes

- Mixed remotes in one pipeline are supported — `modules.json` groups components per remote. Keep nf-core components on the nf-core remote rather than forking them, and use `nf-core-module-update`'s patch mechanism for local changes.
- CUBI repositories may have several push targets; confirm which remote is the *modules* source before assuming it is `origin`.
