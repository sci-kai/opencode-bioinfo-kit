# Deploying opencode with this configuration

From a clean machine to a running opencode session, with **KI Connect NRW** (for
members of NRW universities with access) or **local LM Studio models**. Requires **opencode 2**; for 1.x see
[upgrading-from-opencode-1.md](upgrading-from-opencode-1.md). Everything runs through
one script, `codebase/opencode-kit.py` (Python ≥ 3.8, standard library only).

## Prerequisites

- **System**: Linux or macOS (WSL works; native Windows does not). HPC login nodes are fine
  if they can reach the opencode installer and your model backend. No sudo is needed;
  everything goes into your home folder.
- **Tools on `PATH`**: `git`, `curl`, `bash`, and `python3` (3.8 or newer). The kit checks
  this and stops with a hint if one is missing.
- **A model backend**, one of:
  - KI Connect NRW: an account at <https://chat.kiconnect.nrw> and an API key
    (section 3a).
  - LM Studio: a running server with a chat model that supports tool calls, reachable from
    the machine that runs opencode (section 3b).
- **Network**: the installer (`opencode.ai`) and, for KI Connect, `chat.kiconnect.nrw`.

## Quick start: one command

```bash
git clone --recurse-submodules <this-repo-url> ~/Projects/opencode-config
~/Projects/opencode-config/codebase/opencode-kit.py setup-opencode kiconnect
exec $SHELL -l                     # reload PATH (first install only)
cd ~/Projects/<some-project> && opencode
```

`setup-opencode` runs, in order:

1. **checks** prerequisites and initialises the submodules (CUBI knowledge base, BioNeMo
   skills) if the clone was made without `--recurse-submodules`;
2. **installs opencode 2** if it is missing, using the official installer into
   `~/.opencode/bin`. An installed opencode 2 is kept, and an installed 1.x stops with a
   hint;
3. **asks which folders outside the project opencode may use** (section "Directories" below), saved per user;
4. **asks for the API key** (input hidden) and checks it against
   `https://chat.kiconnect.nrw/api/v1/models`, including that every model the config uses
   is offered. It then stores the key with `opencode auth import`;
5. **deploys** (section 4): config, CUBI KB files, the skills you select;
6. **tests** the deployment (section 5).

Options of `setup-opencode` (and `deploy-configs`):

| Option | Effect |
|---|---|
| `--envs-dir`, `--scratch-dir`, `--scratch-mount`, `--conda-base`, `--tmp-dir`, `--extra-dir` (repeatable), `--lmstudio-url` | Directories without the questions (servers); saved per user |
| `--agents nf-core,dev,bioinformatics,refdata` | Agent packages (`list-agents`; `refdata` needs the external seqc2-toolkit, not included); `core` is always installed; default: previous selection, else ask, else `all`. The orchestrator's routing table lists only the installed agents |
| `--skills nf-core,cubi-dev,bionemo-nim` | Skill selection ([skills.md](skills.md)); default: previous selection, else ask in a terminal, else the skill groups of the chosen agent packages (`nf-core,cubi-dev` if none) |
| `--live` | Also test a real model call |
| `--no-test` | Skip the test |
| `--dry-run` | Show what would happen, change nothing |
| `--opencode-version 2.2.6` | (setup) install this exact version instead of the newest |
| `--upgrade-from-v1` | (setup) replace an installed opencode 1; one-way |
| `--api-key-env VAR` | (setup) read the key from an environment variable, e.g. on servers |
| `--replace-key` / `--no-key` | (setup) store a new key / skip the key step |

Server example: `KI_CONNECT_API_KEY=… codebase/opencode-kit.py setup-opencode kiconnect --api-key-env KI_CONNECT_API_KEY --skills nf-core,cubi-dev`.

The sections below explain each step, for manual installs and troubleshooting.

## What agents may and may not do

The rules live in `configs/shared/permissions.json` and are the same for every backend.
In short:

- **May**: read and edit files in the project folder opencode runs in and in the folders
  you granted (conda, envs, scratch, temp, extra). Use this toolkit checkout and opencode's
  config folder (read only), `~/.conda`, `~/.nextflow`, `~/.singularity` and `~/.apptainer`.
