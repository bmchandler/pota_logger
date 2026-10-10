# Releasing

Versions are calendar dates, `YYYY.M.D` with no leading zeros
(`2026.10.10`, `2026.1.5`). A second release the same day adds `.1`, a
third `.2` (`2026.10.10.1`).

## Make a release

1. Commit everything for the release, on `main`.
2. Run:

   ```bash
   uv run tag_new_version.py
   ```

   or give the version (`uv run tag_new_version.py 2026.10.10.1`).
3. Check the version it shows, and answer `y` to `Tag <version>? [y/N]`.
4. When it says `Committed and tagged <version>`, push with the command
   it prints:

   ```bash
   git push origin main <version>
   ```

That's all. Don't edit the version in `pyproject.toml` by hand, and
don't tag by hand.

## What the script does

- Refuses a tree with changes, or a branch other than `main`.
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
- Commits those two files as `Version <version>`.
- Tags that commit `<version>` (a plain tag, no `v`).
- Never pushes.

## Why these go together

The version the app reports (the ADIF export's `PROGRAMVERSION`, the
user agent on downloads) comes from `pyproject.toml`, not from the tag.
A tag without the version change leaves exports carrying the old
version; a version change without a tag names a release no commit can
be found by. Done together, in this order, a version in an exported
file points at exactly one tagged commit. See REQUIREMENTS.md,
Versioning, for the full reasoning.

## Undo, before pushing

If the wrong version was tagged and nothing is pushed yet:

```bash
git tag -d <version>
```

```bash
git reset --hard HEAD~1
```

Check `git log -1` shows `Version <version>` before the reset. Once a
tag is pushed, leave it; make a new release instead.

## If the script can't run

Do the same steps by hand, in this order, on a clean `main` with the
tests passing:

```bash
uv version <version>
```

```bash
git add pyproject.toml uv.lock
```

```bash
git commit -m "Version <version>"
```

```bash
git tag <version>
```
