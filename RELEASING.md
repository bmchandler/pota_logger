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

What the app reports as its version comes from `pyproject.toml` (through
the installed package's metadata), never from the tag. It's the ADIF
export's `PROGRAMVERSION` and the `pota-logger/<version>` user agent on
the parks list download (and on the QRZ.com API, when built). A tag
alone changes nothing the app reports, so exports would carry the last
release's version; a version set without a tag names a release no commit
can be found by. Done together, a version in an exported file points at
exactly one tagged commit.

## Frozen dependencies

End users install with `uv tool install`/`upgrade` from git. That path
**ignores `uv.lock`** and re-resolves dependencies from the version
specifiers in `[project.dependencies]`, so a bare `textual>=...` lets
every transitive dependency float and `uv tool upgrade` pulls whatever
is newest (it did, on 2026-11-21: `markdown-it-py`, `mdit-py-plugins`,
and `platformdirs` all moved). To give a reproducible install,
`[project.dependencies]`
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

## Design rationale

Why releases are built this way. The steps themselves are above
([Make a release](#make-a-release), [What the script does](#what-the-script-does)).

- **Calendar versioning** (decided 2026-10-10): a release is named for
  the date it's made, as `YYYY.M.D` (`2026.10.10`), with `.1`, `.2` and
  so on for a second or third release the same day (`2026.10.10.1`). The
  app isn't a library: no code depends on it, so semantic versioning's
  "is this change breaking?" has no one to answer to, and the date needs
  no judgment call. The log file's format has its own "version", apart
  from the app's: its header row (see
  [REQUIREMENTS.md, Storage](REQUIREMENTS.md#storage)).
- **No leading zeros** (`2026.1.5`, not `2026.01.05`): Python's version
  rules (PEP 440) drop them, so `uv version 2026.01.05` writes
  `2026.1.5`, and the tag must read the same as `pyproject.toml`.
- **Releases only when the operator asks.** The first tag, `MVP`
  (e1ad0e4), stays as it is. The script is the only way to bump the
  version, for every release, whether an agent or a person makes it; an
  agent still pauses for the operator's go-ahead before running it, as
  before any commit.
- **Between releases**, `dev`'s version is the last release's plus
  `+dev` (`2026.10.12+dev`, a PEP 440 local version), and a dev build
  installed from git reports the commit it was built from too:
  `2026.10.12+dev.5f820a58`, the first 8 characters of the commit,
  wherever the app reports its version (app_version.py). The commit
  can't be written in `pyproject.toml` (a commit can't contain its own
  hash), and reading it from git when the package is built needs a
  backend that does that (`hatchling` with `hatch-vcs`), set aside to
  stay with uv's own. So it's read when the app runs, from the
  `direct_url.json` an installer writes for an install from git (PEP
  610, which requires the commit; uv 0.12.17 checked writing it, for
  `uv tool install` and `uvx`). A clone run (`uv run`) or an install
  from a package index has no commit there, so its version is reported
  as written. PyPI refuses local versions, which never reach it: only
  releases would be published there.
- **Branches** (decided 2026-10-11): `main` only ever points at the
  newest release's tag, so an install from git without a branch or tag
  (`uv tool install git+<repo-url>`) gets the newest release, and
  `uv tool upgrade` the next one. Work goes on `dev`, and releases are
  made there; `main` is never committed to, only moved forward by
  `tag_new_version.py`. Tags are for releases only: a dev build is
  installed by branch (`@dev`, which `uv tool upgrade` follows) or by
  commit (`@<commit>`, which it doesn't). README.md shows `main`'s code,
  so it can lag `dev`; a fix to docs about released behavior that users
  need goes out as a release of its own, noted in the changelog. The
  converse (settled 2026-11-22): a change nothing in a release would
  reflect — developer docs (REQUIREMENTS.md, DEVELOPMENT.md, CLAUDE.md),
  tests, release tooling — is not a release. There's no honest changelog
  line for it (the changelog is user-facing only), so it rides `dev` to
  both remotes and `main` stays put. Only a change a user would notice
  earns a version bump.
- **`branch_guard.py`** (beside `tag_new_version.py`, for developers,
  not in the package) installs git hooks that refuse a commit on `main`,
  and a push that would set the remote's `main` to a commit no release
  tag points at, or delete it. Its install changes only its own line in
  each hook file (git_hooks.py). A checkout from before the guard (a
  branch from an older release) has no script, so its line does nothing
  there.
- **Fast-forward only, no merge commits** (settled 2026-11-22). `main`
  is a bookmark on `dev`'s linear history, moved forward to each
  release's commit (`tag_new_version.py`, `update-ref`), never merged
  into, so `main` stays an ancestor of `dev` and a push of `main` is
  always a fast-forward. This keeps one linear history, keeps
  `branch_guard.py` meaningful (a merge commit would itself be a commit
  on `main`, which it refuses), and keeps the version-to-commit mapping
  exact (`main` points *at* the tagged commit, not a merge above it). A
  merge commit buys nothing here: the release spine is the tags
  (`git tag --sort=-creatordate`, `git diff <old-tag> <new-tag>`), not
  `main`'s own history. Revisit only if the project gains multiple
  contributors integrating through reviewed PRs, or needs to maintain an
  old release apart from `dev` (a hotfix branch from a tag); both are
  deliberate changes, not the default.

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
