---
name: nf-core-gpu-module
description: 'Write or adapt an nf-core module for GPU execution: the accelerator directive contract, ext.use_gpu, dual CPU/GPU containers, CUDA pinning, and GPU test configuration. Use when a tool has a GPU code path or a module must run on GPU nodes.'
argument-hint: 'Module name and the GPU-capable tool/package'
user-invocable: true
---

# GPU-Enabled Modules

**Canonical guide:** <https://nf-co.re/docs/developing/components/gpu-modules>

## The contract

A module **never sets** the `accelerator` directive itself. The *pipeline* requests GPUs by
setting `accelerator = 1` in its process config; the module only *reacts* to `task.accelerator`.
This keeps modules usable on CPU-only infrastructure.

## Choosing a container strategy

- **Single container** — GPU support adds little size, or one image covers both paths.
- **Dual container** — the GPU variant is substantially larger (a CUDA PyTorch image can add ~3 GB). Switch on `task.accelerator`:
  ```groovy
  conda "${ task.accelerator ? "${moduleDir}/environment.gpu.yml" : "${moduleDir}/environment.yml" }"
  container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
      (task.accelerator ? '<singularity-gpu-url>' : '<singularity-cpu-url>') :
      (task.accelerator ? '<docker-gpu-url>' : '<docker-cpu-url>') }"
  ```
- **Vendor container** (proprietary, no conda equivalent) — guard against conda profiles so a conda run fails with a clear message instead of silently running the wrong thing.

## CUDA pinning

Pin `cuda-version` exactly. The pin sets the **minimum NVIDIA driver version required on the
host**, so choose the lowest value the GPU package actually supports on conda-forge:

```yaml
dependencies:
  - "conda-forge::pytorch-gpu=2.1.0"
  - "conda-forge::cuda-version=11.2"
```

Check the target cluster's driver version before pinning — a pin above what the nodes provide
makes the module unrunnable there.

## Enabling the GPU path

- Use `ext.use_gpu` (set by the pipeline in `conf/modules.config`) to pass the tool's own GPU flag through `ext.args`, rather than branching inside the script body where possible.
- Set `maxForks = 1` on GPU processes to prevent Singularity deadlocks when several tasks share one GPU.

## Testing

- Write a separate `tests/main.gpu.nf.test` for dual-mode modules.
- Tag GPU tests `"gpu"` (or `"gpu_highmem"`) so CI can select or skip them.
- Ship a `tests/nextflow.gpu.config` that sets `accelerator = 1`.
- Use the **same assertions** as the CPU test — the point is proving GPU and CPU paths produce equivalent results.

## Verification

- `nf-core modules lint <name>` clean.
- CPU test passes on a machine without a GPU (the module must not require one).
- GPU test passes where hardware is available, or is explicitly reported as untestable in this environment with the reason.

## Notes

- Running GPU workloads inside containers on CUBI infrastructure has known quirks — check the CUBI hints knowledge base (`~/.config/opencode/cubi-kb/hints-kb-agents-instructions.md`) before debugging from scratch.
