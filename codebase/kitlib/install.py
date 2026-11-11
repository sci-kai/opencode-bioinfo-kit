#!/usr/bin/env python3
"""Install opencode 2 and store/check the backend API key (library module of opencode-kit).

Run codebase/opencode-kit.py instead of this file.
"""

import getpass
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from .common import die, find_opencode, info, opencode_json, opencode_major, require_v2, run_opencode, warn

INSTALLER = "https://opencode.ai/v2/install"


def check_prerequisites():
    """Stop early with a fix if something the kit needs is missing."""
    if sys.version_info < (3, 8):
        die(f"Python {platform.python_version()} found; 3.8 or newer is needed")
    if platform.system() not in ("Linux", "Darwin"):
        die(f"{platform.system()} is not supported; use Linux (or WSL) or macOS")
    for tool in ("bash", "curl", "git"):
        if not shutil.which(tool):
            die(f"'{tool}' not found on PATH; install it with your package manager")


def _run_installer(version, dry_run):
    """Download the official opencode 2 installer and run it."""
    # an exact version (2.x.y) is passed to the installer; 'latest' means newest
    args = [] if version == "latest" else ["--version", version]
    if dry_run:
        info(f"[dry-run] would download {INSTALLER} and run: bash <installer> {' '.join(args)}")
        return
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "install.sh"
        info(f"downloading the official installer {INSTALLER}")
        # curl, not urllib: opencode.ai rejects Python's default user agent (HTTP 403)
        dl = subprocess.run(["curl", "-fsSL", "-o", str(script), INSTALLER], capture_output=True, text=True)
        if dl.returncode != 0:
            die(f"{INSTALLER}: download failed ({dl.stderr.strip()}); check the network/proxy")
        # the installer puts the binary in ~/.opencode/bin and adds it to PATH in the shell rc
        res = subprocess.run(["bash", str(script), *args])
        if res.returncode != 0:
            die(f"opencode installer exited with {res.returncode}; see its output above")
    # make the fresh binary visible to this process
    os.environ["PATH"] = f"{Path.home() / '.opencode' / 'bin'}{os.pathsep}{os.environ['PATH']}"


def ensure_opencode(version="latest", upgrade_from_v1=False, dry_run=False):
    """Return the opencode 2 binary, installing it when missing."""
    if version != "latest" and not version.startswith("2."):
        die(f"--opencode-version {version}: only opencode 2.x is supported (latest or 2.x.y)")
    exe = find_opencode()
    major = opencode_major(exe) if exe else None
    if exe and major == 2:
        info(f"opencode 2 already installed at {exe}; keeping it")
        return exe
    if exe and major == 1 and not upgrade_from_v1:
        die(
            f"{exe} is opencode 1.x, which this configuration does not support. opencode 2 "
            "migrates ~/.local/share/opencode on first start, so going back is not possible. "
            "Optional safety copy: cp -a ~/.local/share/opencode ~/.local/share/opencode_backup_v1 ; "
            "then re-run with --upgrade-from-v1"
        )
    if exe and major == 1:
        warn("replacing opencode 1 with opencode 2 (one-way; the data folder is migrated on first start)")
    _run_installer(version, dry_run)
    if dry_run:
        return find_opencode()
    return require_v2(find_opencode())


def provider_info(config):
    """(provider id, label, base URL, model ids used by any agent) of a built config."""
    if len(config["providers"]) != 1:
        die(f"expected exactly one provider in the backend, found {sorted(config['providers'])}")
    ((pid, pdef),) = config["providers"].items()
    refs = [a["model"] for a in config["agents"].values()] + [config["model"]]
    # 'provider/model#variant' -> 'model'
    used = {r.split("/", 1)[1].split("#", 1)[0] for r in refs}
    return pid, pdef.get("name", pid), pdef["settings"]["baseURL"].rstrip("/"), used