- **May not**: use any other folder outside the project (denied by the first permission rule);
  read or edit credentials (`.ssh`, `.aws`, `.gnupg`, `.env`, `.netrc`, `.git-credentials`,
  opencode's `auth.json` and `opencode.db`); edit opencode's config folder, a project-level
  `.opencode/` folder, `opencode.json(c)`, or this toolkit's `configs/` and `codebase/`.
- **Denied shell commands**: `sudo`, `git push`, history rewriting, recursive deletes and
  similar. The agent then asks you to run them yourself.

This is a safety net against slips, not a sandbox: it matches command text and folder names,
and an agent with shell access can still do harm in the folders it may use. Run opencode in
a project you can restore from git, and keep backups of data.

## Directories: strict access

opencode may only use the project folder it runs in, plus:

| Always | Granted by you (asked once, saved in `~/.config/opencode/opencode-kit-settings.json`) |
|---|---|
| this toolkit, `~/.config/opencode` (config, skills, KB files), `~/.conda`, `~/.nextflow`, `~/.singularity`, `~/.apptainer`, opencode's tool output | conda installation (detected), conda envs folder, scratch folder for large data (plus an optional mount point that is checked before use), temp folder (default `<system temp>/opencode-<user>`, mode 0700), any extra folders |

Every other folder is denied. The first permission rule is "deny all external folders", and
`test-deployment` checks that nothing else slipped in. The safeguards stay in place for every
user:

- **Credentials**: `.ssh`, `.aws`, `.gnupg`, `.env`, `.netrc`, `.git-credentials`, opencode's
  `auth.json` and `opencode.db` can't be read or edited.
- **Shell**: `sudo`, `git push`, history rewriting (`git reset --hard`, `git commit --amend`,
  `git clean`, `git filter-branch`), recursive deletes (`rm -r`, `find -delete`), `truncate`,
  `chown -R` and similar commands are **denied**, not asked: the agent stops and asks you to run
  them yourself. Genomic record content can't be printed through the shell (`cat`/`head` of
  BAM, VCF, FASTQ, ...).
- **Config**: agents may read but **not edit** opencode's config folder
  (`~/.config/opencode`, or `$XDG_CONFIG_HOME/opencode`) as a whole, any project-level
  `.opencode/` folder, `opencode.json` or `opencode.jsonc`, and this toolkit's `configs/` and
  `codebase/`. These hold or generate the permission rules, and opencode loads agent
  definitions (with their own permissions) from `agent/`, `agents/`, `mode/` and `modes/` in a
  config folder. `cubi-rules/` stays editable (`update-cubi-digest --run`).

As a consequence, **opencode can't be used to develop this toolkit's `configs/` and
`codebase/`**: edit them with another editor (or another agent tool) and redeploy.

