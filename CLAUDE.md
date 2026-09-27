# POTA Logger T3

Textual TUI logbook for hunting POTA parks, managed with uv (Python 3.13).
REQUIREMENTS.md is the source of truth for scope and field rules; keep it
updated in the same change whenever a rule changes.

## Commands

- Run the app: `uv run pota-logger-t3`
- Run tests: `uv run pytest`
- Install the callsign guard git hooks (once per clone):
  `uv run python -m pota_logger_t3.callsign_guard install`

## How we work

- Build in small "horizontal" steps: only what the current request needs.
  Don't scaffold ahead or add functions before a step uses them.
- Add or update tests alongside each change.
- After code changes are done, stage what makes sense, draft a commit
  message, and pause there. Don't run `git commit` until the user reviews
  the diff/stage/message and app behavior and gives a clear go-ahead to
  commit, in whatever natural phrasing ("Proceed", "Proceed with commit",
  "Looks good, proceed", "Go ahead and commit", etc.).
- Commit messages: short subject line, a body with details when useful,
  then the Co-Authored-By trailer. The first commit in a repo is always
  `Initial Commit`.
- When a request is ambiguous (especially about UI behavior), ask instead
  of guessing.
- REQUIREMENTS.md's "Status and plan" section says what's built and
  what's next; update it when a planned item lands.

## Entry checks: block vs warn

- Block (refuse with a notification, focus the field) only what can't be
  right: a report digit out of range, a frequency outside the bands.
- Warn (modal, Enter saves anyway) what's probably wrong but could be
  real, like a special-event call or a dupe. The operator copies a paper
  log, so a real but odd contact must never be unsaveable.
- Messages use the operator's ham shorthand ("Possible dupe", not
  "duplicate"). Warning messages end with "Esc to correct, or confirm
  with Enter." and use explicit line breaks so they wrap cleanly.

## Privacy

- Never put the operator's real station callsign in tracked files, tests,
  examples, or commit messages. Use made-up calls like `W1TST` or `W1ABC`.
- The real callsign lives only in `data/settings.toml`; `data/` is
  git-ignored. The callsign guard hooks are a backup, not the main rule.

## Code notes

- Each entry field with rules has a small module with `parse_*` (raises
  ValueError with a message shown to the operator) and, if displayed
  differently, `format_*`: freq.py, modes.py, callsigns.py, parks.py,
  states.py, reports.py, power.py, dates.py. sidebands.py holds the
  MODE-and-FREQ sideband rules.
- `entry_form.py` holds `FIELDS` (name, placeholder, longest value),
  `PARSERS`, `REPORTS` (parsed after, since they depend on MODE),
  `OPTIONAL`, `DEFAULTS`, `CARRY_FORWARD`, and `WARNINGS`. `__init__.py`
  holds `FORMATTERS` and `DISPLAY_LENGTHS` for the log table.
- Warnings (probably wrong, but saveable) are checks in entry_warnings.py
  listed in `WARNINGS`, shown in warning_screen.py. Each check takes the
  entry and the entries logged so far (`EntryForm.logged`). The unusual-CALL
  warning has its own modal (callsign_warning_screen.py) so the call can
  be edited there.
- On Enter, `EntryForm.on_input_submitted` runs, stopping at the first
  problem: missing fields, `PARSERS`, `REPORTS`, `check_sideband`, the
  unusual-CALL modal, then each of `WARNINGS` in order.
- Log table columns use fixed widths: Textual's DataTable doesn't redraw
  rows already drawn when an auto-width column widens.

## Testing notes

- Tests never touch the real `data/`: use the `settings_path` / `app`
  fixtures in tests/conftest.py, which point at a temp dir.
- tests/test_app.py builds on `ENTRY` (USB on a 20m voice frequency) and
  `CW_ENTRY`. A test that saves several entries needs a different CALL on
  each, or the possible-dupe warning stops it. Use past dates, or
  `991231` for a future one.
- To see what the TUI draws (it can't be previewed in the browser), run
  the app with `run_test(size=(100, 24))` in a scratch script, and print
  `"".join(seg.text for seg in strip)` for each strip in
  `app.screen._compositor.render_strips()`.
