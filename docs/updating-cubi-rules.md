# Updating the CUBI rules

The CUBI knowledge base (<https://github.com/core-unit-bioinformatics/knowledge-base/wiki>)
is the git submodule `cubi-rules/knowledge-base.wiki`. Agents use it in two ways:

| What | File | Kept current by |
|---|---|---|
| Full pages, read on demand | `~/.config/opencode/cubi-kb/{rules,tech,hints}-kb-agents-instructions.md` | **automatic**: every `deploy-configs` regenerates them from the submodule |
| Short digest, loaded into every agent | `cubi-rules/cubi-rules-condensed.md` | **AI-assisted**: when the KB changes, an AI updates it from a generated prompt, and you review the result |

The digest can't be generated mechanically. It condenses the rule pages (9 at the time of
writing) into about 60 lines of instructions that matter to agents, without repeating
`configs/instructions/general-work-rules.md`. That condensing is what the AI does.
`cubi-rules/kb-source.json` records the KB commit the digest was last derived from, so
the kit can tell when it is out of date.

## Workflow

This is for maintainers of the toolkit. Users only get a new digest by pulling the repo and
running `deploy-configs` again.

```bash
codebase/opencode-kit.py check-cubi-digest --fetch     # 1. is the digest current? is upstream newer?
codebase/opencode-kit.py update-git-submodules --only kb      # 2. move the submodule to upstream
codebase/opencode-kit.py update-cubi-digest             # 3. write the AI prompt and show the steps
codebase/opencode-kit.py update-cubi-digest --run       # 4a. let opencode apply it (agent 'build') …
#   … or 4b: open opencode in the repo and type "Follow the instructions in @generated/cubi-digest-update-prompt.md"
#   … or 4c: paste generated/cubi-digest-update-prompt.md into any AI chat, with the digest and the changed pages
git diff cubi-rules/cubi-rules-condensed.md    # 5. review: every changed line must match a KB change
codebase/opencode-kit.py mark-cubi-digest-synced        # 6. record the new KB commit
git add cubi-rules/ && git commit -m "Update CUBI digest to KB <commit>"
codebase/opencode-kit.py deploy-configs kiconnect      # 7. agents get the new digest and KB files
```

`deploy-configs` warns when the digest is out of date, and `check-cubi-digest` exits with code 3, so it
can run in a script or cron job.

## What the generated prompt contains

`generated/cubi-digest-update-prompt.md` (written by `update-cubi-digest`, printed by `print-cubi-digest-prompt`):

- the role of the digest and the limits it must keep: short, imperative, no duplication,
  no invented rules;
- the KB commits since the recorded one;
- the **full diff of the rule pages** (`rules/`), or a list of changed pages when the
  diff is very large;
- the changed tech/hints pages, which are not condensed (the digest only points to them);
- the instruction to edit only the digest, not commit, and list each change as
  `KB page -> digest line`.

`--full` writes a prompt that re-derives the digest from all rule pages instead. Use it
after large reorganisations of the KB.

## Reviewing

- Every added or changed line in the digest must trace back to a KB change in the
  prompt. Delete anything the AI made up.
- Rules that only matter to people (e.g. meeting conventions) don't belong in the digest.
- Keep the digest under about 60 lines: it costs context in every agent call, and local
  models have small contexts.
- If you keep a CUBI digest for another agent tool, update it too. It is a separate digest
  of the same KB.
