#!/usr/bin/env python3
"""Shared paths and helpers of the opencode-kit (library module).

Run codebase/opencode-kit.py instead of this file.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# repo layout -----------------------------------------------------------------
REPO = Path(__file__).resolve().parent.parent.parent
CONFIGS = REPO / "configs"
SKILLS = REPO / "skills"
CUBI = REPO / "cubi-rules"
KB_WIKI = CUBI / "knowledge-base.wiki"
KB_SOURCE = CUBI / "kb-source.json"
DIGEST = CUBI / "cubi-rules-condensed.md"
BUILD = REPO / "generated"
SUBMODULES = {"kb": KB_WIKI, "bionemo": SKILLS / "bionemo-agent-toolkit"}

# deployment targets (opencode 2 global locations) ------------------------------


def _xdg_dir(var, fallback, env=None):
    """$<var>/opencode when <var> is an absolute path (XDG spec), else ~/<fallback>/opencode."""
    env = os.environ if env is None else env
    value = env.get(var) or ""
    # XDG Base Directory spec: relative values are invalid and must be ignored
    base = Path(value) if os.path.isabs(value) else Path.home() / fallback
    return base / "opencode"


def config_dir(env=None):
    """opencode's global config folder: $XDG_CONFIG_HOME/opencode, else ~/.config/opencode."""
    return _xdg_dir("XDG_CONFIG_HOME", ".config", env)


def data_dir(env=None):
    """opencode's data folder (credentials, sessions): $XDG_DATA_HOME/opencode, else ~/.local/share/opencode."""
    return _xdg_dir("XDG_DATA_HOME", os.path.join(".local", "share"), env)


OC_CONFIG_DIR = config_dir()
OC_DATA_DIR = data_dir()
OC_SKILLS_DIR = OC_CONFIG_DIR / "skills"
OC_KB_DIR = OC_CONFIG_DIR / "cubi-kb"
SUPPORTED_MAJOR = 2


def die(msg):
    """Print an ERROR: message to stderr and exit non-zero."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg):
    """Print an INFO: message to stderr."""
    print(f"INFO: {msg}", file=sys.stderr)


def warn(msg):
    """Print a WARNING: message to stderr."""
    print(f"WARNING: {msg}", file=sys.stderr)


def load_json(path, expect=None, fix=None):
    """Load a JSON file; stop with the file name, the problem and a fix on failure.

    expect: required top-level type (dict or list), checked when given.
    fix: what the user should do; default: repair the syntax (e.g. a trailing comma).
    """
    fix = fix or "fix the syntax, e.g. a trailing comma"
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        die(f"{path}: file not found")
    except UnicodeDecodeError as err:
        die(f"{path}: not UTF-8 text ({err}); {fix}")
    except json.JSONDecodeError as err:
        die(f"{path}: invalid JSON ({err}); {fix}")
    except OSError as err:
        die(f"{path}: cannot read ({err.strerror or err}); check the file permissions, or {fix}")
    if expect is not None and not isinstance(data, expect):
        wanted = "object" if expect is dict else "array" if expect is list else expect.__name__
        die(f"{path}: top level is a JSON {type(data).__name__}, expected a JSON {wanted}; {fix}")
    return data


def write_atomic(path, text, fsync=False):
    """Write text to path via a temp file in the same folder and os.replace.

    A crash or a full disk leaves either the old or the new file, never half of one.
    A symlink at `path` is kept: the text goes to the file it points to.
    """
    path = Path(path)
    if path.is_symlink():
        # keep the user's symlink (e.g. a config kept in a dotfiles repo): write its target
        target = Path(os.path.realpath(str(path)))
        info(f"{path} is a symlink; writing through to its target {target}")
        path = target
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            if fsync:
                fh.flush()
                os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def is_within(child, parent):
    """True when `child` is `parent` or below it (separator-aware; paths are not resolved)."""
    child, parent = os.path.abspath(str(child)), os.path.abspath(str(parent))
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:  # different drives (Windows)
        return False


def render(obj):
    """Serialise JSON the way the repo stores it: 2 spaces, trailing newline."""
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def git(args, cwd=REPO, check=True):
    """Run git and return stdout; stop with git's message on failure."""
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and res.returncode != 0:
        die(f"git {' '.join(args)} (in {cwd}) failed: {res.stderr.strip()}")
    return res.stdout.strip()


def ensure_submodules(names=("kb", "bionemo"), dry_run=False):
    """Initialise missing submodules (a clone without --recursive has empty dirs).

    In a dry run nothing is changed: missing submodules stop with the command to run.
    """
    missing = [n for n in names if not (SUBMODULES[n] / ".git").exists()]
    if not missing:
        return
    paths = [str(SUBMODULES[n].relative_to(REPO)) for n in missing]
    if dry_run:
        die(
            f"submodule(s) {', '.join(paths)} not initialised, and a dry run changes nothing; "
            f"run: git -C {REPO} submodule update --init (or the same command without --dry-run)"
        )
    info(f"initialising submodule(s) {', '.join(paths)} (git submodule update --init)")
    git(["submodule", "update", "--init", *paths])


