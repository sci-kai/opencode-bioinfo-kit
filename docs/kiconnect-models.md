# KI Connect NRW models

Provider id `ki_connect`, OpenAI-compatible API `https://chat.kiconnect.nrw/api/v1`
(`@ai-sdk/openai-compatible`). The key is stored with `opencode auth login` (see
[deploy.md](deploy.md)), never in a file.

## Deployments (checked 2026-11-08 via `GET /api/v1/models`)

The web page *User groups → Deployments* needs a login; the API list is the same and is
what opencode uses. Context lengths are the vLLM `max_model_len` reported by the server;
speeds are one measured request (about 1000-token answer) and only a rough guide.

| Model id | Model | Context | Output limit set | Speed | Tier |
|---|---|---|---|---|---|
| `GPT OSS 120B KI.Inferenz.nrw` | OpenAI gpt-oss-120b (MoE, reasoning) | 131072 | 8192 | ~190 tok/s | `light` (incl. title generation) |
| `MistralSmall_4` | Mistral Small 4 119B-2603 | 262144 | 65536 | ~90 tok/s | `writing` |
| `qwen-3.8-27B` | Qwen3.8 27B (dense, thinking, tool calls) | 262144 | 65536 | ~25 tok/s | `main`, `codegen`, `careful` (default model is the `main` tier) |
| `GPT5-GWDG` | GPT-5, high effort | 400000 | 128000 | – | manual only (quota: 500K tokens or 200 messages/week) |
| `GPT5_4` | GPT-5.4, high effort | 128000 | 16384 | – | manual only (same quota) |
| `Qwen3_Embedding_8B` | embedding model | – | – | – | not usable as a chat/agent model |

## Tier routing

Qwen3.8 27B is the default model and runs all main and heavy work. Only light tasks and
pure documentation writing go to the faster models.

| Tier | Model | Agents | Why |
|---|---|---|---|
| `main` | qwen-3.8-27B | `build`, `general` + default `model` | Strongest reasoning and tool use available on KI Connect. |
| `codegen` | qwen-3.8-27B | `nextflow`, `nf-core-modules`, `nf-core-template`, `nf-core-testing`, `nf-core-migration` | Code quality over speed; 262K context and a 64K output budget. |
| `careful` | qwen-3.8-27B | `plan`, `debug-agent`, `bioinformatics-agent`, `nextflow-lint`, `nf-core-release`, `paper-writing` | Correctness-critical work. |
| `writing` | Mistral Small 4 | `nf-core-docs` | Documentation prose; about 4× faster, with a 64K output budget. |
| `light` | GPT OSS 120B | `explore`, `title`, `summary`, `conda-agent` | Fastest; short tool-driven tasks. |

Trade-off: qwen is slow (about 25 tok/s, and it thinks before answering). If the
orchestrator feels too slow, set `tiers.main.model` back to `ki_connect/MistralSmall_4`
(with `temperature` 0.3, `top_p` 0.9). The heavy specialists stay on qwen.

To move all agents of a tier to another model, change one line under `tiers` in
`configs/backends/kiconnect/backend.json`. To move one agent, add it to `agent_tiers` (e.g.
`"nextflow-lint": "light"` if linting on qwen is too slow). Then run
`codebase/opencode-kit.py deploy-configs kiconnect`.

## When KI Connect changes its deployments

1. List the models: `curl -s -H "Authorization: Bearer $KI_CONNECT_API_KEY" https://chat.kiconnect.nrw/api/v1/models`
   (the kit also checks this list when it stores a key; `setup-opencode kiconnect --replace-key`
   warns about models that are missing).
2. Find the context limit: send a request with a huge `max_tokens`; vLLM answers with
   `max_tokens=... cannot be greater than max_model_len=<N>`.
3. Check tool calls with a small `tools` request (`finish_reason: tool_calls`).
4. Add or rename the model under `providers.ki_connect.models` (with `capabilities` and
   `limit`), update `tiers`, update the
   table above with the date, and run `codebase/opencode-kit.py preview-configs` (validates) and `codebase/opencode-kit.py deploy-configs kiconnect`.
