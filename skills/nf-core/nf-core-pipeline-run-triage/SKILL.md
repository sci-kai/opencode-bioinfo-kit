---
name: nf-core-pipeline-run-triage
description: 'Diagnose a failing Nextflow pipeline run from the work directory and logs: locating the failing task, reading .command.sh/.command.err/.command.log, exit codes, resource-limit failures, and resuming correctly. Use when a pipeline run crashes, hangs, or produces wrong output.'
argument-hint: 'The error message or the failing process name'
user-invocable: true
---

# Triage a Failing Pipeline Run

## Privacy hard rule — read this first

The work directory is full of FASTQ/BAM/CRAM/VCF files. **Never** read their record content into
your context — no `cat`/`head`/`less`/`zcat` on them, no unredirected `samtools view` /
`bcftools view`, no `Read` tool. Diagnose from logs, exit codes, and metadata-only checks
(`samtools quickcheck`, `flagstat`, `idxstats`, `bcftools stats`, `bcftools view -h`, file size,
line counts). This holds no matter how convenient reading the file would be.

## Procedure

1. **Read the Nextflow error block in full.** It names the failing process, the exit status, and the exact work directory — do not guess any of these.
2. **Go to the task directory** (`work/<hash-prefix>/<hash>/`) and inspect, in this order:
   - `.command.err` — the tool's stderr, usually the actual cause
   - `.command.log` — combined output
   - `.command.sh` — the *resolved* command, with `ext.args` and staged file names substituted. Compare it against what you intended; a wrong flag or a missing input shows up here immediately.
   - `.exitcode`
   - `ls -la` — check whether the expected input files were actually staged (broken symlink = an upstream channel problem, not a tool problem)
3. **Classify the exit code before theorising:**
   - `1`/`2` and a tool message → tool/argument error; fix `ext.args`, inputs, or the module.
   - `137` (OOM-killed), `140`/`143` (scheduler kill) → resource limits, not a code bug. Raise the process `label`/resources, or the profile's limits.
   - `127` → command not found: the tool is missing from `environment.yml`/the container.
   - `126` → permission/executable problem, often a container or filesystem-mount issue.
4. **Check the run-level log** `.nextflow.log` for scheduler submission errors, container pull failures, and channel/staging problems that never reached a task.
5. **Check the known-issues knowledge base** before improvising a fix: `~/.config/opencode/cubi-kb/hints-kb-agents-instructions.md` covers recurring environment quirks (offline conda, GPU-in-container, filesystem oddities). Say in your report whether a documented fix applied or you had to improvise.
6. **Reproduce narrowly.** Re-run the failing tool command from `.command.sh` inside the task directory (or the module's nf-test) rather than re-running the whole pipeline.
7. **Fix at the right layer:** wrong flag → `ext.args`; wrong channel shape → the workflow (see `nf-core-meta-map`); missing dependency → `environment.yml`/container (`nf-core-container-uri`); resource limit → process label or profile.
8. **Re-run and confirm.** `nextflow run ... -resume` re-uses cached tasks; verify the previously failing task actually re-executed (it appears without a cached marker in the run summary) rather than being skipped from cache.

## Verification

- The originally failing command now succeeds — re-run the exact thing that failed, not an approximation.
- The pipeline's `-profile test,<backend>` run completes end to end.
- Expected outputs exist and are non-empty (`ls -la`, `samtools quickcheck`, `bcftools stats`), verified without reading their content.
- Any temporary instrumentation (`.view()`, `NXF_DEBUG`, added `println`) is removed.

## Notes

- `-resume` that keeps failing identically usually means the cached upstream task produced bad output; delete that task's cache or run with `-resume` from an earlier point rather than repeating the same run.
- Never "fix" a failure by removing an assertion, widening an error-strategy to `ignore`, or setting `errorStrategy 'retry'` on a deterministic failure — report the root cause instead.
