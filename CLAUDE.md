# POTA Logger

Textual TUI logbook for hunting POTA parks, managed with uv (Python 3.13).
REQUIREMENTS.md is the source of truth for scope and field rules; keep it
updated in the same change whenever a rule changes.

Setup, commands, tests, code layout, and conventions shared with any
developer are in DEVELOPMENT.md, imported here:

@DEVELOPMENT.md

## How we work

- Build in small "horizontal" steps: only what the current request needs.
  Don't scaffold ahead or add functions before a step uses them.
- Add or update tests alongside each change.
- After code changes are done, stage what makes sense, draft a commit
  message, and pause there. Don't run `git commit` until the user reviews
  the diff/stage/message and app behavior and gives a clear go-ahead to
  commit, in whatever natural phrasing ("Proceed", "Proceed with commit",
  "Looks good, proceed", "Go ahead and commit", etc.).
- Work and commit on `dev`, never on `main`: `main` only ever points at
  the newest release's tag, and only the release script moves it
  (`branch_guard.py`'s hooks refuse a commit on it).
- Releases (only when the user asks; steps in RELEASING.md), on `dev`:
  `uv run tag_new_version.py`, the only way to bump the version. It sets a calendar version (`uv
  version <YYYY.M.D>`), commits `pyproject.toml` and `uv.lock`, and tags
  that commit, always all together (see REQUIREMENTS.md Versioning for
  why), then moves `main` to it and commits `<YYYY.M.D>+dev` on `dev`. It asks before changing anything: get the user's go-ahead first,
  as for any commit.
- Note each change a user would notice in CHANGELOG.md, under
  `## Unreleased` (add the heading if a release removed it), in the same
  commit: terse, for users, not a commit log.
- Don't `git push` after a commit unasked. The user pushes by hand,
  or asks for a push, usually at the end of a session or after a few
  commits.
- Commit messages: short subject line, a body with details when useful,
  then the Co-Authored-By trailer. The first commit in a repo is always
  `Initial Commit`.
- When a request is ambiguous (especially about UI behavior), ask instead
  of guessing.
- "Can we ...?" / "Could we ...?" is a literal question, not a go-ahead
  to edit. Answer it: is it doable out of the box with the framework,
  what are the trade-offs, would it override stock framework behavior
  (e.g. a built-in key binding)? Then wait for a clear instruction.
  Avoid overriding framework defaults unless the user decides to.
- REQUIREMENTS.md's "Status and plan" section says what's built and
  what's next; update it when a planned item lands.
- README.md is for users of the release: what it does, installing,
  upgrading, using it, their data. Developer material (development
  builds, running from a clone, tests, releasing, requirements) goes in
  the developer docs, which README.md never mentions or links: those
  who need them will find them. Its only links to the repo's files are
  CHANGELOG.md and LICENSE.md.
- In docs, a reference to a section or file is a link to it:
  `[Your data](#your-data)`, `[DEVELOPMENT.md](DEVELOPMENT.md)`,
  `[Development builds](DEVELOPMENT.md#development-builds)`. Not needed
  for a file already linked earlier in the same paragraph.
- README.md's "Noted issues" table (Issue, Status, Reason) lists only
  issues the operator decides to note: ones that won't be fixed (so
  users don't expect a fix), or that users must know about to keep
  their log safe. Not every bug goes there.

## Privacy

The rules are in DEVELOPMENT.md's Privacy. Beyond them:

- The operator's `data/settings.toml` holds a placeholder call, used
  nowhere in the repo, instead of the real one. Never name the
  placeholder in tracked files, and don't use it as a test call.
- The operator's real call goes only where it credits them as the
  app's maker. Check staged changes and commit messages by hand for any
  other real call (one from a log in `data/`, above all): no hook
  checks them.

## Code notes

- Each entry field with rules has a small module with `parse_*` (raises
  ValueError with a message shown to the operator) and, if displayed
  differently, `format_*`, in `fields/`: freq.py, modes.py, callsigns.py,
  parks.py, states.py, reports.py, power.py, dates.py. sidebands.py
  (also in `fields/`, with ascii_text.py) holds the
  MODE-and-FREQ sideband rules.
- The app (`PotaLoggerApp`, `main`) is app.py; the modals
  (`*_screen.py`) and status_bar.py are in `screens/`. `__init__.py`
  files hold only a docstring.
- adif.py turns an entry into one ADIF record (`adif_record`, ending
  `<EOR>`; `adif_fields` gives the (name, value) pairs, blanks left
  out): what the file export writes per entry and QRZ.com's API takes
  per QSO. `adif_file` adds the header (`adif_header`), one record per
  line; `export_file_name` names the file. It takes clean entries only:
  export is refused while any row is marked `!`, `U`, or `=` (see
  REQUIREMENTS.md Export).
- app_version.py's `app_version()` is the version the app reports
  (ADIF's `PROGRAMVERSION`, the parks download's user agent; the QRZ.com
  API's when built): pyproject.toml's, plus a dev build's short commit
  from `direct_url.json` (`2026.10.11+dev.5f820a58`). Use it, not
  `importlib.metadata.version`. `is_dev` (a `+dev` version) also picks
  data_folder.py's `pota-logger-dev` folder for an install; a clone
  keeps `data/`. Tests pass `data_dir` a version rather than rely on
  the clone's.
- Git hooks: branch_guard.py (beside tag_new_version.py, which it
  imports `MAIN` and `VERSION` from) adds its own marked line to the
  hook files (git_hooks.py's `add_hook_line`), leaving others' alone.
- export_screen.py holds `ExportScreen` (`f6`, or the ADIF button; the
  app's `action_export` gives it the log's entries, refused rows left
  out, whether the log is clean of `CLEAN_LOG_MARKERS`, and
  `export_range`'s default dates). It doesn't show the folder; it reads
  it from `app.settings` on Export, since F2 opens Settings over it (its
  own binding: the app's keys don't reach a modal). The only folder
  made is the default (`default_export_folder`: `exports/` beside
  `data/`), by the app's `with_export_folder`, only when it fills a
  blank setting (at start, or a folder cleared in Settings); `folder_path`
  in settings.py expands `~`, and Settings saves only an existing typed
  folder. Tests use the `export_folder` and `export_app`
  fixtures (an existing folder in the temp dir), or `home` for `~`.
- parks_list.py downloads POTA's parks list (`download_parks`, the
  app's only network use; raises `ParksDownloadError` with a message for
  the operator) into `parks_folder(data_dir)`; `saved_copy` gives a
  sound copy's `ParksCopy` (`ETag`, `Last-Modified`), or None. The app's
  `apply_settings` offers it at first start (`ParksOfferScreen`, once
  `load_log` hasn't blocked); Settings after setup shows the copy's date
  with `Check for Updated`. Both run the app's `check_parks_list`, a
  thread worker (`fetch_parks_list`) whose result comes back by
  `call_from_thread`. `load_parks` reads the copy into `app.parks`
  (reference to `Park`: name, active, DXCC, US states without `US-`),
  likewise in a thread (the app's `load_parks`, at start and after a
  download). parks.py holds `Park`, apart from parks_list.py (once
  needed to avoid an import cycle through adif.py, logbook.py, and
  entry_form.py). PARK refuses ADIF's `@LOCATION`: `adif_fields` adds
  it to `POTA_REF` from ST, for a park in several states. `EntryForm.show_park_name` shows PARK's name on
  COMMENT's label row (`#park-name`, centered via `labeled_input`'s
  `beside`) and `fill_state` fills ST (`filled_state`, put aside like
  `pota_comment`), wherever PARK's value changes. Warning checks take
  `parks` as a third argument (`park_not_listed`,
  `state_not_the_parks`); `adif_fields` takes it for `DXCC` and that location. Tests use the `pota` fixture (tests/conftest.py), a
  local server, setting `app.parks_url` to its `url`, then
  `parks_list_done` to wait (`parks_app` has `APP_LIST` saved): never reach
  pota.app from a test.
- `entry_form.py` holds `FIELDS` (name, placeholder, longest value) in
  entry order: `ROW_FIELDS` for the top row (`ENTRY_ORDER`), then COMMENT,
  laid out below it. `LOG_FIELDS` (`LOG_ROW_FIELDS`, then COMMENT) is
  paper-log order, for the log table's columns and the CSV's: use it,
  not `FIELDS`, wherever column order matters. Also
  `PARSERS`, `REPORTS` (parsed after, since they depend on MODE),
  `OPTIONAL`, `DEFAULTS`, `CARRY_FORWARD`, and `WARNINGS`. `app.py`
  holds `FORMATTERS` and `DISPLAY_LENGTHS` for the log table.
- Warnings (probably wrong, but saveable) are checks in entry_warnings.py
  listed in `WARNINGS`, shown in warning_screen.py. Each check takes the
  entry, the entries logged so far (`EntryForm.logged`), and the parks
  list (`app.parks`, empty without one). The unusual-CALL
  warning has its own modal (callsign_warning_screen.py) so the call can
  be edited there; the settings modal uses it for the station callsign.
- One station callsign per log (multiple calls, OPERATOR, and multiple
  logbooks are out of scope): `Logbook.load(station_callsign)` refuses a
  row with another call (note `FIX_BY_HAND`, which `f3` checks), so the app's
  `load_log` waits until a call is set. Settings shows the call only
  while none is set (`SettingsScreen(with_callsign)`); after that, F2
  opens it with the on/off settings (`SWITCHES` in settings.py, as
  `SettingCheckbox`, which draws its X only when checked) and the ADIF
  export folder (`adif_export_folder`, always shown; each text field's
  problem shows below it, `PROBLEM_IDS`). Tests of the
  call in the modal use the `no_call_app` fixture, opening Settings with
  Enter from the block.
- COMMENT's POTA info: `EntryForm.pota_comment` is the info (`pota_info`)
  the app last wrote at the start of COMMENT, None while its setting is
  off for the entry in the form; `update_pota_comment` runs on leaving
  PARK or ST and on Enter, and `settings_changed` after Settings saves.
- On Enter, `EntryForm.on_input_submitted` runs, stopping at the first
  problem: no station callsign set (the app's `require_station_callsign`
  block, which leads to Settings), `update_pota_comment` (not a check),
  missing fields, `check_ascii` on every field (with `ASCII_EXAMPLES`),
  `PARSERS` (in entry order), `REPORTS`, `check_sideband`,
  `unchanged_edit` (steps back, saving nothing), `blocked_as_dupe`, the unusual-CALL modal (then `blocked_as_dupe` again,
  as the call may change there), then each of `WARNINGS` in order. The
  dupe block's modal closes back to the form as typed, new or edit.
- logbook.py holds the CSV storage, `Logbook` (`app.logbook`): `load`
  at start (entries plus a message per skipped row or file, which with
  `unsaved` go in `file_errors.txt`, file_errors.py, behind the app's
  `block_on_file_errors` modal, Quit only) keeps each
  file's lines in `files`, the only source of truth while the app runs;
  `append` on each save and `replace` for an edit (only that row's lines
  change) rewrite the whole file from that copy. A failed write raises
  `LogWriteError` with the `writes` left, which the app's `save` retries
  from a modal (Esc: nothing saved; the form keeps the entry, as it's
  cleared only by `EntryForm.entry_saved`). `check_row` finds every
  `Problem` in a row (field, message, note on what saving fixes), after
  `load` has fixed how each value is written (`tidied`: spaces, case, a
  number's form; never COMMENT, nor what a value means). Rows
  refused on load that split into COLUMNS are kept in `Logbook.refused`
  (`Refused`: a dict of raw text, file, line, problems), shown at the top
  of `saved_entries` marked `!` (`REFUSED_MARKER`), with their problems
  listed below COMMENT when selected (the app's `entry_view`, then
  `EntryForm.show`), and fixed or deleted like any entry; check
  `Logbook.is_refused` before formatting an entry's values. Every row
  ends with its record ID (`UUIDv4`, record_ids.py), set in
  `EntryForm.submit` and kept by an edit; `load` fills in a blank one
  (written on load with the `tidied` fixes; a failed write goes in
  `unsaved`), and
  `appended` skips a row already in the file, ID included. Entries
  sharing an ID are marked `SHARED_MARKER` (`U`) and explained below
  COMMENT; saved definite dupes likewise get `DUPE_MARKER` (`=`), listed
  after any shared IDs in the app's `repeat_lines` (marks: `!`, `U`, `=`,
  `✎`). `show_log` counts the `!`, `U`, and `=` marks into
  `#mark-counts`, beside the Quit button (`MARK_COUNTS`,
  `mark_count_lines`; tests' `mark_counts` reads it), long or short to
  fit its width (also refit in `fit_log`). Test rows need distinct IDs
  (`new_id()`), or the `2` mark shows. The app keeps log files
  beside settings (`settings_path.parent`), so the test fixtures' temp
  dir covers both.
- Selecting and editing: the log's `CellSelected` (double-click, or
  Enter) sets `app.selected`, switches the table to a row cursor with
  the `-selected` class, and calls `EntryForm.show(entry)` (fields
  disabled, what the form held put aside); `RowHighlighted` moves the
  selection, or snaps back to the edited row while editing. `f3` calls
  `EntryForm.edit()`; Enter runs the usual checks (an edit that reads
  the same, `unchanged_edit`, stops after the field checks and steps
  back as Esc does), then `submit` posts
  `Edited(old, new)` instead of `Submitted`, and the app's
  `on_entry_form_edited` saves it with `Logbook.replace`, then calls
  `finish_edit(new)`. Esc (`action_step_back`) goes from editing to
  selected (`finish_edit`), then to none (`EntryForm.hide`). `f4`
  confirms with `DeleteScreen` (Enter twice), then `Logbook.delete` and
  the app's `entry_deleted`. Entries are
  matched by identity (`is`): `session_entries`, `typed_entries`,
  `saved_entries`, and
  `EntryForm.logged` share the same dicts. Every entry dict carries its `STATION_CALLSIGN`.
- The log table shows `typed_entries` (typed since start or the last
  Sort, in typed order) above
  `saved_entries` (newest first), and is redrawn in full on each save
  (`show_log`), since DataTable can't insert a row mid-table.
  Its first column, with no header, is the status marker
  (`SESSION_MARKER` on session entries, `EDITED_MARKER` on saved ones in
  `edited_entries`); tests' `table_rows` leaves it out (and strips
  padding), and `table_markers` reads it. When there
  are typed entries, the first saved row is overlined as a divider
  (`DIVIDER_STYLE`).
- Sort (`f5` on the cell cursor's column, or `HeaderSelected`) is the
  app's `sort_log`: refused rows first, then every other entry (typed
  ones moved out of `typed_entries`) by `sort_key`; `sort_by` holds the
  column and direction for the header's arrow (`header_cell`). Only with
  the cell cursor (no row selected: `check_action` dims f5, and the
  header handler checks `selected`). `sort_key`'s DATE/TIME behavior is
  decided (see REQUIREMENTS.md Log view); keep it.
  `session_entries` holds every entry typed this session, for the `•`
  mark (`saved_marker` gives it once sorted in).
- Log cells are Rich `Text` built by `log_cell`, padded a space each
  side, with the table's `cell_padding` at 0, so the divider's line is
  unbroken; column widths (`log_columns`: `LOG_COLUMNS`, with COMMENT
  filling the log's width, or as wide as the longest shown) plus 2 for
  that padding.
  Never pass DataTable a plain `str` cell: it's parsed as Rich markup,
  which hid brackets in a COMMENT and crashed on `[/]`.
- Log table columns use fixed widths: Textual's DataTable doesn't redraw
  rows already drawn when an auto-width column widens. COMMENT's still
  follows the entries and the log's width, as `show_log` rebuilds the
  columns on each redraw, and the app's `fit_log` (on the screen's
  layout signal) redraws when the width calls for a new one, keeping
  cursor and scroll.
- An App subclass's `on_mount` doesn't need `super().on_mount()`:
  Textual calls each class's handler, so that runs the app's twice (in a
  scratch script, use `on_ready` for setup after mount).
- Textual CSS quirks met so far (see entry_form.py and app.py):
  a single edge like `margin-bottom` in a more specific rule resets the
  other three sides, so set all four; `height: auto` doesn't count a
  horizontal scrollbar, so keep outer spacing in margins, not padding.
  A screen's `AUTO_FOCUS = None` means the app's setting (focus the
  first focusable); `""` focuses nothing (WarningScreen, so Enter
  confirms until Tab picks a button). A focused Button ignores a second
  Enter during its 0.2 second press effect.

## Testing notes

- Hand-test data in `data/` (made only when asked): a COMMENT saying how
  a record came about is marked when that didn't literally happen, so it
  can't be taken for the real thing: `Simulated hand-added in Calc`, or
  `$Hand-added in Calc` when short of room (`$`: S for simulated, and
  ASCII), or `SIM Hand-added in Calc` where `$` might clash with
  something. A row really made that way (e.g. in Vim, run from the
  terminal) reads plainly. A plain fact about the row as written (`ID in
  uppercase`) needs no mark.
