# Releasing

Versions are calendar dates, `YYYY.M.D` with no leading zeros
(`2026.10.10`, `2026.1.5`). A second release the same day adds `.1`, a
third `.2` (`2026.10.10.1`).

`main` always points at the newest release: it's what an install from
git without a branch or tag gets. Work goes on `dev`, and releases are
made there; the release script moves `main` forward. Never commit on
`main` (`branch_guard.py`'s hooks refuse it; see DEVELOPMENT.md).

## Make a release

1. If the dependencies changed since the last release (e.g. you ran
   `uv lock --upgrade`), freeze them for end users once the tests pass
   on the new lock: `uv run regen_release_deps.py`. It pins the full
   runtime closure into `[project.dependencies]` from `uv.lock` (see
   [Frozen dependencies](#frozen-dependencies)).
2. Note the release's changes in [CHANGELOG.md](CHANGELOG.md), under
   `## Unreleased`, and commit everything for the release, on `dev`.
3. Run:

   ```bash
   uv run tag_new_version.py
   ```

   or give the version (`uv run tag_new_version.py 2026.10.10.1`).
4. Check the version it shows, and answer `y` to `Tag <version>? [y/N]`.
5. When it says `Committed and tagged <version>, and moved main to it.`,
   push with the command it prints:

   ```bash
   git push origin dev main <version>
   ```

That's all. Don't edit the version in `pyproject.toml` by hand, and
don't tag by hand.

## What the script does

- Refuses a tree with changes, a branch other than `dev`, a `main` that
  `dev` doesn't lead on from (something committed on `main`), nothing
  under `## Unreleased` in CHANGELOG.md, or `[project.dependencies]`
  out of sync with `uv.lock` (see
  [Frozen dependencies](#frozen-dependencies)).
- Takes today's date (local), with `.1`, `.2` if that's tagged already;
  a version you give is refused if it's malformed, already tagged, or
  older than the newest tag.
- Asks `Tag <version>? [y/N]`. Anything but `y` stops here, before the
  tests, with nothing changed.
- Runs the tests (`uv run pytest`). If they fail, it stops with
  `Tests failed; nothing changed.`
- Runs `uv version <version>`, which sets the version in
  `pyproject.toml` and `uv.lock`, and checks `pyproject.toml` reads
  exactly that.
- Renames CHANGELOG.md's `## Unreleased` heading to `## <version>`.
- Commits `pyproject.toml`, `uv.lock`, and `CHANGELOG.md` as
  `Version <version>`.
- Tags that commit `<version>` (a plain tag, no `v`).
- Moves `main` forward to that commit.
- Runs `uv version <version>+dev` and commits `pyproject.toml` and
  `uv.lock` as `Version <version>+dev`, so dev builds report
  `<version>+dev` (and their commit), not the release's version.
- Never pushes.

## Why these go together

The version the app reports (the ADIF export's `PROGRAMVERSION`, the
user agent on downloads) comes from `pyproject.toml`, not from the tag.
A tag without the version change leaves exports carrying the old
version; a version change without a tag names a release no commit can
be found by. Done together, in this order, a version in an exported
file points at exactly one tagged commit. See REQUIREMENTS.md,
Versioning, for the full reasoning.

## Frozen dependencies

End users install with `uv tool install`/`upgrade` from git. That path
**ignores `uv.lock`** and re-resolves dependencies from the version
specifiers in `[project.dependencies]`, so a bare `textual>=...` lets
every transitive dependency float and `uv tool upgrade` pulls whatever
is newest. To give a reproducible install, `[project.dependencies]`
pins the whole runtime closure to exact `==` versions.

Those pins are generated from `uv.lock`, so the frozen set is always
one the tests ran against:

```bash
uv run regen_release_deps.py
```

It rewrites `[project.dependencies]` from the lock and reconciles the
lock, as its own reviewed commit. `--check` reports whether they agree
without changing anything. `tag_new_version.py` runs the same check and
refuses a release when they disagree, so an upgraded lock can't ship
without re-pinning.

The loop: on `dev`, `uv lock --upgrade`, run the tests, then
`uv run regen_release_deps.py`, commit, and release.

## Undo, before pushing

If the wrong version was tagged and nothing is pushed yet, on `dev`:

```bash
git tag -d <version>
```

```bash
git branch -f main <previous version>
```

```bash
git reset --hard HEAD~2
```

`<previous version>` is the release before it (the newest tag left,
from `git tag --sort=-creatordate`). Check `git log -2 --format=%s`
shows `Version <version>+dev` and `Version <version>` before the reset.
Once a tag is pushed, leave it; make a new release instead.

## If the script can't run

Do the same steps by hand, in this order, on a clean `dev` with the
tests passing, after renaming CHANGELOG.md's `## Unreleased` heading
to `## <version>`:

```bash
uv version <version>
```

```bash
git add pyproject.toml uv.lock CHANGELOG.md
```

```bash
git commit -m "Version <version>"
```

```bash
git tag <version>
```

```bash
git branch -f main <version>
```

`git branch -f` moves `main` wherever it's told, so check first that
`git merge-base --is-ancestor main <version>` succeeds (prints nothing).
Then:

```bash
uv version <version>+dev
```

```bash
git add pyproject.toml uv.lock
```

```bash
git commit -m "Version <version>+dev"
```
