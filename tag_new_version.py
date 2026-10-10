"""Make a release: set the version, commit it, and tag that commit.

Run it for every version bump, whoever makes it, agent or person:

    uv run tag_new_version.py            # today's date, e.g. 2026.10.10
    uv run tag_new_version.py 2026.10.10.1

Versions are calendar dates, YYYY.M.D without leading zeros (Python's
version rules drop them, and the tag must read the same as
pyproject.toml). A second release the same day adds `.1`, a third `.2`:
if 2026.10.10 is already tagged, the default is 2026.10.10.1.

The order matters. What the app reports as its version (the ADIF
export's PROGRAMVERSION, the user agent) comes from pyproject.toml, never
from the tag, so the tag must point at the commit that sets the version.
Done apart, an export could carry a version no tag leads to. See
REQUIREMENTS.md, Versioning. The same commit turns CHANGELOG.md's
`## Unreleased` heading into the version's, so the release notes name
the version they shipped in.

It refuses a tree with changes, a branch other than main, or a
CHANGELOG.md with nothing under `## Unreleased`, asks
before changing anything, then runs the tests. It never pushes; it
prints the push command. RELEASING.md has the steps, how to undo a
release before it's pushed, and how to do it by hand.
"""

import re
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BRANCH = "main"
CHANGELOG = "CHANGELOG.md"
UNRELEASED = "## Unreleased"
VERSION = re.compile(r"(\d{4})\.([1-9]\d?)\.([1-9]\d?)(?:\.([1-9]\d*))?")


def run(*args: str, cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def parse_version(text: str) -> tuple[int, ...]:
    """A version's numbers, or ValueError if it isn't YYYY.M.D[.N] with a real date."""
    match = VERSION.fullmatch(text)
    if not match:
        raise ValueError(f"{text!r} should be YYYY.M.D or YYYY.M.D.N, no leading zeros, like 2026.1.5")
    numbers = tuple(int(n) for n in match.groups() if n is not None)
    try:
        date(*numbers[:3])
    except ValueError:
        raise ValueError(f"{text!r} isn't a real date") from None
    return numbers


def version_tags(cwd: Path) -> list[str]:
    """Tags that are calendar versions (not `MVP`)."""
    tags = run("git", "tag", "--list", cwd=cwd).splitlines()
    return [tag for tag in tags if VERSION.fullmatch(tag)]


def next_version(today: date, tags: list[str]) -> str:
    """Today's version, with `.1`, `.2`... when today's is already tagged."""
    version = f"{today.year}.{today.month}.{today.day}"
    n = 0
    while (version if n == 0 else f"{version}.{n}") in tags:
        n += 1
    return version if n == 0 else f"{version}.{n}"


def check_version(text: str, tags: list[str]) -> None:
    """Raise ValueError unless `text` is a version not tagged yet and newer than every tag."""
    numbers = parse_version(text)
    if text in tags:
        raise ValueError(f"{text} is already tagged")
    newest = max(tags, key=parse_version, default=None)
    if newest and numbers < parse_version(newest):
        raise ValueError(f"{text} is older than the newest tag, {newest}")


def unreleased_changes(text: str) -> list[str]:
    """The non-blank lines under the changelog's `## Unreleased`."""
    lines = text.splitlines()
    if UNRELEASED not in lines:
        return []
    changes = []
    for line in lines[lines.index(UNRELEASED) + 1 :]:
        if line.startswith("## "):
            break
        if line.strip():
            changes.append(line)
    return changes


def released_changelog(text: str, version: str) -> str:
    """The changelog with `## Unreleased` as the version's heading."""
    return text.replace(f"\n{UNRELEASED}\n", f"\n## {version}\n", 1)


def repo_problems(cwd: Path) -> list[str]:
    problems = []
    branch = run("git", "branch", "--show-current", cwd=cwd)
    if branch != BRANCH:
        problems.append(f"On branch {branch or '(none)'}, not {BRANCH}.")
    if run("git", "status", "--porcelain", cwd=cwd):
        problems.append("The tree has changes; commit or stash them first.")
    changelog = cwd / CHANGELOG
    if not (changelog.is_file() and unreleased_changes(changelog.read_text())):
        problems.append(f"Nothing under {UNRELEASED} in {CHANGELOG}; note the release's changes there first.")
    return problems


def release(version: str, cwd: Path) -> None:
    """Set the version and the changelog's heading, commit them, and tag that commit."""
    run("uv", "version", version, cwd=cwd)
    with open(cwd / "pyproject.toml", "rb") as file:
        written = tomllib.load(file)["project"]["version"]
    if written != version:
        raise SystemExit(f"pyproject.toml reads {written}, not {version}; nothing committed.")
    changelog = cwd / CHANGELOG
    changelog.write_text(released_changelog(changelog.read_text(), version))
    run("git", "add", "pyproject.toml", "uv.lock", CHANGELOG, cwd=cwd)
    run("git", "commit", "-m", f"Version {version}", cwd=cwd)
    run("git", "tag", version, cwd=cwd)


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        print(__doc__)
        return 2
    problems = repo_problems(ROOT)
    if problems:
        print("\n".join(problems))
        return 1
    tags = version_tags(ROOT)
    if argv:
        version = argv[0]
        try:
            check_version(version, tags)
        except ValueError as error:
            print(error)
            return 1
    else:
        version = next_version(date.today(), tags)
    # Asked before the tests, which take a while, so a run by mistake or a
    # mistyped version stops at once.
    try:
        answer = input(f"Tag {version}? [y/N] ")
    except EOFError:
        answer = ""
    if answer.strip().lower() != "y":
        print("Nothing changed.")
        return 1
    print("Running the tests first...")
    if subprocess.run(["uv", "run", "pytest", "-q"], cwd=ROOT).returncode != 0:
        print("Tests failed; nothing changed.")
        return 1
    release(version, ROOT)
    print(f"Committed and tagged {version}. To push: git push origin {BRANCH} {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
