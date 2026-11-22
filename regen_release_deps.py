"""Pin [project.dependencies] to the full runtime closure from uv.lock.

End users install with `uv tool install`/`upgrade` from git, which ignores
uv.lock and re-resolves dependencies from the version specifiers in
[project.dependencies]. So only exact `==` pins there give a reproducible
install; a bare `textual>=...` lets every transitive dependency float, and
`uv tool upgrade` pulls whatever is newest (see REQUIREMENTS.md, Versioning).

This regenerates those pins from the current lock, so the frozen set always
comes from a resolution the tests ran against:

    uv run regen_release_deps.py          # rewrite [project.dependencies]
    uv run regen_release_deps.py --check  # exit 1 if they're out of date

After a lock change (e.g. `uv lock --upgrade`) and a passing test run,
regenerate and commit, then release. tag_new_version.py refuses a release
whose pins don't match the lock (it calls `pins_match` here), so the freeze
can't be forgotten.
"""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# [project.dependencies]'s array, the only `dependencies = [` key in the
# file (dependency-groups uses `dev`, build-system `requires`).
DEPENDENCIES = re.compile(r"^dependencies = \[.*?^\]", re.MULTILINE | re.DOTALL)


def exported_pins(cwd: Path) -> list[str]:
    """The full runtime closure as sorted `name==version` pins, from uv.lock.

    `--no-emit-project` leaves the app itself out; `--no-dev` leaves the dev
    group out; `--frozen` uses the lock as it stands without re-resolving.
    """
    output = subprocess.run(
        ["uv", "export", "--frozen", "--no-dev", "--no-emit-project", "--no-hashes"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    pins = [line.strip() for line in output.splitlines()]
    return sorted(pin for pin in pins if pin and not pin.startswith("#"))


def project_dependencies(cwd: Path) -> list[str]:
    """[project.dependencies] from pyproject.toml, sorted."""
    with open(cwd / "pyproject.toml", "rb") as file:
        return sorted(tomllib.load(file)["project"]["dependencies"])


def normalized(pins: list[str]) -> list[str]:
    """Pins compared case- and space-insensitively, so hand edits still match."""
    return sorted("".join(pin.split()).lower() for pin in pins)


def pins_match(cwd: Path = ROOT) -> bool:
    """Whether [project.dependencies] already equals the lock's closure."""
    return normalized(project_dependencies(cwd)) == normalized(exported_pins(cwd))


def dependencies_block(pins: list[str]) -> str:
    lines = "\n".join(f'    "{pin}",' for pin in pins)
    return f"dependencies = [\n{lines}\n]"


def write_dependencies(cwd: Path) -> bool:
    """Rewrite [project.dependencies] from the lock; True if it changed."""
    path = cwd / "pyproject.toml"
    text = path.read_text()
    block = dependencies_block(exported_pins(cwd))
    new, count = DEPENDENCIES.subn(lambda _: block, text, count=1)
    if count == 0:
        raise SystemExit("Couldn't find [project.dependencies] in pyproject.toml.")
    if new == text:
        return False
    path.write_text(new)
    # The project's own `requires-dist` in uv.lock now lags the new pins;
    # reconcile it (the resolved versions don't change, they're already pinned).
    subprocess.run(["uv", "lock", "--quiet"], cwd=cwd, check=True)
    return True


def main(argv: list[str]) -> int:
    if argv and argv != ["--check"]:
        print(__doc__)
        return 2
    if argv == ["--check"]:
        if pins_match(ROOT):
            print("[project.dependencies] matches uv.lock.")
            return 0
        print("[project.dependencies] is out of date; run `uv run regen_release_deps.py`.")
        return 1
    if write_dependencies(ROOT):
        print("Rewrote [project.dependencies] from uv.lock, and reconciled the lock.")
    else:
        print("[project.dependencies] already matches uv.lock; nothing changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
