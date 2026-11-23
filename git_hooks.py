"""Git hook files for the project's guards (branch_guard.py, beside the
project).

Git runs one file per hook (`.git/hooks/pre-commit`), so guards share
it: each guard's install adds or replaces only its own line, marked with
the guard's name, and leaves the others' alone. A line stops the hook
when its guard refuses, so every guard has its say before git goes on.
"""

import subprocess
from pathlib import Path

HEADER = "#!/bin/sh\n# pota_logger git hooks: each guard's install changes only its own line.\n"


def hooks_dir(repo: Path) -> Path:
    path = repo / subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    path.mkdir(parents=True, exist_ok=True)
    return path


def hook_line(command: str, marker: str) -> str:
    return f"{command} || exit $?  # {marker}"


def add_hook_line(path: Path, command: str, marker: str) -> bool:
    """Put a guard's line in the hook file at `path`, replacing its old
    one. False, with the file untouched, when the file is another tool's.
    """
    text = path.read_text() if path.exists() else HEADER
    if not text.startswith(HEADER):
        return False
    lines = text.splitlines()
    mine = [i for i, line in enumerate(lines) if line.endswith(f"  # {marker}")]
    if mine:
        lines[mine[0]] = hook_line(command, marker)
    else:
        lines.append(hook_line(command, marker))
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o755)
    return True