# opencode binary ---------------------------------------------------------------
def find_opencode():
    """Path of the opencode binary: PATH first, then the installer's default."""
    exe = shutil.which("opencode")
    if exe:
        return exe
    default = Path.home() / ".opencode" / "bin" / "opencode"
    return str(default) if default.is_file() else None


def opencode_version(exe):
    """Installed opencode version string (e.g. '2.2.6'), or None."""
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    # output is e.g. "opencode v2.2.6" (2.x) or "1.18.14" (1.x)
    match = re.search(r"(\d+\.\d+\.\d+)", out.stdout + out.stderr)
    return match.group(1) if match else None


def opencode_major(exe):
    """Major version of the installed opencode, or None if unknown."""
    version = opencode_version(exe)
    return int(version.split(".")[0]) if version else None


def require_v2(exe):
    """Stop with a fix unless opencode 2.x is installed; return the binary path."""
    if not exe:
        die("opencode not found; run: codebase/opencode-kit.py setup-opencode <backend>")
    major = opencode_major(exe)
    if major == 1:
        die(
            f"{exe} is opencode 1.x, which this configuration does not support. Upgrade "
            "(one-way, see docs/upgrading-from-opencode-1.md): "
            "codebase/opencode-kit.py setup-opencode <backend> --upgrade-from-v1"
        )
    if major != SUPPORTED_MAJOR:
        die(f"{exe}: opencode major version {major} unknown/unsupported (expected {SUPPORTED_MAJOR}.x)")
    return exe


# one-shot opencode commands: at most MAX_TRIES tries, ONE_SHOT_TIMEOUT seconds each
MAX_TRIES = 3
ONE_SHOT_TIMEOUT = 60


def _retry_info(args, attempt, tries):
    """INFO line before a retry, so a slow start-up is visible."""
    info(f"retrying 'opencode {' '.join(args[:2])}' (try {attempt} of {tries})")


STARTUP_FLAKE = "Location plugins did not finish activating"
FLAKE_TRIES = 10  # the flake fails within seconds; hangs and other errors count against MAX_TRIES


def run_opencode(exe, args, retries=MAX_TRIES, stdin=None, cwd=None, timeout=180, standalone=True):
    """Run an opencode 2 subcommand, retrying failures.

    opencode 2.2.6 often fails at start-up with 'Location plugins did not finish
    activating' (seen on ARM64, sometimes several times in a row); that fails within
    seconds, so it is retried up to FLAKE_TRIES times. Timeouts and other failures count
    against `retries` (at most MAX_TRIES), which bounds the worst case. Returns the last
    CompletedProcess, or None when every try timed out or could not start.
    """
    cmd = [exe, *args] + (["--standalone"] if standalone else [])
    env = {**os.environ, "OPENCODE_DISABLE_MODELS_FETCH": "1"}
    budget = max(1, min(retries, MAX_TRIES))
    last, failures = None, 0
    for attempt in range(1, FLAKE_TRIES + 1):
        if attempt > 1:
            _retry_info(args, attempt, FLAKE_TRIES)
            time.sleep(3)
        try:
            last = subprocess.run(
                cmd, input=stdin, capture_output=True, text=True, timeout=timeout, env=env, cwd=cwd or Path.home()
            )
        except (subprocess.TimeoutExpired, OSError):
            last = None
        if last is not None and last.returncode == 0:
            return last
        if last is None or STARTUP_FLAKE not in (last.stderr or ""):
            failures += 1
            if failures >= budget:
                break
    return last


def opencode_json(exe, args, retries=MAX_TRIES, cwd=None, timeout=ONE_SHOT_TIMEOUT):
    """Run an opencode command that prints JSON; return the parsed value or None.

    Start-up flakes are retried inside run_opencode; output that is not JSON counts as
    one failed try (at most MAX_TRIES), each run limited to `timeout` seconds.
    """
    tries = max(1, min(retries, MAX_TRIES))
    for attempt in range(1, tries + 1):
        if attempt > 1:
            _retry_info(args, attempt, tries)
            time.sleep(3)
        res = run_opencode(exe, args, retries=tries - attempt + 1, cwd=cwd, timeout=timeout)
        if res is None or res.returncode != 0:
            return None  # run_opencode already used the retry budget
        try:
            return json.loads(res.stdout)
        except json.JSONDecodeError:
            pass
    return None


if __name__ == "__main__":
    sys.exit("ERROR: library module; run codebase/opencode-kit.py")
