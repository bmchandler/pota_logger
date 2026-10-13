# Development

For anyone who wants to run POTA Logger from source, change it, or adapt
it for their own use.

## Contributions

This is a personal project, shared as is, for anyone to use or adapt
and as a portfolio example. Pull requests aren't reviewed or merged.
If issues are open, they're read, and fixed at the maintainer's own
pace and choice. You're welcome to fork it and make it your own.

## Setup

You need [uv](https://docs.astral.sh/uv/); it fetches Python 3.13 and
the dependencies itself.

A clone starts on `main`, the newest release. Work goes on `dev`:

```bash
git switch dev
```

```bash
uv run pota-logger
```

Run it from the project folder. At first start it asks for your
station callsign.

## Branches

- `main` only ever points at the newest release's tag, so an install
  from git without a branch or tag gets it. It's never committed to:
  `tag_new_version.py` moves it forward at each release (see
  RELEASING.md).
- `dev` is where work goes, and releases are made. Its version is the
  last release's plus `+dev` (`2026.10.11+dev`), set by the release
  script; a build installed from git adds its commit
  (`2026.10.11+dev.5f820a58`), read when the app runs (`app_version.py`).
- Tags are for releases only. Testers install a development build by
  branch or commit instead (see Development builds).

Run from a clone, the app keeps its files in the clone's `data/`, for
development: git-ignored, so logs stay out of the code history.
Installed (`uv tool install`, see README.md), it uses
`~/.local/share/pota-logger/data/` (or `$XDG_DATA_HOME/pota-logger/data/`)
instead, outside the install, which an upgrade replaces, and writes a
`README.txt` beside it. `data_folder.py` tells the two apart by a
`pyproject.toml` two folders above the package, which only a clone has.
A development build installed (its version has `+dev`) uses
`~/.local/share/pota-logger-dev/` instead of `pota-logger/`, so testing
it never touches a release's log; a clone keeps its `data/` either way.

ADIF exports go to `exports/` beside `data/` unless Settings names
another folder: the clone's `exports/` (git-ignored), or installed,
`~/.local/share/pota-logger/exports/`. `tmp/` (git-ignored) is for
other scratch files while developing.

If you'll commit, install the branch guard's git hooks once per clone.
They refuse a commit on `main` and a push that would set the remote's
`main` to anything but a release:

```bash
uv run branch_guard.py install
```

The callsign guard's hooks are retired (see Privacy). In a clone that
installed them, delete the `pota_logger callsign guard` lines from
`.git/hooks/pre-commit` and `.git/hooks/commit-msg`, or each commit
fails, as the module they run is gone. If its hook files predate the
shared ones (no `pota_logger git hooks` line at the top), delete those
two files whole, then install the branch guard's.

## Development builds

To test what's being worked on (which may not be ready for use),
install the newest development build:

```bash
uv tool install "git+https://github.com/bmchandler/pota_logger@dev"
```

and update it with `uv tool upgrade pota-logger`. Or install one
commit, which `uv tool upgrade` doesn't move:

```bash
uv tool install "git+https://github.com/bmchandler/pota_logger@<commit>"
```

From a git server of your own over SSH, use its URL instead, here for a
server named `gitserver` with the repository in its `git` user's home:

```bash
uv tool install "git+ssh://git@gitserver/~/pota_logger.git@dev"
```

```bash
uv tool install "git+ssh://git@gitserver/~/pota_logger.git@<commit>"
```

Leave off `@dev` for the newest release. In an `ssh://` URL the path
starts at the server's root, so `/~/` stands for the user's home (or
give the full path, like `/home/git/pota_logger.git`). Git's short form,
`git@gitserver:pota_logger.git`, isn't a URL, so uv doesn't take it.

A development build keeps its files in `~/.local/share/pota-logger-dev/`,
apart from a release's, so testing it never touches your real log
(uninstalling leaves it, too). It reports its version as the release
it follows, plus `+dev` and its commit (`2026.10.11+dev.5f820a58`), in
ADIF exports too.

Commits from `4ccbe051` on use `pota-logger-dev`. Earlier ones were made
before development builds had a folder of their own: installed by
commit, they report a release's version and use the release's
`~/.local/share/pota-logger/`, your real log's. With a clone, to tell
which side a commit is on (it prints `after` or `before`):

```bash
git merge-base --is-ancestor 4ccbe051 <commit> && echo after || echo before
```

Only one `pota-logger` can be installed at a time: to switch between a
release and a development build, run the other's install command. Go
back to the release before logging for real. To try a development build
without replacing your installed release:

```bash
uvx --from "git+https://github.com/bmchandler/pota_logger@dev" pota-logger
```

## Tests

```bash
uv run pytest
```

Tests run in parallel (pytest-xdist, with `--dist worksteal`), about 55
seconds in all. For a few tests, add `-n0`, as starting the workers
takes about 2 seconds:

```bash
uv run pytest -n0 tests/fields/test_freq.py
```

- `tests/` mirrors `src/pota_logger/`: `tests/fields/`, `tests/screens/`,
  and a test file beside them per top-level module (`test_logbook.py`).
  The app's tests (`app.py`) are in `tests/app/`, a file per area
  (`test_entry.py`, `test_editing.py`, `test_export.py`...), sharing
  `tests/app/helpers.py` (`ENTRY`, `fill`, `table_rows`...) and the
  fixtures in `tests/app/conftest.py` (`export_app`, `no_call_app`,
  `parks_app`...). What tests in more than one folder share is in
  `tests/helpers.py` (`fail_to_write`). Each test folder is a package
  (`__init__.py`), so files in different folders can share a name.
- Most of the time is app tests: about 0.6 second per `run_test` (mostly
  Textual's own styling and layout), plus about 0.1 second per
  `pilot.press`. Set field values with `fill()` unless typing key by key
  is what's being tested. Put a field's rules and messages in its
  module's unit tests, which are nearly instant, but keep an app test
  that shows the field is wired into the form.
- Tests never touch the real `data/`: use the `settings_path` and `app`
  fixtures in `tests/conftest.py`, which point at a temp dir. `app` has
  station callsign `W1TST` saved; an app on `settings_path` alone has
  none, so it opens on the station-callsign-required block. Each test
  keeps to its own temp dir, as tests run in parallel.
- Tests never reach pota.app: the `pota` fixture is a local server
  standing in for it. Nor GitHub: the `releases` fixture makes a local
  git repository with the tags given, for the check for a newer
  release.
- App tests build on `ENTRY` (USB on a 20m voice frequency) and
  `CW_ENTRY`. A test that saves several entries needs a different
  CALL on each, or the dupe block stops it. Use past dates, or `991231`
  for a future one.
- REQUIREMENTS.md's "Status and plan" has the test-speed history and
  why the slow tests are kept as they are.

## Where things are

- [REQUIREMENTS.md](REQUIREMENTS.md) is the source of truth for scope,
  field rules, and what's built and planned. A change to a rule updates
  it in the same commit.
- [RELEASING.md](RELEASING.md): how to make a release.
- [CLAUDE.md](CLAUDE.md): instructions for the AI coding agent used on
  this project (Claude Code), with detailed notes on how the code fits
  together. Worth a read for the same reason.
- `src/pota_logger/`:
  - `app.py`: the app (`PotaLoggerApp`, and `main`, which the
    `pota-logger` command runs) and the log table.
  - `entry_form.py`: the entry form, its fields, and the checks run on
    Enter.
  - `fields/`: one module per entry field with rules: `freq.py`,
    `modes.py`, `callsigns.py`, `parks.py`, `states.py`, `reports.py`,
    `power.py`, `dates.py`. Each has `parse_*`, which raises
    `ValueError` with the message shown to the operator, and `format_*`
    where the value shows differently from how it's stored. Also
    `sidebands.py`, the rules that tie MODE and FREQ together, and
    `ascii_text.py`, the ASCII check on every text input.
  - `entry_warnings.py`: warnings (probably wrong, but saveable).
    `dupes.py`: the definite dupe check.
  - `logbook.py`: the CSV storage, loading and checking the files.
    `record_ids.py`: each row's record ID. `file_errors.py`: the
    errors file for rows too broken to load.
  - `adif.py`: ADIF records and the export file.
  - `parks_list.py`: POTA's parks list download, one of the app's two
    network uses.
  - `updates.py`: the other, the check for a newer release at start
    (`git ls-remote`), and the upgrade on Quit (`uv tool upgrade`).
  - `settings.py`: the settings file. `data_folder.py`: where the app
    keeps its files, and the installed `README.txt` (`README_TEXT`), a
    summary of README.md's "Your data": change them together.
  - `app_version.py`: the version the app reports (ADIF export, user
    agent), with a development build's commit.
  - `screens/`: the modals (`*_screen.py`) and the status bar
    (`status_bar.py`).
  - `theme.py`: the color theme.
  - `git_hooks.py`: the git hook files the branch guard writes its
    lines into.
- `tag_new_version.py`: makes a release (see RELEASING.md).
- `branch_guard.py`: the branch guard's git hooks (see Branches).

## Conventions

### Entry checks: block vs warn

- Block (refuse with a notification, focus the field) only what can't be
  right: a report digit out of range, a frequency outside the bands, or
  anything the ADIF standard doesn't allow (input must always fit ADIF,
  whatever QRZ or other logbooks accept; what ADIF allows is accepted
  unless the operator decides otherwise). Non-ASCII is refused up front
  by `check_ascii` (`ascii_text.py`), since Python's `isdigit()` and
  `\d` also match digits like ５ and ²; use it for any new text input
  too. A definite dupe (`dupes.py`: the same in every column but COMMENT
  and the record ID) is also blocked, with its own modal (`Roger
  Roger`).
- Warn (modal, Enter saves anyway) what's probably wrong but could be
  real, like a special-event call or a voice signal outside the voice
  range. The operator copies a paper log, so a real but odd contact must
  never be unsaveable.
- Messages use the operator's ham shorthand ("dupe", not "duplicate").
  Warning messages end with "Esc to correct, or confirm with Enter." and
  use explicit line breaks so they wrap cleanly.

### Textual

- Prefer stock Textual behavior and looks, and avoid overriding its key
  bindings; overriding them is a deliberate decision.
- Colors come from the `pota` theme in `theme.py`; widget CSS uses theme
  variables (`$primary`, `$warning`, `$surface`...), not hex colors.
- Never pass a DataTable a plain `str` cell: it's read as Rich markup,
  which hid brackets in a COMMENT and crashed on `[/]`. Log cells are
  Rich `Text`.

### Third parties

In docs and comments, state what a third party (POTA, QRZ.com, other
logbooks) does as fact only from its own documentation (the ADIF spec
for ADIF). Otherwise word it as uncertain ("appears to", "it's likely"),
with the evidence where known.

## Seeing what the TUI draws

- Text: run the app with `run_test(size=(107, 24))` in a scratch script
  (107 is the form's full width; narrower adds its scrollbar), and print
  `"".join(seg.text for seg in strip)` for each strip in
  `app.screen._compositor.render_strips()`.
- An image: `app.export_screenshot()` gives an SVG. Before converting it
  (e.g. cairosvg), replace the "Fira Code" font with "DejaVu Sans Mono":
  without Fira Code, the block characters in borders (▊ ▎ ▔ ▁) draw as
  full-cell boxes and hide sub-cell edges.
- cairosvg skips `text-decoration`, so it doesn't draw underlines; a
  headless Firefox screenshot of the SVG does (`firefox --headless
  --screenshot=out.png --window-size=1330,650 file:///path/to.svg`).
  Textual's SVG export doesn't draw overlines at all (the log divider),
  so no screenshot shows it.
- To confirm what escape codes reach a real terminal (e.g. SGR 53 for
  overline), run a scratch app under `pty.fork()` with the window size
  set by `TIOCSWINSZ`, capture its output, and search the `\x1b[...m`
  codes.

## Privacy

There's no official standard reserving callsigns for examples, the way
some domain names are, so any call that passes the app's callsign
checks may belong to someone. So:

- The maintainer's own call appears only to credit who made the app
  (README.md, and the app's own about information).
- Everywhere else (tests, examples, the app's messages and
  placeholders, commit messages), use calls chosen to look made up,
  like `W1TST` or `W1ABC`. Never one copied from a real log.
- Those calls go only in code that can't reach the network: tests with
  the network mocked, or with a test server the test starts on loopback
  (`127.0.0.1`) that serves canned data and reaches nothing outside
  (the `pota` fixture in tests/conftest.py, which stands in for
  pota.app's parks list). Never in code that may make a real network
  call.
- Anything else that sends a callsign (a logbook upload, say) is tested
  by hand by a person, with their own call (`/TEST` added, for
  example), and kept out of the test suite.

`data/` is git-ignored, so logs stay out of the repo. Nothing checks
commits for callsigns: check staged changes and commit messages
yourself. (The callsign guard's git hooks once blocked the call in
`data/settings.toml`; they were retired once the maintainer's call
became public as credit.)
