# LM Studio model settings for opencode

A worked example: load and sampling settings for one real LM Studio host (RTX 4060 Ti 16 GB
VRAM, 64 GB RAM, Intel i9) and the model set it uses,
`configs/backends/local/lmstudio-models.example.json`. Model list as of 2026-09-19
(`/api/v0/models`, saved as the test fixture `codebase/tests/data/`). Section 1 applies to any
host; for other models and GPUs, use section 2 as a pattern and the model cards for sampling.

Memory and speed figures are **estimates**. LM Studio's load dialog shows the real memory
estimate for your settings; go by that figure.

## How opencode uses the models

`codebase/opencode-kit.py configure-lmstudio` reads the models from your LM Studio server and
builds your *model set*: a heavy and a fast model, or one model per tier, plus extra models you
can switch to by hand in opencode. You can also write the set as a file (start from the example,
or `configure-lmstudio --export my-models.json`) and import it with
`configure-lmstudio --models-file my-models.json`; that works without a running server. Until
you choose, the example set below is used and every deploy warns about it.

Per model the set holds `context` (required: the length LM Studio loads it with), and
optionally `output`, `tools`, `reasoning`, `name`, and `temperature` + `top_p` (both or neither;
they replace the tier sampling wherever that model runs). The example gives Gemma 4 26B its
recommended temperature 1.0 this way.

The *fast* role fills the tiers `light`, `main` and `writing`, the *heavy* role fills `codegen`
and `careful` (see [deploy.md](deploy.md), section 3b). Your own set can assign any model to any tier.

| Role | Model | Used by | Why |
|---|---|---|---|
| Fast | `qwen/qwen3.5-9b` | `build`, `general`, `explore`, `title`, `summary`, `conda-agent`, `nextflow-lint`, `nf-core-docs`, `nf-core-release` | Fits entirely on the GPU with a 128K context. Fast, and strong tool calling for its size. |
| Heavy | `qwen/qwen3.8-27b` | `plan`, `nextflow`, `nf-core-modules`, `nf-core-testing`, `nf-core-template`, `nf-core-migration`, `bioinformatics-agent`, `debug-agent`, `paper-writing` | The strongest coder you have. Doesn't fit in 16 GB, so some layers run from system RAM: slow but best quality. |
| Manual only | `gemma-4-26b-a4b-qat`, `gemma-4-12b-qat`, `gemma-4-e4b`, `nemotron-3-nano-4b`, `bonsai-27b` | no agent | Declared in the model set so you can switch to them from within opencode. |

Both models are Qwen3.5-architecture models, so tool-call formatting and the chat template behave
the same across hand-offs.

## 1. Global LM Studio settings (do these first)

**Developer → Server Settings**

- **Just-in-Time model loading: ON.** opencode requests models by ID and LM Studio loads them on
  demand.
- **Only keep last JIT loaded model (auto-evict): ON.** The 9B and the 27B cannot both sit in
  VRAM. Evicting the 9B gives the 27B the whole GPU, which is far faster than squeezing both in.
  A switch between roles costs one reload (a few seconds for the 9B, roughly 10–20 s for the
  27B from NVMe), which is small compared with a subagent run.
- **Auto-unload unused JIT models, TTL:** 60 min.
- **Require authentication:** your choice. If it is on, `export LMSTUDIO_API_KEY=<token>` before
  `configure-lmstudio`, and give the token to `setup-opencode local` so that opencode sends it.

**Unload anything you loaded by hand before using opencode.** For example, a hand-loaded
`google/gemma-4-e4b` at a 131K context. Auto-evict only removes models that were JIT-loaded, so a
hand-loaded model keeps holding VRAM and pushes more of the 27B into slow system RAM. Check with
`lms ps`, then unload it with `lms unload google/gemma-4-e4b` (or `lms unload --all`).

**Per-model defaults are what JIT loading uses.** Set everything below under
**My Models → ⚙ (gear icon) next to the model**, on the *Load* and *Inference* tabs. Settings
changed only in the Chat tab's sidebar do **not** apply to API requests.

**Settings that apply to every model**

- **Flash Attention: ON.** It's faster and required for KV-cache quantization.
- **K and V cache quantization: `Q8_0`.** It halves the context memory with no measurable quality
  loss; this is what makes the long contexts below fit.
- **CPU Thread Pool Size = number of P-cores** (8 on an i9-13900/14900). Only the offloaded
  layers of the 27B use it, and the E-cores slow those down rather than helping.
- **Try mmap(): ON.** **Keep model in memory: ON.** You have the RAM, and it makes reloads after
  eviction faster.
- **Max concurrent predictions: 1** for the 27B. For the 9B, 2 is fine if you see opencode's
  title and main requests queueing, at the cost of extra context memory.
- **If the host runs Windows:** in the NVIDIA Control Panel, set *Manage 3D settings → CUDA –
  Sysmem Fallback Policy* to **Prefer No Sysmem Fallback**. Otherwise the driver silently spills
  VRAM into shared memory over PCIe, which is much slower than LM Studio's own CPU offload.

**Sampling: which side sets what**

opencode sends `temperature` and `top_p` with every request (0.6 / 0.95 on all local agents), and
those override LM Studio's values. opencode **cannot** send `top_k`, `min_p`, or penalties, so
LM Studio's per-model defaults below are the ones that apply for those.

## 2. Per-model settings

### `qwen/qwen3.5-9b`: fast role (Q4_K_M)

