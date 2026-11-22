---
name: release
description: >
  Cut a POTA Logger release on `dev`: freeze deps if the lock changed,
  move `## Unreleased` in CHANGELOG.md to the new version, run
  tag_new_version.py (version bump + commit + tag together, move `main`,
  then commit the `+dev` version), and stop before pushing. Use when the
  user asks to make, cut, or tag a release, or to bump/publish the
  version. NOT for ordinary commits on `dev`, and NOT for dev-doc-only,
  test-only, or release-tooling changes, which ride `dev` with no
  version bump.
---

# Release

This is the triggerable checklist. The full step mechanics and the
design rationale both live in [RELEASING.md](../../../RELEASING.md). This
skill does not restate them — it makes the procedure fire at the right
moment and holds the guard rails in one place. When a step here and
RELEASING.md ever disagree, RELEASING.md is canonical: fix it, and fix
this.

## Before you touch anything — preconditions

- **Does this change earn a release?** Only a change a user would notice
  does. Dev-doc-only (REQUIREMENTS.md, DEVELOPMENT.md, CLAUDE.md),
  test-only, and release-tooling changes ride `dev` to both remotes with
  **no version bump** — if that is all that changed, stop and say so
  instead of releasing.
- **On `dev`, clean tree.** The release script refuses otherwise; check
  first so you fail fast with a clear message rather than mid-run. It
  also refuses a `main` that `dev` doesn't lead on from (something was
  committed on `main`).
- **Get the user's explicit go-ahead before anything commits or tags**,
  exactly as for any commit on this project. Releasing commits and tags.

## Steps (checklist — mechanics in RELEASING.md)

1. **If `uv.lock` changed since the last release** (e.g. you ran
   `uv lock --upgrade`), freeze deps once the tests pass on the new
   lock: `uv run regen_release_deps.py`, committed as its own reviewed
   commit. `tag_new_version.py` refuses a release when the pins and the
   lock disagree.
2. **Changelog + commit.** Ensure CHANGELOG.md has real entries under
   `## Unreleased`, then commit everything for the release on `dev`.
3. **Run the release script** (the only way to bump the version):

   ```bash
   uv run tag_new_version.py
   ```

   or pass an explicit version: `uv run tag_new_version.py 2026.10.10.1`.
4. **Verify the version it prints**, then answer `y` to
   `Tag <version>? [y/N]`. Anything but `y` stops before the tests with
   nothing changed. The script then runs the tests, bumps
   `pyproject.toml` + `uv.lock`, renames the changelog heading, commits
   `Version <version>`, tags it, moves `main` to it, and commits
   `Version <version>+dev` on `dev`.
5. **Report the push command the script prints and STOP:**

   ```bash
   git push origin dev main <version>
   ```

   Do not push unless the user asks. The user pushes by hand or asks for
   a push, after reviewing.

## Guard rails (hold these even if the steps seem to be going fine)

- Never edit the version in `pyproject.toml` by hand; never tag by hand.
  `uv version` (via the script) is the only bump.
- Never commit on `main` (branch_guard.py's hooks refuse it); never push
  unasked.
- **Privacy:** before committing, scan the staged diff **and** the commit
  message **and** the changelog for any real callsign — no hook checks
  these. The maintainer's real call appears only to credit who made the
  app; everywhere else use made-up-looking calls (`W1TST`, `W1ABC`).

## Why bump + commit + tag are one atomic script

A version a build embeds in its output must trace to exactly one commit.
A tag without the bump leaves exports carrying the old version; a bump
without the tag names a release no commit answers to. Done together, in
the script's order, an embedded version points at exactly one tagged
commit. Full reasoning: [RELEASING.md → Design rationale](../../../RELEASING.md).
Why the frozen-dep pins go with it:
[RELEASING.md → Frozen dependencies](../../../RELEASING.md).

## When something is wrong

- **Wrong version tagged, nothing pushed yet** → the rollback steps are
  in [RELEASING.md → Undo, before pushing](../../../RELEASING.md). Once a
  tag is pushed, leave it; make a new release instead.
- **The script can't run** → do the same steps by hand, in order, per
  [RELEASING.md → If the script can't run](../../../RELEASING.md).
