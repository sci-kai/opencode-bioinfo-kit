---
name: nf-core-container-uri
description: 'Define or fix the conda/container specification of an nf-core module: environment.yml pinning and the Docker/Singularity container directive via Seqera Containers (Wave). Use when creating a module, bumping a tool version, or when a container URI fails to pull.'
argument-hint: 'Module name and the conda package(s) with versions'
user-invocable: true
---

# Module Containers and Conda Environments

**Canonical guide:** <https://nf-co.re/docs/developing/containers/seqera-containers>
(ARM64 specifics: <https://nf-co.re/docs/developing/containers/arm64-on-bioconda>)

## Rules

- One tool plus its required dependencies per module. Do not bundle unrelated tools into one container.
- `environment.yml` is the source of truth; the container URIs are generated *from* its package list. If they disagree, the module is broken.
- Pin exact versions with an explicit channel prefix (`bioconda::samtools=1.21`), never a floating version.

## Procedure

1. Write/update `modules/.../environment.yml` with the channel-prefixed, version-pinned package(s).
2. Test the environment resolves before generating containers — a container build failure is much slower to diagnose than a conda solve failure. Hand off to `conda-agent` if the solve is non-trivial.
3. Generate the container URIs at <https://seqera.io/containers/>:
   - Enter the exact packages from `environment.yml`.
   - Generate the **Docker** URI first.
   - Switch to **Singularity**, wait for the build to finish, then tick the **HTTPS** checkbox (it only appears after a successful build) and copy that URI.
4. Write the directive in `main.nf` exactly in this shape:
   ```groovy
   container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
       'https://community-cr-prod.seqera.io/<singularity-container-id>' :
       'community.wave.seqera.io/<docker-container-id>' }"
   ```
   Formatting rules that lint and runtime both depend on:
   - the Docker URI has **no** `https://` prefix;
   - the Singularity URI **must** keep the full `https://community-cr-prod...` prefix.
5. Keep the `conda "${moduleDir}/environment.yml"` directive alongside it.

## Verification

- `nf-core modules lint <name>` passes its container checks.
- The module runs under each backend the pipeline supports: `nf-test test ... --profile docker` and `--profile singularity` (and `--profile conda` where used).
- Version reported by the module at runtime matches the pin in `environment.yml`.

## Notes

- If a Singularity pull fails with an HTML/404 body, the usual cause is a Docker-style URI in the Singularity slot or a missing `https://` — re-check step 4 before suspecting the registry.
- On ARM64 hosts, check the bioconda ARM64 guide before assuming a package has a linux-aarch64 build; if it does not, note the constraint rather than silently pinning an x86-only image.
- GPU tools use a different, dual-container pattern — see `nf-core-gpu-module`.
- Offline/air-gapped HPC environments have their own container and conda caveats; check the CUBI hints knowledge base before improvising.
