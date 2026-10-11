"""Git hooks that keep main on the newest release.

main only ever points at a release tag, so that installing from git
without naming a branch or tag (`uv tool install git+<repo-url>`) gets a
release. Work goes on dev, and tag_new_version.py moves main to each
release it tags. These hooks catch a slip:

- pre-commit refuses a commit on main.
- pre-push refuses a push that would set the remote's main to a commit
  no release tag points at, or delete it.

They share the hook files with the callsign guard
(src/pota_logger/git_hooks.py). Install once per clone:

    uv run branch_guard.py install
"""

import subprocess
import sys
from pathlib import Path

from pota_logger.git_hooks import add_hook_line, hooks_dir
from tag_new_version import MAIN, VERSION

ROOT = Path(__file__).resolve().parent
HOOK_MARKER = "pota_logger branch guard"
HOOKS = ["pre-commit", "pre-push"]
MAIN_REF = f"refs/heads/{MAIN}"


def run(*args: str, cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def commit_problems(cwd: Path) -> list[str]:
    branch = run("git", "branch", "--show-current", cwd=cwd)
    if branch == MAIN:
        return [f"On {MAIN}, which only moves to a release: commit on dev instead."]
    return []


def is_release(commit: str, cwd: Path) -> bool:
    """Whether a release tag points at `commit`."""
    tags = run("git", "tag", "--points-at", commit, cwd=cwd).splitlines()
    return any(VERSION.fullmatch(tag) for tag in tags)


def push_problems(updates: str, cwd: Path) -> list[str]:
    """Problems with the refs a push sends: `updates` is what git gives
    pre-push, a line per ref, `<local ref> <local commit> <remote ref>
    <remote commit>`.
    """
    problems = []
    for line in updates.splitlines():
        local_ref, commit, remote_ref, _ = line.split()
        if remote_ref != MAIN_REF:
            continue
        if not commit.strip("0"):
            problems.append(f"That would delete {MAIN} on the remote.")
        elif not is_release(commit, cwd):
            problems.append(
                f"{local_ref} ({commit[:8]}) to {MAIN}: no release tag points at it."
            )
    return problems


def report(problems: list[str], bypass: str) -> int:
    if not problems:
        return 0
    print("branch guard: blocked.", file=sys.stderr)
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    print(f"Releases move {MAIN} (uv run tag_new_version.py).", file=sys.stderr)
    print(f"Bypass once with {bypass}.", file=sys.stderr)
    return 1


def install(repo: Path = ROOT) -> int:
    folder = hooks_dir(repo)
    for hook in HOOKS:
        path = folder / hook
        # Skipped in a checkout from before the guard (a branch from an
        # older release), where the script isn't there to run.
        line = f"test ! -f branch_guard.py || uv run --quiet branch_guard.py {hook}"
        if not add_hook_line(path, line, HOOK_MARKER):
            print(f"branch guard: {path} is another tool's; not changing it.", file=sys.stderr)
            return 1
        print(f"Installed in {path}")
    return 0


def main(argv: list[str]) -> int:
    match argv:
        case ["install"]:
            return install()
        case ["pre-commit"]:
            return report(commit_problems(Path(".")), "git commit --no-verify")
        case ["pre-push"]:
            return report(push_problems(sys.stdin.read(), Path(".")), "git push --no-verify")
        case _:
            print("usage: branch_guard.py install | pre-commit | pre-push", file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
