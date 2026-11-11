# Skills

Skills are step-by-step procedures that an agent loads on demand. opencode lists every
installed skill (ID and description) to the model, and the model loads the full text with
the `skill` tool when a task matches. This repo ships two collections:

| Group | Source | Skills |
|---|---|---|
| `nf-core` | `skills/nf-core/<id>/SKILL.md`, written for this setup from <https://nf-co.re/docs/developing> | 25: template sync, module lifecycle, nf-test, lint, release, migrations, … |
| `cubi-dev` | `skills/cubi-dev/<id>/SKILL.md` | 23: Python scripts/tools (`python-*`), data storage and formats (`data-*`), test design (`test-*`) |
| `refdata` | `skills/refdata/<id>/SKILL.md`, optional (agent package `refdata`); needs the external seqc2-toolkit, which is not included | 8: SEQC2/GIAB test data, dataset preparation and downsampling, truth-set benchmarking, offline transfer (`refdata-*`) |
| `bionemo` | `skills/bionemo-agent-toolkit/` (git submodule of [NVIDIA-BioNeMo/bionemo-agent-toolkit](https://github.com/NVIDIA-BioNeMo/bionemo-agent-toolkit), Apache-2.0 / CC-BY-4.0) | 34, in four sub-groups (below) |

| Sub-group | Folder in the toolkit | Skills | Needs |
|---|---|---|---|
| `bionemo-nim` | `nim-skills/` | 12: Boltz-2, DiffDock, Evo 2, GenMol, MolMIM, OpenFold2/3, ProteinMPNN, RFdiffusion, MSA search, pipelines | `NVIDIA_API_KEY` (hosted NIMs on build.nvidia.com) or `NGC_API_KEY` plus a GPU for local NIM containers |
| `bionemo-library` | `library-skills/` | 4: Parabricks, genomics workflow acceleration, cuEquivariance, nvMolKit | NVIDIA GPU, the library installed |
| `bionemo-open-models` | `open-models-skills/` | 14: Proteina-Complexa, KERMT | GPU, model setup (the skills explain it) |
| `bionemo-workflows` | `workflows/` | 4: protein binder design | as the skills they combine |

The toolkit's `plugins/` folder repeats the same skills for other agent tools and is
ignored.

## Choosing and installing

```bash
codebase/opencode-kit.py list-skills                              # catalog; * = installed
codebase/opencode-kit.py deploy-configs kiconnect --skills nf-core,bionemo-nim
codebase/opencode-kit.py install-skills --skills nf-core          # skills only, config untouched
codebase/opencode-kit.py install-skills --skills none             # remove all kit-installed skills
```

A selection is a comma-separated list of **groups** (`nf-core`, `cubi-dev`, `refdata`, `bionemo`,
`bionemo-nim`, `bionemo-library`, `bionemo-open-models`, `bionemo-workflows`, `all`),
single **skill IDs** (e.g. `evo2-nim`), or `none`.

If `--skills` is not given, `deploy-configs` and `setup-opencode` reuse the previous selection. On the
first run they ask in the terminal. Without a terminal they install the skill groups of the
chosen agent packages (`nf-core,cubi-dev,refdata` for `--agents all`).
A previous selection does not include groups added later: pass e.g.
`--skills nf-core,cubi-dev,bionemo-nim` once to add `cubi-dev`.

Installed layout (opencode 2 allows grouping folders):

```
~/.config/opencode/skills/
├── nf-core/<id>/SKILL.md
├── cubi-dev/<id>/SKILL.md
├── refdata/<id>/SKILL.md
├── bionemo/<id>/SKILL.md
└── .opencode-kit.json        # what the kit installed, and the selection
```

The kit removes only skills listed in its manifest, so skills you installed by hand stay.
It also cleans up the flat `~/.config/opencode/skills/nf-core-*` copies of the old layout.
opencode 2 doesn't read the old opencode 1 folder `~/.opencode/skills`; delete it if it
still exists.

Every skill is installed as its own folder. When a skill folder contains further skills
(the binder-design workflow does), those are installed separately. Inside another
skill's folder, opencode would not find them.

## Testing

`codebase/opencode-kit.py test-deployment` (also run by `deploy-configs`) starts one real opencode session
against a local fake model endpoint. It then checks that every installed skill appears in
the model's `<available_skills>` list. No API key is needed, and your sessions are not
touched. The check exists because the server's skill listing (`GET /api/skill`) does not
show global skills in a one-shot call (opencode 2.2.6).

## Updating the bionemo skills

```bash
codebase/opencode-kit.py update-git-submodules --only bionemo     # move the submodule to upstream
codebase/opencode-kit.py deploy-configs kiconnect          # reinstall the selected skills
git add skills/bionemo-agent-toolkit && git commit -m "Update bionemo-agent-toolkit"
```

## Adding a skill

Every folder under `skills/` (except the BioNeMo submodule) is a group; a new folder is a
new selectable group, no code change needed.

1. Create `skills/<group>/<id>/SKILL.md` (e.g. `skills/cubi-dev/…`). `<id>` is lower-case kebab-case, at most 64
   characters, and equals the frontmatter `name:`. Add a `description:` (at most 1024
   characters) that says when to use the skill. The kit enforces these rules for its own
   skills.
2. Link the nf-co.re page it is derived from, as the existing skills do.
3. Name the skill in the prompt and description of the agent that owns it
   (`configs/agents/nf-core-*/`).
4. `codebase/opencode-kit.py preview-configs`, then `deploy-configs`.
