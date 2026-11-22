# POTA Logger — Test suite history

Why the suite is shaped and paced as it is. How to run the tests is in
[DEVELOPMENT.md](../DEVELOPMENT.md#tests).

The test suite was sped up 2026-10-05, from about 4 minutes (699 tests)
to about 40 seconds: tests run in parallel with pytest-xdist (`-n auto`
by default, in pyproject.toml), and the COMMENT limit test fills the
field to near its limit instead of typing 103 keys. Profiling an app
start (about 0.35 seconds, plus about 0.25 seconds settling before the
first key) found it almost all in Textual's own styling and layout; the
one cost of ours, the notifications' class set on the
screen, which restyled every widget, now goes on the ToastRack alone.
`test_typed_entry_with_tab_between_fields` and
`test_rows_drawn_in_full_without_redraw` (about 7 seconds each) type key
by key on purpose (key-by-key entry, and a redraw bug that needed it).
Each field's "blocks entry" app test stays, though its parser's unit
tests check the same message (decided 2026-10-05): it's what proves the
field is wired into the form's checks (`PARSERS`, `REPORTS`, focus), which
a unit test can't. Full coverage is preferred over speed; with tests in
parallel they cost about 1 to 2 seconds.

Checked again 2026-10-10: 935 tests took about 100 seconds. The
2026-10-05 suite (699 tests) still runs in about 46 seconds on the same
machine, and the cost of a key press or an app start hasn't changed, so
the rise is growth: app tests went from 172 to 278 and run somewhat
longer each. The rest was workers left idle at the end: xdist's default
`load` scheduling hands out tests in advance, so slow ones bunch up on a
few workers. `--dist worksteal` (idle workers take tests from busy ones)
brought it to about 72 seconds. Splitting `tests/test_app.py` into
`tests/app/`, a file per area (2026-10-10, for readability), brought it
to about 55, likely as smaller files spread more evenly across the workers.
