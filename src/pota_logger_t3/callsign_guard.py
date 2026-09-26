"""Git hooks that block commits containing the station callsign.

The callsign comes from data/settings.toml, which git ignores, so the
hooks themselves never contain it. Install with:

    uv run python -m pota_logger_t3.callsign_guard install
"""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

from pota_logger_t3.settings import SETTINGS_PATH, load_settings

HOOK_MARKER = "# pota_logger_t3 callsign guard"
HOOKS = {
    "pre-commit": "pre-commit",
    "commit-msg": 'commit-msg "$1"',
}


def callsign_pattern(callsign: str) -> re.Pattern[str]:
    """Match the callsign on its own, any case, not inside a longer word."""
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(callsign)}(?![A-Za-z0-9])", re.IGNORECASE)


def added_lines(diff: str) -> list[tuple[str, int, str]]:
    """(file, line number, text) for each added line in a unified diff."""
    lines = []
    path, line_no = "", 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].removeprefix("b/")
        elif line.startswith("@@"):
            line_no = int(re.search(r"\+(\d+)", line).group(1))
        elif line.startswith("+"):
            lines.append((path, line_no, line[1:]))
            line_no += 1
    return lines


def staged_findings(callsign: str, repo: Path = Path(".")) -> list[str]:
    """Where the callsign appears in staged changes, as file[:line]."""
    pattern = callsign_pattern(callsign)
    diff = subprocess.run(
        ["git", "diff", "--cached", "--no-color", "--unified=0"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    findings = []
    for path, line_no, text in added_lines(diff):
        if pattern.search(text):
            findings.append(f"{path}:{line_no}")
    names = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    findings.extend(f"{name} (file name)" for name in names if pattern.search(name))
    return findings


def message_findings(callsign: str, message: str) -> list[str]:
    """Lines of a commit message that contain the callsign, skipping comments."""
    pattern = callsign_pattern(callsign)
    return [
        f"commit message line {number}"
        for number, line in enumerate(message.splitlines(), start=1)
        if not line.startswith("#") and pattern.search(line)
    ]


def load_callsign(settings_path: Path = SETTINGS_PATH) -> str | None:
    """The station callsign, or None (with a warning) if there isn't one."""
    try:
        callsign = load_settings(settings_path).station_callsign
    except tomllib.TOMLDecodeError:
        print(f"callsign guard: can't read {settings_path}; not checking.", file=sys.stderr)
        return None
    if not callsign:
        print(f"callsign guard: no station callsign in {settings_path}; not checking.", file=sys.stderr)
        return None
    return callsign


def report(findings: list[str]) -> int:
    if not findings:
        return 0
    print("callsign guard: station callsign found; commit blocked.", file=sys.stderr)
    for finding in findings:
        print(f"  {finding}", file=sys.stderr)
    print("Remove it, or bypass once with git commit --no-verify.", file=sys.stderr)
    return 1


def install(repo: Path = Path(".")) -> int:
    hooks_dir = repo / subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for hook, command in HOOKS.items():
        path = hooks_dir / hook
        if path.exists() and HOOK_MARKER not in path.read_text():
            print(f"callsign guard: {path} already exists; not replacing it.", file=sys.stderr)
            return 1
        path.write_text(
            f"#!/bin/sh\n{HOOK_MARKER}\n"
            f"exec uv run --quiet python -m pota_logger_t3.callsign_guard {command}\n"
        )
        path.chmod(0o755)
        print(f"Installed {path}")
    return 0


def main(argv: list[str]) -> int:
    match argv:
        case ["install"]:
            return install()
        case ["pre-commit"]:
            callsign = load_callsign()
            return report(staged_findings(callsign)) if callsign else 0
        case ["commit-msg", message_path]:
            callsign = load_callsign()
            message = Path(message_path).read_text()
            return report(message_findings(callsign, message)) if callsign else 0
        case _:
            print("usage: callsign_guard install | pre-commit | commit-msg FILE", file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
