#!/usr/bin/env python3
"""Per-user directory settings: which folders outside the project opencode may use.

The repository holds no machine-specific paths. Each user states their own folders once;
they are stored in ~/.config/opencode/opencode-kit-settings.json (outside the repo) and
rendered into the permission rules and the global agent rules at deploy time.

Keys (absolute paths as the user wrote them, symlinks not resolved; null = not
configured, i.e. no access):
    conda_base      the conda installation (auto-detected with `conda info --base`)
    envs_dir        folder with project conda prefix envs and their spec files
    scratch_dir     folder for large data, pipeline runs, caches, Nextflow work dirs
    scratch_mount   mount point to check before using scratch_dir (removable disks)
    tmp_dir         temporary files of agents (default <system temp>/opencode-<user>)
    extra_dirs      list of further folders the user grants
    lmstudio_url    LM Studio server URL (only for the 'local' backend)
    lmstudio_models LM Studio model set: models and which one runs each tier (kitlib/lmstudio.py)

Run codebase/opencode-kit.py instead of this file.
"""

import datetime
import getpass
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from . import common
from .common import OC_CONFIG_DIR, die, info, is_within, load_json, render, warn, write_atomic

SETTINGS_FILE = OC_CONFIG_DIR / "opencode-kit-settings.json"
DIR_KEYS = ("conda_base", "envs_dir", "scratch_dir", "scratch_mount", "tmp_dir")


def _user_name():
    """Login name for the per-user temp folder (falls back to the numeric uid)."""
    try:
        return getpass.getuser()
    except (KeyError, OSError, ImportError):
        return str(os.getuid()) if hasattr(os, "getuid") else "user"


# Design decision: one temp folder per user (mode 0700) so two users on one machine
# don't share agent temp files; rejected: a fixed /tmp/opencode (collides, world-readable).
# A tmp_dir saved by an older kit (/tmp/opencode) is kept as it is.
DEFAULT_TMP = os.path.join(tempfile.gettempdir(), f"opencode-{_user_name()}")
# Design decision: refuse folders that would open far more than intended (the whole
# disk, the whole home or a parent of it, system or credential folders, the parents of
# credential folders); rejected: trusting any input. Deeper folders (/tmp/x, /mnt/disk)
# stay allowed.
FORBIDDEN = {
    "/", "/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64", "/boot", "/dev", "/proc", "/sys",
    "/var", "/var/tmp", "/var/lib", "/dev/shm", "/root", "/home", "/Users", "/tmp", "/private",
    "/private/etc", "/private/var", "/private/tmp", "/private/var/tmp", "/opt", "/mnt", "/media",
    "/srv", "/run", "/Library", "/System", "/Applications", "/Volumes",
}
# system trees: the folder and everything below it is refused
FORBIDDEN_TREES = ("/etc", "/proc", "/sys", "/dev", "/boot", "/private/etc")
# below the home folder: credentials of other tools; '.config/opencode' and
# '.local/share/opencode' are opencode's config and credential store (their XDG
# locations are refused as well, see _secret_dirs)
FORBIDDEN_HOME_PARTS = (
    ".ssh", ".gnupg", ".aws", ".local/share/opencode", ".config/opencode", ".claude",
    ".config/gh", ".kube", ".docker", ".password-store", ".netrc", ".git-credentials",
)
# macOS file systems are case-insensitive by default: /ETC is /etc there
CASE_INSENSITIVE = sys.platform == "darwin"
# a folder name with these would become a wildcard in the permission rules
GLOB_CHARS = set("*?[]{}")

QUESTIONS = {
    "conda_base": "Conda installation (base prefix)",
    "envs_dir": "Folder for project conda envs and their spec files (empty = none)",
    "scratch_dir": "Scratch folder for large data, runs and caches (empty = none)",
    "scratch_mount": "Mount point to check before using the scratch folder (empty = none)",
    "tmp_dir": "Temporary folder for agents",
    "extra_dirs": "Further folders opencode may use, comma-separated (empty = none)",
    "lmstudio_url": "LM Studio server URL, e.g. http://localhost:1234/v1",
}
RECONFIGURE = "codebase/opencode-kit.py configure-directories"