| Setting | Value |
|---|---|
| Context length | **131072**. Must match `context` for this model in your model set. |
| GPU offload | **All layers (max)** |
| Flash attention / KV cache | ON / `Q8_0` for K and V |
| Evaluation batch size | 1024. Faster prompt processing for opencode's ~20K-token system prompts; drop to 512 if it no longer fits. |
| Temperature / Top P | 0.6 / 0.95 (sent by opencode; set the same here for other clients) |
| Top K / Min P | **20 / 0** |
| Repeat penalty | **1.0 (off)**. If it starts looping, try 1.05. |
| Thinking | **ON**. Agentic coding and tool use are clearly better with it. |

Expected: about 9–11 GB VRAM in total and roughly 40–50 tok/s generation. The Qwen3.5
architecture uses linear attention in most layers, so the KV cache stays small even at 128K.

### `qwen/qwen3.8-27b`: heavy role (Q4_K_M)

| Setting | Value |
|---|---|
| Context length | **65536**. Must match `context` in the model set. Each subagent starts with a fresh context, so 64K is plenty, and opencode compacts before it overflows. Doubling it moves another ~2 GB of layers into RAM. |
| GPU offload | **As many layers as fit while the load estimate stays at or below ~15 GB VRAM** (probably ~48–52 of 64 layers). Leave about 1 GB of headroom, because running out of VRAM during generation is much worse than offloading one more layer. |
| Flash attention / KV cache | ON / `Q8_0` for K and V |
| Offload KV cache to GPU memory | ON. Keep attention on the GPU and let weight layers go to the CPU. |
| Evaluation batch size | 512 (default). Only raise it if VRAM is left over. |
| CPU threads | Number of P-cores |
| Temperature / Top P | 0.6 / 0.95 (sent by opencode) |
| Top K / Min P | **20 / 0** |
| Repeat penalty | **1.0 (off)** |
| Thinking | **ON** |

Expected: about 6–12 tok/s generation. The first token of a turn can take 30–90 s while the
prompt is processed. That's why the opencode `lmstudio` provider has `timeout` set to 30 min and
`chunkTimeout` to 10 min; don't lower them.

For `qwen3.8` there are no published settings yet. The API reports it as the `qwen35`
architecture, so these are Qwen3.5's published settings for coding in thinking mode. If its
Hugging Face model card recommends different sampling, use the model card's values.

### `google/gemma-4-26b-a4b-qat`: manual (MoE, Q4_0)

This is the best "medium" option: a mixture-of-experts model with about 4B active parameters, so
it runs several times faster than the 27B dense model even with some experts in system RAM. Try
it on `build`/`general` if the 9B routes badly, or on a mid-difficulty specialist if the 27B is
too slow for your patience.

| Setting | Value |
|---|---|
| Context length | 65536 (matches the model set) |
| GPU offload | All layers (max) |
| Force MoE expert weights onto CPU | Raise the layer count until the load estimate is at or below ~15 GB. This keeps attention and shared weights on the GPU, which costs far less speed than offloading whole layers. |
| Flash attention / KV cache | ON / `Q8_0` |
| Temperature / Top P / Top K | Google recommends 1.0 / 0.95 / 64. opencode's agents send 0.6 / 0.95, which is fine for tool use; set Top K 64 here. |
| Repeat penalty | 1.0 |

Expected: about 20–35 tok/s.

### `google/gemma-4-12b-qat`: manual (Q4_0)

Context 65536, all layers on the GPU (about 7 GB of weights), flash attention on, KV `Q8_0`,
Top K 64, repeat penalty 1.0. The Qwen3.5 9B does the same job faster with more context, so
you'd rarely need this.

### `google/gemma-4-e4b`: manual (Q4_K_M)

Context 131072, all layers on the GPU, flash attention on, KV `Q8_0`, Top K 64. Useful for quick
chats outside opencode. **Don't leave it loaded by hand while opencode runs** (see section 1).

### `nvidia/nemotron-3-nano-4b`: manual (Q4_K_M)

This is a hybrid Mamba model with a 1M maximum context and a very cheap cache. It's a candidate
for summarizing huge logs (`.nextflow.log`, long `.command.err` files), not for code. Load it at
131072 (matching the model set) with all layers on the GPU; you can go much higher if you also
raise its `context`. Keep LM Studio's bundled sampling defaults.

### `prism-ml/bonsai-27b`: experimental (Q1_0)

This is a 1-bit Qwen3.5-architecture 27B. It fits entirely on the GPU with room to spare, so it's
fast, but 1-bit weights lose accuracy exactly where nf-core work needs it: exact syntax and CLI
flags. Don't use it for specialists. If you want to experiment, compare it against the 9B on the
fast role. Settings: context 131072, all layers on the GPU, Top K 20, Min P 0.

### `text-embedding-nomic-embed-text-v1.5`

opencode doesn't use it. Leave it unloaded.

## 3. Applying and checking

1. Set the per-model defaults above in LM Studio and unload any hand-loaded models.
2. Deploy the config: `codebase/opencode-kit.py deploy-configs local` (see [deploy.md](deploy.md)).
3. Start opencode and send one message. On the host, `lms ps` should show `qwen/qwen3.5-9b` at a
   131072 context.
4. Trigger a heavy agent, e.g. "ask the nextflow agent to explain `main.nf`". `lms ps` should
   now show only `qwen/qwen3.8-27b` at 65536.
5. If you change a context length in LM Studio, change it in the model set too: run
   `codebase/opencode-kit.py configure-lmstudio` again (or `--context <ID>=<N>`, or edit your
   file and `--models-file` it), then `deploy-configs local`. A larger value in opencode than in
   LM Studio makes long sessions fail with context-overflow errors instead of compacting.