The shell deny rules are a safety net against slips, not a sandbox: they match command text, and
variants such as `rm -r -f` get past them. The kit refuses unsafe answers: `/`, your home folder
or a parent of it, system folders and their roots (`/tmp`, `/var/tmp`, `/dev/shm`, `/mnt`,
`/home`, ...; deeper folders such as `/mnt/disk` are fine), anything below `/etc`, `/proc`,
`/sys`, `/dev` and `/boot`, credential folders and their parents (`~/.ssh`, `~/.claude`,
`~/.config/gh`, `~/.kube`, `~/.docker`, `~/.password-store`, opencode's own folders, `~/.config`,
`~/.local`), folders that everyone may write to and that someone else owns, names with wildcard
characters (`* ? [ ] { }`, also in a symlink's target), and folders that don't exist. On macOS
these checks ignore case. A symlinked folder is granted under both its path and its target. The
temp folder must be a real folder (no symlink) owned by you; if others can read it, the kit sets
it to mode 0700 (on every deploy).

```bash
codebase/opencode-kit.py configure-directories          # ask again (current values are the defaults)
codebase/opencode-kit.py configure-directories --show   # print the settings
codebase/opencode-kit.py configure-directories --scratch-dir /data/me/scratch --envs-dir ~/envs
codebase/opencode-kit.py deploy-configs kiconnect        # apply the changes
```

Agents learn the folders from the "Directories" section of their global rules. Unset folders
are shown as "not configured": agents then ask instead of guessing. Without a scratch folder,
they ask before large downloads.

## 1. opencode 2

```bash
curl -fsSL https://opencode.ai/v2/install -o /tmp/oc-install.sh && bash /tmp/oc-install.sh
opencode --version          # opencode v2.x
```

Alternative: `npm install -g @opencode/cli`. Don't use `opencode.ai/install` or the npm
package `opencode-ai`: both install opencode 1. Docs: <https://opencode.ai/docs>.

## 2. The repository and its submodules

```bash
git clone --recurse-submodules <this-repo-url> ~/Projects/opencode-config
# already cloned without submodules:
git -C ~/Projects/opencode-config submodule update --init
```

Any location works: the kit writes the paths of the checkout it runs from. The two
submodules are pinned to tested commits. `codebase/opencode-kit.py update-git-submodules` moves them to
upstream ([updating-cubi-rules.md](updating-cubi-rules.md), [skills.md](skills.md)).

## 3a. KI Connect NRW (main setup)

KI Connect NRW (<https://chat.kiconnect.nrw>) is the NRW universities' gateway to hosted
LLMs. It has an OpenAI-compatible API at `https://chat.kiconnect.nrw/api/v1`. Models and
routing: [kiconnect-models.md](kiconnect-models.md).

1. Log in at <https://chat.kiconnect.nrw> with your university account and create an API
   key. Your user group needs the deployments qwen-3.8-27B, Mistral Small 4 and GPT OSS
   120B.
2. `setup-opencode` stores it. By hand: `opencode auth login ki_connect --method key`; the
   provider id must be `ki_connect`. Never put the key into a file: the agents may not
   read the credential store (`configs/shared/permissions.json`).

## 3b. Local models with LM Studio (alternative)

For a user who already runs LM Studio with downloaded models and only wants opencode on top:

1. In LM Studio: **Developer → Start server** (port 1234). If opencode runs on another machine,
   enable "Serve on Local Network" and open port 1234 in the firewall.
2. Run `codebase/opencode-kit.py setup-opencode local` (or `configure-lmstudio` on its own). It asks
   for the server URL (`localhost:1234` or `http://<host>:1234/v1`; `/v1` is added if missing),
   then **asks LM Studio which models it has** and shows them with size, tool support, maximum
   and loaded context:

   ```
    #  model                     size tools  max ctx   loaded state
    1  qwen/qwen3.8-27b           27B   yes   262144        - not-loaded
    2  qwen/qwen3.5-9b             9B   yes   262144   131072 loaded
   How should the tiers be filled? [1]:
   ```

   The agents run on five tiers: `light` (small helpers), `main` (the orchestrator), `writing`
   (docs), `codegen` (code) and `careful` (planning, debugging, reviews). You fill them either
   - **[1] with two models**: *heavy* for `codegen` + `careful`, *fast* for the rest (one model
     for both is fine on small machines), or
   - **[2] with one model per tier**, e.g. a mid-size MoE model for `careful` only.

   Suggestions: heavy = the largest model with tool support (1-/2-bit quantisations skipped);
   fast = a model that is already loaded, else the one nearest 9B. Embedding models are never
   offered, and a model without tool support gets a warning (agents need tool calls).
3. Name **further models** to declare for switching by hand inside opencode (or none).
4. Enter the **context length** each chosen model is loaded with in LM Studio (default: the
   loaded length, else 65536, never above the model's maximum). It must match LM Studio's load
   setting (My Models → gear → Load), otherwise compaction never triggers or the context
   overflows. See [lmstudio-model-settings.md](lmstudio-model-settings.md) for a worked example.
5. If "Require authentication" is on in LM Studio, `export LMSTUDIO_API_KEY=<token>` before
   `configure-lmstudio` (to list the models), and enter the token when `setup-opencode` asks
   (opencode sends it with every request).

The result is your **model set**, saved as `lmstudio_models` in
`~/.config/opencode/opencode-kit-settings.json`. Later changes:

| Task | Command |
|---|---|
| show the saved set | `configure-lmstudio --show` |
| choose again (new models downloaded) | `configure-lmstudio`, then `deploy-configs local` |
| without a terminal | `configure-lmstudio --url <url> --heavy <ID> --fast <ID> [--tier careful=<ID>] [--extra <ID>] [--context 65536] [--context <ID>=131072]` |
| write the set by hand | `configure-lmstudio --export my-models.json`, edit, then `configure-lmstudio --models-file my-models.json` (works offline; checked against the server when it answers) |

A set file lists the models (`context` required; optional `output`, `tools`, `reasoning`,
`name`, and `temperature` + `top_p` together, which replace the tier sampling wherever that model
runs) and assigns every tier. `configs/backends/local/lmstudio-models.example.json` is a real
example (Qwen3.5 9B + Qwen3.8 27B on a 16 GB GPU host, five more models declared). Until you have
chosen a set, `preview-configs` and `deploy-configs local --dry-run` use that example and warn
about it. A real first `deploy-configs local` with the server unreachable and no saved set
stops: start the server, or define the set offline with `configure-lmstudio --models-file`.
When the server URL changes (flag or answer), the set is chosen again from the new server; if
it is unreachable, the old set is kept with a warning that it is unchecked. Context lengths below
32768 are allowed (minimum 4096) but warned about: the agents' prompts and tools take about 20K
tokens. Model IDs must not contain `#` (opencode's variant separator). Sets saved by older
versions of the kit (heavy/fast only) are converted automatically.

## 4. Deploy (or redeploy)

```bash
codebase/opencode-kit.py deploy-configs kiconnect --dry-run
codebase/opencode-kit.py deploy-configs kiconnect            # or: local
```

`deploy-configs` writes only these locations (in `$XDG_CONFIG_HOME/opencode` instead of
`~/.config/opencode` when `XDG_CONFIG_HOME` is set, as opencode does):

| Path | Content |
|---|---|
| `~/.config/opencode/opencode.json` | generated config. The previous one goes to `~/.config/opencode/backups/opencode_<YYYYMMDD>-<hhmmss>.json` |
| `~/.config/opencode/prompts/`, `instructions/` | agent prompts and global rules rendered for you (routing table, your folders) |
| `~/.config/opencode/cubi-kb/` | CUBI knowledge-base pages, concatenated for the agents |
| `~/.config/opencode/skills/{nf-core,bionemo}/` | the selected skills, plus the manifest `.opencode-kit.json` |
| `~/.config/opencode/opencode-kit-settings.json` | your directory settings (only when they changed) |
| `~/.config/opencode/.opencode-kit-deploy.json` | deploy manifest: backend, agent packages, files written |
| `~/.config/opencode/backups/` | replaced files: the previous config, and your own files that were in the way of a prompt, instruction file or skill (with a WARNING) |
| the temp folder | created with mode 0700 |

A symlink at one of these files is kept: the kit writes to its target.

`--dry-run` changes nothing. It stops if the submodules are not initialised (run
`git submodule update --init` first). For the `local` backend it still asks the LM Studio server
for its model list (read-only).

Everything above is written into opencode's config folder, `$XDG_CONFIG_HOME/opencode` or
`~/.config/opencode`. opencode itself keeps credentials and sessions in its data folder
(`$XDG_DATA_HOME/opencode` or `~/.local/share/opencode`); the kit writes there only through
`opencode auth import`.

The generated config is not part of the repo. To look at it without installing, run
`codebase/opencode-kit.py preview-configs`, which writes `generated/<backend>/opencode.json` and
`generated/cubi-kb/` (gitignored). It also warns when the CUBI digest is older than the
knowledge base ([updating-cubi-rules.md](updating-cubi-rules.md)).

If `~/.config/opencode/opencode.jsonc` exists, opencode merges it. Keep it empty
(`$schema` only) or delete it.

## 5. Test

```bash
codebase/opencode-kit.py test-deployment           # also runs at the end of deploy-configs / setup-opencode
codebase/opencode-kit.py test-deployment --live    # plus one real model call ("pong")
```

| Check | Passes when |
|---|---|
| opencode 2 installed | `opencode --version` is 2.x |
| config present | `~/.config/opencode/opencode.json` exists |
| instruction files | the global instruction files exist |
| agents resolve | `opencode debug agents`: every agent has its configured model+variant and its prompt **text** |
| credentials | a key is stored for the provider (not required for LM Studio) |
| CUBI KB files | `~/.config/opencode/cubi-kb/*.md` exist |
| session: skills | a real session advertises every installed skill to the model |
| session: instructions | both global instruction files are in the session's system prompt |
| session: build prompt | the `build` agent's prompt is in the system prompt |
| directory sandbox | external folders: deny-all first, then only the standard folders and yours; no `agent/`, `agents/`, `mode/`, `modes/` folder in opencode's config folder |
| session: routing | the orchestrator's routing table names every installed subagent |
| live model call | (`--live`) the default model answers |

The three session checks run `opencode run` once against a local fake endpoint, in a
throwaway copy of the config. They need no key and don't touch your sessions.

## Running

```bash
cd ~/Projects/<some-project>
opencode                                          # TUI; Tab switches primary agents, @<agent> calls a subagent
opencode run "Reply with exactly one word: pong"  # one-shot
opencode serve --hostname 0.0.0.0 --port 4096     # server; set OPENCODE_PASSWORD first
```

## Updating

```bash
cd ~/Projects/opencode-config
git pull --recurse-submodules                       # toolkit and pinned submodules
codebase/opencode-kit.py deploy-configs kiconnect   # or: local; uses your saved answers
opencode upgrade                                    # newest opencode 2 (optional)
```

`git pull` alone changes nothing in your opencode setup: the deployed files are only
replaced by `deploy-configs`. If the submodules were not updated, run
`git submodule update --init`.

Maintainers move the submodules to upstream with
`codebase/opencode-kit.py update-git-submodules` and then commit the new pins.

## Uninstall and reset

The kit writes only the locations listed in section 4. To remove the setup, delete these
from opencode's config folder (`~/.config/opencode`, or `$XDG_CONFIG_HOME/opencode`):

- `opencode.json`, `prompts/`, `instructions/`, `cubi-kb/`;
- the skills the kit installed: `codebase/opencode-kit.py install-skills --skills none`
  removes exactly those (skills you added yourself stay);
- `.opencode-kit-deploy.json`;
- `opencode-kit-settings.json`, to forget your folders, LM Studio URL and model set
  (the next deploy asks again).

Keep `backups/` as long as you may want a previous config back: it holds the replaced
`opencode.json` and any of your own files the kit moved out of the way. The temp folder
(default `<system temp>/opencode-<user>`) can be deleted as well.

To reset only your answers, delete `opencode-kit-settings.json` and run `deploy-configs`
again. To remove opencode itself, delete `~/.opencode/bin`, and your sessions and
credentials in `~/.local/share/opencode`. The toolkit checkout is not touched by any of this.

## Troubleshooting

The kit prints `ERROR:` (stops), `WARNING:` and `INFO:` lines on stderr. Messages below are
quoted in part; `<...>` stands for your values.

| Message or symptom | Cause and fix |
|---|---|
| `'git' not found on PATH; install it with your package manager` (same for `curl`, `bash`) | A prerequisite is missing. Install it (on HPC: `module load` it) and run again. |
| `Python 3.x found; 3.8 or newer is needed` | Run the kit with a newer interpreter: `python3.11 codebase/opencode-kit.py ...`. |
| `submodule(s) ... not initialised` | The clone has no submodules. Run `git submodule update --init` in the checkout. |
| `ServiceUnavailableError: Location plugins did not finish activating` | opencode 2.2.6 start-up flake, common on slow machines. The kit retries up to 3 times. If it still fails, run the same command again. `OPENCODE_DISABLE_MODELS_FETCH=1` makes it rarer. |
| `... is opencode 1.x, which this configuration does not support` | [upgrading-from-opencode-1.md](upgrading-from-opencode-1.md). |
| `opencode not found; run: codebase/opencode-kit.py setup-opencode <backend>` | opencode 2 is not on `PATH`. Run `setup-opencode`, then `exec $SHELL -l`. |
| FAIL `credentials`: `missing: ki_connect` | No API key is stored for the provider. Run `codebase/opencode-kit.py setup-opencode kiconnect` (add `--replace-key` for a new key), or `opencode auth login ki_connect --method key`. The provider id must be `ki_connect`. |
| `<url>: HTTP 401; the API key was rejected, create a new one` | The KI Connect key is wrong or expired. Create a new key, then `setup-opencode kiconnect --replace-key`. |
| `model not found`, or a warning `models used by this backend but not offered by the server` | KI Connect renamed a deployment, or your user group lacks it: [kiconnect-models.md](kiconnect-models.md). |
| `LM Studio at <url> not reachable and no model set saved, so the local config can't be built` | The server is down, or the URL is wrong. Start it (**Developer → Start server**, port 1234). If opencode runs on another machine, enable "Serve on Local Network" and allow port 1234 in the firewall. Or define the model set offline: `configure-lmstudio --models-file <file>` (start from `configs/backends/local/lmstudio-models.example.json`), then `deploy-configs local`. |
| `WARNING: LM Studio not reachable: the example model set is used ...` | Only a dry run or `preview-configs` may fall back to the example set. Choose your own with `configure-lmstudio`. |
| `<url>: HTTP 401, the server requires a token; export LMSTUDIO_API_KEY=<token ...>` | "Require authentication" is on in LM Studio. `export LMSTUDIO_API_KEY=<token>` (token from **Developer → Server Settings**), then run `configure-lmstudio` again. `setup-opencode local` also asks for the token. |
| Long sessions fail with context overflow, or compaction never starts | The `context` in your model set differs from the context length LM Studio loads the model with. Make them equal (My Models → gear → Load), then `configure-lmstudio --context <ID>=<N>` and `deploy-configs local`. See [lmstudio-model-settings.md](lmstudio-model-settings.md). |
| `tmp_dir: '<path>' is owned by uid ... expected you` (also `is a symlink ...`, `is not a folder`) | The temp folder must be a real folder that you own. Pass `--tmp-dir <folder>`, e.g. a new folder below your scratch folder. |
| `<key>: '<path>' is your home folder or a parent of it; choose a dedicated folder below it` (also `is a system folder ...`, `is below the system folder ...`) | The kit refuses folders that are too broad. Pick a dedicated subfolder, e.g. `~/opencode-scratch` instead of `~`, or `/mnt/disk` instead of `/mnt`. |
| `<key>: folder '<path>' does not exist; create it first (mkdir -p <path>) or leave it empty` | Create the folder, or leave the question empty. |
| `<key>: '<path>' contains one of * ? [ ] { }, which would act as a wildcard ...` | Rename the folder or choose another one. |
| `WARNING: directories not confirmed yet: only the temp folder, saved folders and folder flags are allowed` | You have not answered the folder questions yet. Run `configure-directories`, then `deploy-configs <backend>`. |
| FAIL `directory sandbox`: `<...>/agent exist(s): opencode loads agent definitions from there and their permissions override the sandbox` | A folder `agent/`, `agents/`, `mode/` or `modes/` exists in opencode's config folder. Its agents ignore the sandbox rules. Move the definitions into `configs/agents/` of this repo and redeploy, or remove the folder. |
| FAIL `agents resolve`: `prompt not loaded` | Don't edit `opencode.json` by hand. Edit `configs/` and redeploy. |
| FAIL `session: skills` | `codebase/opencode-kit.py list-skills`, then redeploy. Check for a skill with the same ID in `~/.claude/skills` or a project `.opencode/skills`. |
| Setting seems ignored | opencode 2 silently drops unknown fields. `opencode debug config --standalone --print-logs --log-level warn` shows `normalization diagnostic` lines. |
| Project `CLAUDE.md` ignored | opencode 2 reads `AGENTS.md`: `ln -s CLAUDE.md AGENTS.md`. |
| An agent refuses a command and asks you to run it | A denied shell command (see "What agents may and may not do"). Run it yourself. |
| After moving the checkout, agents lose their prompts or rules | The deployed config points into the checkout. Run `deploy-configs <backend>` from the new location. |