def check_key(base_url, key, used_models):
    """Call <base_url>/models with the key; stop on auth errors, warn on missing models."""
    url = f"{base_url}/models"
    req = urllib.request.Request(url)
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            listing = json.load(resp)
    except urllib.error.HTTPError as err:
        if err.code in (401, 403):
            die(f"{url}: HTTP {err.code}; the API key was rejected, create a new one")
        die(f"{url}: HTTP {err.code} ({err.reason})")
    except urllib.error.URLError as err:
        die(f"{url}: not reachable ({err.reason}); check settings.baseURL in the backend.json and the network")
    except (socket.timeout, TimeoutError):
        die(f"{url}: no answer within 60 s; check the network/proxy and try again")
    except ValueError as err:  # includes json.JSONDecodeError and UnicodeDecodeError
        die(f"{url}: answer is not JSON ({err}); expected an OpenAI-style model list, check settings.baseURL")
    except OSError as err:
        die(f"{url}: connection failed ({err}); check the network and try again")
    if not isinstance(listing, dict) or not isinstance(listing.get("data", []), list):
        die(f"{url}: expected a JSON object with a 'data' list of models, got {type(listing).__name__}; check settings.baseURL")
    available = {m.get("id") for m in listing.get("data", []) if isinstance(m, dict)}
    info(f"{base_url}: key accepted, {len(available)} models available")
    missing = sorted(used_models - available)
    if missing:
        warn(
            f"models used by this backend but not offered by the server: {', '.join(missing)}; "
            "update configs/backends/<backend>/backend.json (see docs/kiconnect-models.md)"
        )


def stored_providers(exe):
    """Provider ids with a stored credential ('opencode auth list'), or None."""
    entries = opencode_json(exe, ["auth", "list", "--format", "json"], retries=5)
    if entries is None:
        return None
    # only the presence of a connection is checked; keys are never printed
    return {e["id"] for e in entries if e.get("connections")}


def store_key(exe, pid, label, key):
    """Store the key in opencode 2's credential store via 'opencode auth import'."""
    # same format as 'opencode auth export'; the key goes over stdin, never argv
    payload = [{
        "id": f"cred_{pid}_{secrets.token_hex(6)}",
        "integrationID": pid,
        "label": label,
        "active": True,
        "value": {"type": "key", "key": key},
    }]
    res = run_opencode(exe, ["auth", "import"], retries=5, stdin=json.dumps(payload))
    if res is None or res.returncode != 0:
        detail = res.stderr.strip()[-300:] if res else "timeout"
        die(f"'opencode auth import' failed ({detail}); use 'opencode auth login {pid} --method key' instead")
    info(f"stored the key for '{pid}' with 'opencode auth import'")


def handle_key(exe, config, api_key_env=None, replace=False, dry_run=False):
    """Make sure a working key for the backend's provider is stored."""
    pid, label, base_url, used = provider_info(config)
    stored = stored_providers(exe) if exe else set()
    if stored and pid in stored and not replace:
        info(f"a key for '{pid}' is already stored (use --replace-key to change it)")
        return
    if api_key_env:
        key = os.environ.get(api_key_env, "")
        if not key:
            die(f"--api-key-env {api_key_env}: variable is empty or not set")
    elif sys.stdin.isatty():
        key = getpass.getpass(f"API key for {label} ({pid}), input hidden: ").strip()
    elif pid == "lmstudio":
        # LM Studio runs without a token by default; its server is checked by configure-lmstudio
        info("no terminal to ask for an LM Studio token; continuing without one (pass --api-key-env VAR if your server needs one)")
        return
    else:
        die("no terminal to ask for the key; pass --api-key-env VAR or --no-key")
    if not key and pid != "lmstudio":
        die("empty API key")
    check_key(base_url, key, used)
    if not key:
        return
    if dry_run:
        info(f"[dry-run] would store the key for provider '{pid}'")
        return
    store_key(exe, pid, label, key)


if __name__ == "__main__":
    sys.exit("ERROR: library module; run codebase/opencode-kit.py")
