# opencode-config

An [opencode](https://opencode.ai/docs) 2 agent setup and deployment toolkit for
bioinformatics, nf-core and CUBI-style development. Any user can clone it and deploy it for
themselves. One set of agents runs on two model backends:

- **KI Connect NRW**: for members of NRW universities with access. Qwen3.8 27B for all main
  and heavy work, GPT OSS 120B and Mistral Small 4 for light tasks and documentation.
- **Local LM Studio**: for any user with an LM Studio server. You choose any models the
  server offers: two (heavy + fast), one per tier, plus extras to switch to by hand; or you
  write the model set as a file. A real example set (Qwen3.5 9B + Qwen3.8 27B on a 16 GB GPU
  host) ships in `configs/backends/local/lmstudio-models.example.json`.

Maintained by Kai Horny (CUBI, HHU).

## Quick start

For bioinformaticians and teams (CUBI-style or any institution) who want a ready-made,
sandboxed opencode setup with agents, skills and the CUBI rules. Linux, macOS and HPC login
nodes work. You need no sudo.

**Prerequisites**

- `git`, `bash`, `curl` (for the opencode installer) and Python 3.8 or newer. The kit uses
  only the Python standard library.
- One model backend:
  - **KI Connect NRW**: an account at <https://chat.kiconnect.nrw> and an API key, or
  - **Local LM Studio**: a running LM Studio server with at least one chat model that
    supports tool calls.

**1. Clone with the submodules**

```bash
git clone --recurse-submodules <repo-url> ~/Projects/opencode-config
# cloned without --recurse-submodules?
git -C ~/Projects/opencode-config submodule update --init
```

**2. Run the setup for your backend**

```bash
~/Projects/opencode-config/codebase/opencode-kit.py setup-opencode kiconnect   # KI Connect NRW
~/Projects/opencode-config/codebase/opencode-kit.py setup-opencode local       # local LM Studio
exec $SHELL -l    # first install only: reload PATH so that `opencode` is found
```

`setup-opencode` installs opencode 2 if it is missing, deploys the config, and tests it. It asks
once per user (answers are saved in `~/.config/opencode/opencode-kit-settings.json`, never in the repo):

- **Folders** outside the project that opencode may use: conda envs, scratch, temp and extra
  folders. Everything else is denied.
- **Agent packages** (`core` is always installed; `nf-core`, `dev`, `bioinformatics`, `refdata` are optional; `refdata` needs the external seqc2-toolkit, not included).
- **Skills** (default `nf-core,cubi-dev`).
- **KI Connect**: the API key (input hidden). **LM Studio**: the server URL, then the
  models for your *model set* and the context length each one is loaded with.

Without a terminal (servers, CI), pass the answers as flags. See
[docs/deploy.md](docs/deploy.md).

**3. Verify**

```bash
~/Projects/opencode-config/codebase/opencode-kit.py test-deployment          # offline checks
~/Projects/opencode-config/codebase/opencode-kit.py test-deployment --live   # plus one real model call
```

Setup and deploy run the offline test automatically (add `--live` to include the model call).

**4. Use it**

```bash
cd ~/Projects/<some-project> && opencode
```

**The checkout must stay where it is.** The deployed config points to the agent prompts and
rules inside this checkout. If you move or rename the folder, run `deploy-configs <backend>`
again from the new place. After `git pull --recurse-submodules`, also run `deploy-configs <backend>`.

Details, options, updating, uninstalling and troubleshooting: [docs/deploy.md](docs/deploy.md).

## The toolkit: `codebase/opencode-kit.py`

| Command | Does |
|---|---|
| `setup-opencode <backend>` | install opencode 2 + API key + `deploy-configs` (fresh machine) |
| `deploy-configs <backend>` | write `~/.config/opencode/opencode.json`, KB files and skills, then `test-deployment` |
| `test-deployment [--live]` | check the deployment, including a real session and optionally a model call |
| `preview-configs` | generate the configs and KB files into `generated/` and validate all skills, without installing anything (to review a change) |
| `configure-directories` | state which folders outside the project opencode may use (conda, envs, scratch, temp, extra); everything else is denied |
| `configure-lmstudio` | choose the LM Studio model set: from the server's list (heavy/fast or per tier, extras) or a hand-written file (`--models-file`); `--show`, `--export` |
| `list-agents` | agent packages (core, nf-core, dev, bioinformatics, refdata); choose with `--agents` on setup/deploy |
| `list-skills` / `install-skills --skills …` | choose nf-core / cubi-dev / refdata / BioNeMo skills |
| `check-cubi-digest` / `update-cubi-digest [--run]` / `mark-cubi-digest-synced` | keep the CUBI digest in line with the knowledge base (AI-assisted) |
| `update-git-submodules` | move the submodules (knowledge base, BioNeMo toolkit) to upstream |

## Documentation

| Document | Content |
|---|---|
| [docs/deploy.md](docs/deploy.md) | Install, deploy, test and troubleshoot, from scratch to the first session |
| [docs/skills.md](docs/skills.md) | Skill groups (nf-core, BioNeMo), selection, install, adding a skill |
| [docs/updating-cubi-rules.md](docs/updating-cubi-rules.md) | Keeping the CUBI digest current when the knowledge base changes |
| [docs/adding-agents.md](docs/adding-agents.md) | Adding a subagent, changing models per tier, adding a backend |
| [docs/kiconnect-models.md](docs/kiconnect-models.md) | KI Connect deployments, limits, speed, tier routing |
| [docs/lmstudio-model-settings.md](docs/lmstudio-model-settings.md) | LM Studio load and sampling settings, worked example for one 16 GB GPU host |
| [docs/upgrading-from-opencode-1.md](docs/upgrading-from-opencode-1.md) | One-way upgrade from opencode 1, v1→v2 schema mapping |

Instructions loaded by every agent:
[configs/instructions/general-work-rules.md](configs/instructions/general-work-rules.md),
[configs/instructions/coding-and-data-standards.md](configs/instructions/coding-and-data-standards.md)
(Python, data and testing defaults) and the CUBI digest [cubi-rules/cubi-rules-condensed.md](cubi-rules/cubi-rules-condensed.md).

## Layout

| Path | Content |
|---|---|
| `configs/agents/<name>/` | one folder per agent: `agent.json` (description, mode, tier) + `prompt.md` |
| `configs/backends/<backend>/backend.json` | provider, tier → model and sampling, per-agent overrides |
| `configs/shared/` | `base.json` (global instructions) and `permissions.json`, the same for every backend |
| `configs/instructions/` | global agent rules (`general-work-rules.md`, `coding-and-data-standards.md`) |
| `cubi-rules/` | CUBI digest, `kb-source.json` (the KB commit the digest comes from), `knowledge-base.wiki/` (submodule) |
| `skills/nf-core/`, `skills/cubi-dev/`, `skills/refdata/` | self-made skills (nf-core procedures; Python, data, testing procedures; reference data and benchmarking, needs the external seqc2-toolkit) |
| `skills/bionemo-agent-toolkit/` | NVIDIA BioNeMo agent skills (submodule) |
| `codebase/` | `opencode-kit.py` and its library `kitlib/` |
| `docs/` | documentation (table above) |
| `generated/` | review output of `opencode-kit.py preview-configs` (gitignored) |

The generated `opencode.json` is not stored in the repo: `deploy-configs` produces it from
`configs/`, and `preview-configs` writes a copy for review.

## Agents

| Agent | Tier | Role |
|---|---|---|
| `build`, `general` | main | Orchestrator: plans, delegates, verifies, commits (routing table in `configs/agents/build/routing.json`, rendered for the installed agents) |
| `plan` | careful | Read-only planning (opencode built-in prompt) |
| `explore`, `title`, `summary` | light | opencode built-ins |
| `conda-agent` | light | Conda environments, never `.venv` |
| `bioinformatics-agent` | careful | Correctness-critical genomic file-format code and statistics |
| `python-dev` | codegen | Python scripts, tools and packages: structure, CLI, errors, style, packaging, provenance |
| `data-formats` | careful | How data is stored: formats, configs and secrets, schemas, state/backups, checksums, output docs |
| `test-design` | careful | Test tiers, use cases, synthetic data, failure-path and regression tests, test reports |
| `refdata` | careful | Package `refdata`: SEQC2/GIAB reference samples, test data with the external seqc2-toolkit (install separately), benchmarking against truth sets |
| `debug-agent` | careful | Error diagnosis, using the CUBI hints first |
| `paper-writing` | careful | Methods sections from the run's versions and parameters |
| `nextflow` | codegen | Nextflow/nf-core fallback: workflows, configs, architecture |
| `nextflow-lint` | careful | Independent lint gate after every pipeline change |
| `nf-core-template`, `-modules`, `-testing`, `-migration` | codegen | nf-core specialists owning the matching skills |
| `nf-core-release` | careful | Release preparation (never tags or publishes) |
| `nf-core-docs` | writing | Pipeline documentation |

## License

The toolkit (code, configs, prompts, own skills, docs) is MIT licensed, see [LICENSE](LICENSE).
Exceptions keep their own licenses:

- `cubi-rules/knowledge-base.wiki/` (submodule): CUBI knowledge base, Core Unit
  Bioinformatics, Medical Faculty, HHU, CC BY-NC-SA 4.0.
- `cubi-rules/cubi-rules-condensed.md`: derived from that knowledge base, so also
  CC BY-NC-SA 4.0 (attribution: CUBI knowledge base).
- `skills/bionemo-agent-toolkit/` (submodule): NVIDIA BioNeMo agent toolkit, Apache-2.0 for
  code and CC BY 4.0 for content, see its `LICENSE`.