def load():
    """Saved settings, or None when the user has not configured them yet."""
    if not SETTINGS_FILE.is_file():
        return None
    return load_json(
        SETTINGS_FILE, expect=dict,
        fix=f"repair the file, or delete it and run: {RECONFIGURE}",
    )


def save(settings):
    """Write the settings file (atomic) with a timestamp."""
    record = dict(settings, updated=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    write_atomic(SETTINGS_FILE, render(record))
    info(f"saved directory settings to {SETTINGS_FILE}")


def detect_conda_base():
    """`conda info --base`, or None when conda is not on PATH."""
    exe = shutil.which("conda")
    if not exe:
        return None
    try:
        res = subprocess.run([exe, "info", "--base"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    return res.stdout.strip() or None


def suggestions():
    """Defaults offered to a new user (detected where possible, else empty)."""
    return {
        "conda_base": detect_conda_base(),
        "envs_dir": None,
        "scratch_dir": None,
        "scratch_mount": None,
        "tmp_dir": DEFAULT_TMP,
        "extra_dirs": [],
        "lmstudio_url": None,
    }


def _homes():
    """The home folder as written and resolved (they differ when home is a symlink)."""
    home = os.path.abspath(os.path.expanduser("~"))
    return {home, os.path.realpath(home)}


def _fold(path):
    """Path as compared: lower-case on case-insensitive macOS, unchanged elsewhere."""
    return path.lower() if CASE_INSENSITIVE else path


def _secret_dirs():
    """Credential folders/files that are never granted: home parts plus opencode's real dirs."""
    secrets = {os.path.join(home, part) for home in _homes() for part in FORBIDDEN_HOME_PARTS}
    # opencode's own folders where they really are ($XDG_CONFIG_HOME, $XDG_DATA_HOME)
    for folder in (common.OC_CONFIG_DIR, common.OC_DATA_DIR):
        secrets.update({os.path.abspath(str(folder)), os.path.realpath(str(folder))})
    return sorted(secrets)


def _too_broad(path):
    """Why `path` (absolute) must not be granted, or None when it is fine."""
    folded = _fold(path)
    if folded in {_fold(f) for f in FORBIDDEN}:
        return "is a system folder or a root of other users' data; choose a dedicated folder below it"
    for tree in FORBIDDEN_TREES:
        if is_within(folded, _fold(tree)):
            return f"is below the system folder {tree}; choose a folder of your own"
    for home in _homes():
        if folded == _fold(home) or is_within(_fold(home), folded):
            return "is your home folder or a parent of it; choose a dedicated folder below it"
    for secret in _secret_dirs():
        if is_within(folded, _fold(secret)):
            return "holds credentials or opencode's own config and is never accessible to agents"
        if is_within(_fold(secret), folded):
            return f"contains {secret} (credentials or opencode's own config); choose a dedicated folder"
    return None


def check_glob(value, key, shown=None):
    """Stop when a path contains characters that act as wildcards in permission rules."""
    if GLOB_CHARS & set(value):
        where = f"'{value}'" if shown is None else f"'{shown}' (-> '{value}')"
        die(
            f"{key}: {where} contains one of {' '.join(sorted(GLOB_CHARS))}, which would act as a "
            "wildcard in the permission rules; rename the folder or choose another one"
        )


def _check_not_shared(path, key):
    """Stop when a folder is writable by everyone and owned by someone else.

    Another user could then plant files (scripts, configs) that agents later run or read.
    Skipped where the platform has no user IDs (Windows).
    """
    if not hasattr(os, "getuid"):
        return
    try:
        st = os.stat(path)
    except OSError:
        return  # missing: reported by the caller
    if st.st_mode & stat.S_IWOTH and st.st_uid != os.getuid():
        die(
            f"{key}: '{path}' is writable by every user (mode {oct(stat.S_IMODE(st.st_mode))}) and owned by "
            f"uid {st.st_uid}, not by you (uid {os.getuid()}); other users could plant files there. "
            f"Choose a folder you own, e.g. a new one below it (mkdir -m 700 {path}/<name>)"
        )


def check_private_tmp(path, key="tmp_dir"):
    """The temp folder must be a real folder (no symlink) of this user, closed to others.

    Owned by the user but open to group/others: tightened to 0700 (INFO). Anything else
    stops, since another user could read or plant the agents' temp files. Skipped where
    the platform has no user IDs (Windows).
    """
    if not hasattr(os, "getuid"):
        return
    fix = "choose another temp folder with --tmp-dir (e.g. a new folder below your scratch folder)"
    try:
        st = os.lstat(str(path))
    except OSError as err:
        die(f"{key}: cannot inspect '{path}' ({err.strerror or err}); {fix}")
    if stat.S_ISLNK(st.st_mode):
        die(f"{key}: '{path}' is a symlink (to {os.path.realpath(str(path))}), expected a real folder; {fix}")
    if not stat.S_ISDIR(st.st_mode):
        die(f"{key}: '{path}' is not a folder; {fix}")
    mode = stat.S_IMODE(st.st_mode)
    if st.st_uid != os.getuid():
        die(f"{key}: '{path}' is owned by uid {st.st_uid} (mode {oct(mode)}), expected you (uid {os.getuid()}); {fix}")
    if mode & 0o077:
        try:
            os.chmod(str(path), 0o700)
        except OSError as err:
            die(f"{key}: '{path}' has mode {oct(mode)} and cannot be set to 0700 ({err.strerror or err}); {fix}")
        info(f"{key}: '{path}' had mode {oct(mode)} (open to group/others); set it to 0700")


def normalise_dir(value, key, create=True):
    """Absolute, checked folder path (symlinks kept as written), or None for empty.

    Stops on unsafe paths. Both the path as written and its resolved target are checked,
    so a symlink can't smuggle in a forbidden folder or a wildcard character. A missing
    tmp_dir is created (mode 0700) when `create` is true; an existing one must be a
    private folder of this user (check_private_tmp, re-checked on every resolve).
    """
    if value is None or (isinstance(value, str) and value.strip() in ("", "none", "n/a")):
        return None
    if not isinstance(value, str):
        die(
            f"{key}: expected a folder path (text) or null, got {type(value).__name__} {value!r}; "
            f"fix {SETTINGS_FILE} or run: {RECONFIGURE}"
        )
    check_glob(value, key)
    written = os.path.abspath(os.path.expanduser(value))
    resolved = os.path.realpath(written)
    check_glob(resolved, key, shown=written)
    for form in sorted({written, resolved}):
        reason = _too_broad(form)
        if reason:
            shown = form if form == written else f"{written} (-> {form})"
            die(f"{key}: '{shown}' {reason}")
    path = Path(written)
    if key == "scratch_mount":
        if not path.is_dir():
            die(f"{key}: mount point '{path}' does not exist; mount the disk or leave it empty")
        return written
    if key == "tmp_dir":
        if not os.path.lexists(written):
            if not create:
                return written  # created later (deploy) or never (dry run)
            make_private_dir(path, key)
        check_private_tmp(written, key)
        return written
    if not path.exists():
        die(f"{key}: folder '{path}' does not exist; create it first (mkdir -p {path}) or leave it empty")
    if not path.is_dir():
        die(f"{key}: '{path}' is not a folder")
    _check_not_shared(resolved, key)
    return written


def make_private_dir(path, key="tmp_dir"):
    """Create a folder only the user can access, then check it (check_private_tmp).

    The check also catches a folder someone else created first (exist_ok race).
    """
    try:
        os.makedirs(str(path), mode=0o700, exist_ok=True)
    except OSError as err:
        die(
            f"{key}: cannot create '{path}' ({err.strerror or err}); create it yourself "
            f"(mkdir -m 700 -p {path}) or choose another folder with --{key.replace('_', '-')}"
        )
    check_private_tmp(path, key)


def finalise(raw, backend, create=True):
    """Validate a raw settings dict; returns the normalised dict."""
    out = {key: normalise_dir(raw.get(key), key, create) for key in DIR_KEYS}
    out["tmp_dir"] = out["tmp_dir"] or normalise_dir(DEFAULT_TMP, "tmp_dir", create)
    extra = raw.get("extra_dirs")
    if extra is None:
        extra = []
    elif isinstance(extra, str):
        extra = [e.strip() for e in extra.split(",")]
    elif not isinstance(extra, list) or not all(isinstance(e, str) for e in extra):
        die(
            f"extra_dirs: expected a list of folder paths (text) or a comma-separated text, got {extra!r}; "
            f"fix {SETTINGS_FILE} or run: {RECONFIGURE}"
        )
    out["extra_dirs"] = sorted({d for d in (normalise_dir(e, "extra_dirs", create) for e in extra) if d})
    if out["scratch_mount"] and not out["scratch_dir"]:
        die("scratch_mount is set but scratch_dir is not; set both or neither")
    if out["scratch_dir"] and out["scratch_mount"]:
        below = is_within(out["scratch_dir"], out["scratch_mount"]) or is_within(
            os.path.realpath(out["scratch_dir"]), os.path.realpath(out["scratch_mount"])
        )
        if not below:
            die(
                f"scratch_dir '{out['scratch_dir']}' is not below scratch_mount '{out['scratch_mount']}'; "
                "choose a scratch folder on the mounted disk or fix the mount point"
            )
    from .lmstudio import normalise_url  # lmstudio imports common only

    out["lmstudio_url"] = normalise_url(raw.get("lmstudio_url"))
    out["lmstudio_models"] = raw.get("lmstudio_models") or None
    if backend == "local" and not out["lmstudio_url"]:
        die("the local backend needs lmstudio_url (e.g. --lmstudio-url http://localhost:1234/v1)")
    return out


def ask(current):
    """Interactive questions; Enter keeps the value in brackets."""
    print("\nDirectories opencode may use outside the project folder (strict: nothing else).", file=sys.stderr)
    print("Always allowed: the project, this toolkit, ~/.config/opencode, ~/.conda, ~/.nextflow,", file=sys.stderr)
    print("~/.singularity, ~/.apptainer. Empty answer = not configured; '-' clears a value.\n", file=sys.stderr)
    answers = {}
    for key, question in QUESTIONS.items():
        value = current.get(key)
        shown = ", ".join(value) if isinstance(value, list) else (value or "")
        reply = input(f"{question} [{shown}]: ").strip()
        if reply == "-":
            answers[key] = [] if key == "extra_dirs" else None
        elif reply:
            answers[key] = reply
        else:
            answers[key] = value
    return answers


def resolve(backend, interactive, overrides=None, reconfigure=False, create=True, allow_example=True):
    """(settings for this deploy, changed against the saved file); writes nothing.

    Saved file + CLI overrides; asks when not yet confirmed. Directories count as
    confirmed once the user answered the questions or passed folder flags; until then
    every deploy asks again (or warns without a terminal), even if the file already
    exists because e.g. configure-lmstudio saved the LM Studio part first.

    Without the questions, an unconfirmed setup grants only the temp folder, what was
    saved before and the folders given as flags: detected values (conda base) are
    only suggested, so a flag never confirms a folder the user did not name.

    Local backend: the LM Studio model set is chosen again whenever the final server URL
    differs from the saved one (flag or answer), unless a set is given with it. Without a
    set and a reachable server, allow_example decides: True (dry run) builds with the
    example set and a warning, False (a real deploy) stops.
    """
    saved = load()
    overrides = {k: v for k, v in (overrides or {}).items() if v not in (None, [], "")}
    dir_override = any(k in overrides for k in (*DIR_KEYS, "extra_dirs"))
    suggested = suggestions()
    base = {**suggested, **(saved or {})}
    need_ask = saved is None or not saved.get("directories_confirmed") or reconfigure
    if need_ask and interactive and not dir_override:
        raw = {**base, **ask(base), **overrides}  # answers update, never drop, saved keys
        confirmed = True
    elif need_ask:
        # only the temp folder is granted without asking; detected folders stay suggestions
        unasked = {k: (v if k == "tmp_dir" else None) for k, v in suggested.items() if k in (*DIR_KEYS, "extra_dirs")}
        raw = {**suggested, **unasked, **(saved or {}), **overrides}
        confirmed = dir_override or bool((saved or {}).get("directories_confirmed"))
        if not confirmed:
            hint = ""
            if suggested.get("conda_base") and not raw.get("conda_base"):
                hint = f" Detected conda base {suggested['conda_base']} is NOT granted (pass --conda-base to grant it)."
            warn(
                "directories not confirmed yet: only the temp folder, saved folders and folder flags "
                f"are allowed.{hint} Confirm them with: {RECONFIGURE}"
            )
    else:
        raw = {**saved, **overrides}
        confirmed = True
    settings = finalise(raw, backend, create)
    settings["directories_confirmed"] = confirmed
    # local backend: pick the LM Studio models once (asks the server what it has); a
    # different server (new URL from a flag or an answer) has other models: choose again
    saved_url = (saved or {}).get("lmstudio_url")
    url_changed = saved is not None and settings["lmstudio_url"] != saved_url
    if backend == "local" and not overrides.get("lmstudio_models") and (
        not settings.get("lmstudio_models") or url_changed
    ):
        from .lmstudio import api_key, choose

        chosen = choose(settings["lmstudio_url"], key=api_key(), interactive=interactive,
                        current=settings.get("lmstudio_models"))
        if chosen:
            settings["lmstudio_models"] = chosen
        elif settings.get("lmstudio_models"):
            if url_changed:
                warn(f"LM Studio at {settings['lmstudio_url']} not reachable: keeping the saved model set, which "
                     f"was chosen for the previous server {saved_url or '(none)'} and is unchecked for this one; "
                     "choose again when the server runs: codebase/opencode-kit.py configure-lmstudio")
        elif allow_example:
            warn("LM Studio not reachable: the example model set is used until you choose yours with: "
                 "codebase/opencode-kit.py configure-lmstudio (or --models-file to define it offline)")
        else:
            die(f"LM Studio at {settings['lmstudio_url']} not reachable and no model set saved, so the local "
                "config can't be built; start the LM Studio server (Developer -> Start server) and deploy again, "
                "or define the set offline: codebase/opencode-kit.py configure-lmstudio --models-file <file> "
                "(example: configs/backends/local/lmstudio-models.example.json)")
    # only rewrite the file when something changed (keeps its timestamp meaningful)
    changed = saved is None or any(saved.get(k) != v for k, v in settings.items())
    return settings, changed


def persist(settings, changed, dry_run=False):
    """Create the temp folder and save the settings when they changed (nothing in a dry run)."""
    tmp = settings.get("tmp_dir")
    if dry_run:
        if tmp and not os.path.isdir(tmp):
            info(f"[dry-run] would create the temp folder {tmp} (mode 0700)")
        if changed:
            shown = {k: settings.get(k) for k in (*DIR_KEYS, "extra_dirs", "lmstudio_url")}
            info(f"[dry-run] would save directory settings to {SETTINGS_FILE}: {render(shown).strip()}")
        return
    if tmp and not os.path.isdir(tmp):
        make_private_dir(tmp)
    if changed:
        save(settings)


def ensure(backend, interactive, overrides=None, reconfigure=False, dry_run=False):
    """Settings for this deploy (see resolve); saved unless dry_run."""
    settings, changed = resolve(backend, interactive, overrides, reconfigure, create=not dry_run)
    persist(settings, changed, dry_run)
    return settings


def allowed_dirs(settings):
    """Folders granted by the user (deduplicated, sorted)."""
    dirs = [settings.get(k) for k in ("conda_base", "envs_dir", "scratch_dir", "tmp_dir")]
    dirs += settings.get("extra_dirs") or []
    return sorted({d for d in dirs if d})


def describe(settings):
    """Human-readable summary of the settings (never fails on a hand-edited file)."""
    lines = [f"Directory settings ({SETTINGS_FILE}):"]
    for key in (*DIR_KEYS, "extra_dirs", "lmstudio_url"):
        value = settings.get(key)
        shown = ", ".join(str(v) for v in value) if isinstance(value, list) else value
        lines.append(f"  {key:14} {shown or 'not configured'}")
    models = settings.get("lmstudio_models")
    if models:
        from .lmstudio import ModelSetError, describe as describe_models, local_backend, validate

        backend = local_backend()
        try:
            checked = validate(models, backend["tiers"], "lmstudio_models", backend.get("tier_roles"))
            lines += [f"  {line}" for line in describe_models(checked)]
        except ModelSetError as err:
            lines.append(f"  lmstudio_models INVALID: {err}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit("ERROR: library module; run codebase/opencode-kit.py")
