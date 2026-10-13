"""Checking for a newer release, and upgrading to it on Quit.

An install from git (`uv tool install git+<url>`) records where it came
from in `direct_url.json` (PEP 610): the repository's URL, and the
branch, tag, or commit asked for (none: the default branch, `main`, the
newest release). At start the app lists the repository's tags with
`git ls-remote` (uv itself needs git to install from git, so it's
there) and compares the newest release's with its own version. Only an
install that follows a branch is checked, as `uv tool upgrade` doesn't
move one made from a tag or a commit; a clone run (`uv run`) isn't an
install from git, so it's never checked.

`uv tool list --outdated` can't stand in for this: it asks PyPI for the
package by name, whatever the tool was installed from.
"""

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from importlib.metadata import distribution

from pota_logger.app_version import DEV_MARK, PROGRAM_ID, package_version

# The toast when a newer release is found, as dictated (2026-10-12).
NEW_VERSION = "Version {version} is available.\nQuit, then run: uv tool upgrade pota-logger"

# The command that upgrades the app, as installed.
UPGRADE_COMMAND = ["uv", "tool", "upgrade", PROGRAM_ID]

# How long the check may take in all, so a poor connection can't keep
# it going; it runs in the background, and is dropped on Quit.
CHECK_TIMEOUT_SECONDS = 20

# A release's tag: its calendar version (see REQUIREMENTS.md
# Versioning). Other tags (`MVP`) aren't releases.
RELEASE_TAG = re.compile(r"\d+(\.\d+){2,3}")


@dataclass
class InstallSource:
    """Where an install from git came from: the repository's `url`, and
    the branch, tag, or commit asked for (`revision`, None for the
    default branch).
    """

    url: str
    revision: str | None


def install_source(direct_url: str | None) -> InstallSource | None:
    """The source in a `direct_url.json`'s text, or None if it isn't an
    install from git.
    """
    try:
        info = json.loads(direct_url or "{}")
        vcs_info = info.get("vcs_info", {})
        url, vcs = info.get("url"), vcs_info.get("vcs")
        revision = vcs_info.get("requested_revision")
    except (ValueError, AttributeError):
        return None
    if vcs != "git" or not isinstance(url, str) or not url:
        return None
    return InstallSource(url, revision if isinstance(revision, str) and revision else None)


def installed_source() -> InstallSource | None:
    """The app's own install source, or None if it isn't from git."""
    return install_source(distribution(PROGRAM_ID).read_text("direct_url.json"))


def version_key(version: str) -> tuple[int, ...]:
    """A release version's numbers, to compare (`2026.10.12.1`)."""
    return tuple(int(part) for part in version.split("."))


def release_version(version: str) -> str:
    """The release a version is or follows: a dev version without `+dev`."""
    return version.split(DEV_MARK)[0]


def newer_release(ls_remote: str, source: InstallSource, version: str) -> str | None:
    """The newest release tag in `git ls-remote --heads --tags` output, if
    it's newer than `version` (the app's, or the release it follows) and
    the install follows a branch there, else None.
    """
    heads, tags = set(), []
    for line in ls_remote.splitlines():
        _, _, ref = line.partition("\t")
        if ref.startswith("refs/heads/"):
            heads.add(ref.removeprefix("refs/heads/"))
        elif ref.startswith("refs/tags/"):
            tag = ref.removeprefix("refs/tags/")
            if RELEASE_TAG.fullmatch(tag):
                tags.append(tag)
    if source.revision is not None and source.revision not in heads:
        return None
    newest = max(tags, key=version_key, default=None)
    current = release_version(version)
    if newest is None or not RELEASE_TAG.fullmatch(current):
        return None
    return newest if version_key(newest) > version_key(current) else None


def quiet_git_env(environ=os.environ) -> dict[str, str]:
    """git's environment for the check: never asking for a password, and
    giving up on a stalled connection rather than waiting on it.
    """
    env = dict(environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    # Under a second's kilobyte for 10 seconds counts as stalled (HTTPS).
    env.setdefault("GIT_HTTP_LOW_SPEED_LIMIT", "1000")
    env.setdefault("GIT_HTTP_LOW_SPEED_TIME", "10")
    # No password prompts, and a quick give-up on an unreachable server
    # (SSH), unless set otherwise already.
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=10")
    return env


def check_for_release(
    source: InstallSource, version: str | None = None, timeout: float = CHECK_TIMEOUT_SECONDS
) -> str | None:
    """The newest release, if newer than the app (`version`, the app's
    unless given), else None: also when git is missing, the server can't
    be reached in time, or anything else goes wrong, as a check that
    can't be made is no news.
    """
    git = shutil.which("git")
    if git is None:
        return None
    try:
        result = subprocess.run(
            [git, "ls-remote", "--heads", "--tags", "--refs", source.url],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=quiet_git_env(),
            # Off the terminal, so nothing can ask for a password on it
            # under the app's screen.
            start_new_session=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return newer_release(result.stdout, source, version or package_version())


def can_upgrade() -> bool:
    """Whether uv is there to upgrade the app with."""
    return shutil.which("uv") is not None


def upgrade() -> None:
    """Upgrade the app with uv, its output in the terminal (run after the
    app's screen is gone). Ctrl+C stops it.
    """
    try:
        subprocess.run(UPGRADE_COMMAND, env=quiet_git_env())
    except (OSError, KeyboardInterrupt):
        pass
