---
name: test-pytest-setup
description: 'Set up pytest for scripts and tools: tests/ layout, importing bin/ scripts, conftest with an isolation fixture, tmp_path builders, a network marker, filterwarnings=error, local HTTP server fixtures, parametrisation, and the commands to run. Use when adding tests to a Python script, package or workflow bin/ folder.'
---

# pytest setup

## Purpose

A consistent, isolated pytest layout for helper scripts and stand-alone tools.

## When to use

- A new `bin/` script or Python package has no tests yet.
- Tests touch the real home, network or production paths.
- Not for pipeline tests (`test-pipeline-asserts`).

## Steps

1. Layout: workflows `tests/python/test_<script>.py` (one per script) plus `conftest.py`; tools `tests/test_<area>.py`. Name scripts with `_` so they import; for dash-named scripts load with `importlib.util.spec_from_file_location` in a helper.
2. conftest for scripts: `sys.path.insert(0, str(REPO / "bin"))`; constants for the repo and data paths.
3. `pyproject.toml`:

   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   markers = ["network: calls real web APIs (enable with --network)"]
   filterwarnings = ["error"]
   ```
   Add narrow `ignore:` lines for known harmless third-party warnings, with a comment.
4. Network marker in conftest: option `--network`; in `pytest_collection_modifyitems` skip items marked `network` unless set. Default runs never touch the network.
5. Isolation fixture (autouse): `monkeypatch.chdir(tmp_path)`, point `XDG_CONFIG_HOME`/`XDG_DATA_HOME`/`HOME` into `tmp_path`, and fail any test that changed the real user folders (compare a state snapshot before and after).
6. Builders instead of committed data: fixtures create FASTA, VCF or tables in `tmp_path` with `random.Random(<seed>)`; small helpers like `vcf_text(contigs, records)`.
7. Download or cache code: serve a temp folder with `http.server` on `127.0.0.1:0` in a fixture; prove idempotency with `monkeypatch.setattr(net, "get_file", lambda *a, **k: pytest.fail("downloaded again"))`.
8. Run scripts both ways: import for logic tests; `subprocess` for CLI, exit code and stderr (`test-failure-paths`). Use `parametrize` for input classes and seeds.
9. Commands: `pytest -q`, `pytest tests/python/test_x.py::test_name`, `pytest --network`, `pytest --collect-only -q`; format `black` and `ruff check`.
10. Remove debug test files before commit.

## Checks before finishing

- Tests pass from any working directory and leave no files in the repo.
- A second run gives the same result (no order or seed dependence).
- Tests need only the declared dev environment.

## Pitfalls

- Tests that write into the repo or home folder.
- Real service calls in the default run.
- Silent skips hiding missing dependencies: report skipped counts (`test-report`).
