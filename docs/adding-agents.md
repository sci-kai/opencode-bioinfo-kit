# Adding or changing an agent

Every agent is one folder, `configs/agents/<name>/`, and works on every backend. Models are never
set per agent: an agent names a **tier**, and each backend maps tiers to models.

```
configs/agents/<name>/
├── agent.json    # required: description, mode, tier (+ optional opencode fields)
└── prompt.md     # optional: the system prompt
```

## Add a subagent in four steps

1. **Create the folder.** The name is lower case, `a-z0-9` and `-` (e.g. `snakemake`).
   Copy a similar agent as a starting point:

   ```bash
   cp -r configs/agents/nf-core-docs configs/agents/snakemake
   ```

2. **Edit `configs/agents/<name>/agent.json`:**

   ```json
   {
     "description": "Snakemake workflow specialist. Use for: writing or fixing Snakefile/.smk rules, conda/apptainer directives, profiles, and snakemake --lint. Not for Nextflow (that is nextflow).",
     "mode": "subagent",
     "tier": "codegen",
     "package": "dev",
     "prompt": "snakemake",
     "steps": 2000
   }
   ```

   | Field | Meaning |
   |---|---|
   | `description` | **Required for subagents.** The orchestrator picks subagents from it alone: say what the agent owns, when to use it, and what goes elsewhere. |
   | `mode` | `subagent` (called by other agents or `@name`), `primary` (Tab-selectable), or `all`. |
   | `package` | Agent package from `configs/agents/packages.json` (`core`, `nf-core`, `dev`, `bioinformatics`, `refdata`, or a new one you add there); selected with `--agents`. |
   | `tier` | `light` (quick tool work), `writing` (documentation prose), `main` (orchestration), `codegen` (multi-file code generation), `careful` (correctness-critical reasoning). |
   | `prompt` | Name of the agent folder whose `prompt.md` is used, normally the agent's own name. Leave it out to use opencode's built-in prompt. |
   | anything else | Passed to opencode 2 unchanged: `steps`, `permissions` (list of `{action, resource, effect}`, appended to the global rules), `hidden`, `color`, … (see <https://opencode.ai/docs/agents/>). opencode 1 fields (`model`, `temperature`, `top_p`, `env`, `tools`, `permission`, `maxSteps`) stop the build with an error, because opencode 2 would silently ignore them. |

3. **Write `configs/agents/<name>/prompt.md`.** Follow the existing prompts:
   - a one-line role, then **Scope** (what it owns, what it hands back);
   - **Hard constraints** (tool rules, what never to do);
   - a **Working procedure** and a **Definition of done**;
   - the two-line pointer to the global rules, not a copy of them:
     `Global rules (configs/instructions/general-work-rules.md) apply, incl. "denials are not
     stopping points" and "never stop early".`
   - Keep it short. Every line costs context on every call, and local models have little.

4. **Route to it and deploy:**
   - add a row to the routing table `configs/agents/build/routing.json` (`{"task": "…", "agent": "<name>"}`)
     and, if needed, a tie-breaker naming it in backticks. opencode-kit renders the table into the
     orchestrator prompt with only the installed agents, so `build`/`general` know when to delegate;
   - if it owns skills, name them in its prompt and description;
   - build and install:

     ```bash
     codebase/opencode-kit.py preview-configs              # validates, writes generated/ for review
     codebase/opencode-kit.py deploy-configs kiconnect   # installs and tests
     opencode debug agents --standalone   # check model, variant and system prompt text
     ```

## Change which model an agent uses

- **All agents of a tier, one backend:** edit `tiers.<tier>.model` in
  `configs/backends/<backend>/backend.json`.
- **One agent, one backend:** add `"<name>": "<tier>"` to `agent_tiers` in that
  `backend.json` (e.g. the local backend runs `nextflow-lint` on `light`).
- **One agent, all backends:** change `tier` in its `agent.json`.

The model must be declared under `providers.<id>.models` of the backend, or the build stops.
A tier's `temperature`/`top_p` become a model variant (`model#t0.6-p0.95`) automatically,
because opencode 2 has no per-agent sampling.

## Add a skill

Skills are procedures an agent loads on demand (`skills/<group>/<name>/SKILL.md`, e.g. `skills/nf-core/<name>/SKILL.md`). The frontmatter
needs `name:` (equal to the folder name) and `description:` (1–1024 characters).
`codebase/opencode-kit.py deploy-configs` / `install-skills` validate and install them (see [skills.md](skills.md)). Name the skill in the owning agent's prompt
table and description.

## Add a backend

Copy `configs/backends/kiconnect/` to `configs/backends/<new>/`, then change `name`, `providers`
(exactly one; opencode 1 keys `provider`, `npm`, `options` stop the build), the `tiers`
models, sampling and `compaction`. `opencode-kit.py` picks up every
`configs/backends/*/backend.json` automatically, and `codebase/opencode-kit.py deploy-configs <new>` installs it. Every tier
used by an agent must be defined.

## What the generator checks

`codebase/opencode-kit.py preview-configs` (and `deploy-configs`) stop with an `ERROR:` naming the file when:

- a JSON file does not parse (e.g. a trailing comma);
- an agent has no `tier`, or a subagent has no `description`;
- an agent sets `model`/`temperature`/`top_p`;
- a `prompt` reference has no `prompt.md`, or a `prompt.md` belongs to no agent;
- a tier is missing in a backend, or a tier's model is not declared by the provider;
- `agent_tiers` names an unknown agent.

Run `codebase/opencode-kit.py preview-configs` before committing.
