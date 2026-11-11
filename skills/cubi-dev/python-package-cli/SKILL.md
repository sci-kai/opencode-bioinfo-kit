---
name: python-package-cli
description: 'Create or extend an installable Python tool: src layout, pyproject.toml (entry point, package data, black/ruff/pytest config, optional dev deps), __version__ and --version, argparse subcommands with one cmd_<name> function each, --dry-run, plan/verify commands, conda env file. Use for stand-alone tools like dataset builders or CLIs, not for single workflow scripts.'
---

# Installable package with a CLI

Purpose: a reusable tool (e.g. seqc2-toolkit) with subcommands, defaults that are safe, and a
layout that tests and conda can install.

## When to use / not to use

Use when the tool has several commands, shipped data files, or is used outside one workflow. For one
workflow helper use `python-bin-script`. Use typer/click only if the app already does;
new tools use argparse.

## Steps

1. **Layout.**
   ```
   <repo>/pyproject.toml  README.md  CHANGELOG.md  LICENSE
   <repo>/envs/<name>.yaml
   <repo>/src/<pkg>/__init__.py   (__version__ = "0.1.0-dev")
   <repo>/src/<pkg>/cli.py  <topic modules>.py  data/*.yaml
   <repo>/tests/test_<module>.py
   ```
   Repository name follows CUBI rules (`workflow-...`, `project-...`); a pure tool may use a plain short name.
2. **pyproject.toml** (adapt):
   ```toml
   [project]
   name = "<pkg>"
   version = "0.1.0-dev"
   requires-python = ">=3.10"
   dependencies = ["pyyaml"]
   [project.optional-dependencies]
   dev = ["pytest", "black", "ruff"]
   [project.scripts]
   <tool> = "<pkg>.cli:main"
   [tool.setuptools.packages.find]
   where = ["src"]
   [tool.setuptools.package-data]
   <pkg> = ["*.yaml"]
   [tool.black]
   line-length = 100
   [tool.ruff]
   line-length = 100
   [tool.ruff.lint]
   select = ["E", "F", "W", "I", "B", "UP"]
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   pythonpath = ["src"]
   ```
   Version is a semver string with `-dev` on the dev branch; a manual bump is its own commit.
3. **cli.py.** Module docstring lists the commands plus an Examples block. One function `cmd_<name>(args)` per subcommand with a docstring; `build_parser()` uses `add_subparsers(dest="command", required=True)`; global `--verbose`, `--version`. `main(argv=None)` configures logging, calls `args.func(args)`, catches the tool's error class, prints `ERROR: <msg>` to stderr, exits 1.
4. **Command set that works well:** `plan` (what would happen, sizes, what is cached), `fetch`/`build` (do only what is missing), `run` with `--dry-run` (print the final command prefixed with `$ `), `verify` (recompute checksums, exit 1 if any changed), `list`/`catalog` (read-only). Mutating commands support `--dry-run`; never `--force` by default.
5. **Config vs flags.** Defaults in a YAML file shipped as package data; user config (YAML, `n/a` for unset) overrides; CLI flags override config. Cache/data dirs from an env var, else a user dir. Document the order in `--help`.
6. **Environment file** `envs/<name>.yaml`: conda-forge + bioconda, `python=3.12`, tools with exact pins, comment headers per group, `pip: [-e .]` for the package, dev tools at the end. No `.venv`.
7. **Tests**: parser smoke test (`--help`, `--version`), one test per command on tiny synthetic input, failure tests for bad config.
8. Run `black`, `ruff check`, `pytest`; update README (usage per command) and CHANGELOG.

## Checks before finishing

- `pip install -e .` in the conda env, then `<tool> --help` and `<tool> --version` work.
- Package data is found after install (not only from the source tree).
- `--dry-run` writes and downloads nothing (check with `git status` or a temp dir).

## Pitfalls

- Forgetting package-data: works in the repo, fails when installed.
- Type hints are expected in packages; add them to every public function.
- Do not parse secrets from flags; read them from env or a config outside the repo.
