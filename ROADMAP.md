# POTA Logger — Roadmap

What's built, and what's next. The field rules and behavior these items
refer to are in [REQUIREMENTS.md](REQUIREMENTS.md); release mechanics are
in [RELEASING.md](RELEASING.md); design decisions are in
[DECISIONS.md](DECISIONS.md); test-suite history is in
[tests/TESTS.md](tests/TESTS.md).

Built: the entry form with every planned field (COMMENT included), its
field rules, blocks, and warnings, all fitting ADIF (see [Entry behavior](REQUIREMENTS.md#entry-behavior));
the log table (this session's entries as typed, marked `•`, above the
saved ones newest first, with a divider between, and saved ones edited
this session marked `✎`; see [Log view](REQUIREMENTS.md#log-view)); CSV
storage (see [Storage](REQUIREMENTS.md#storage)), with each log row and the settings file's
station callsign checked at start against the entry rules that refuse a
value, each held to what the app writes (how a value is written fixed
on load), and hand-tested in Vim
and LibreOffice Calc (see [Storage](REQUIREMENTS.md#storage) and [Settings](REQUIREMENTS.md#settings)), and kept by the app as its own copy
while it runs, the only source of truth for the log files; deleting an entry (see [Editing](REQUIREMENTS.md#editing)); fixing or deleting a row refused on
load, in the app, with how a value is written fixed on load (see [Storage](REQUIREMENTS.md#storage)); a record ID on every log row, with rows
sharing one marked `U` (see [Storage](REQUIREMENTS.md#storage)); definite dupes, blocked on Enter and
marked `=` at start (see [Entry behavior](REQUIREMENTS.md#entry-behavior)); the status bar; the
settings modal, opened to set the station callsign at first start,
checked like CALL and required before any entry is saved, with every
log row held to it (see [Session-level value](REQUIREMENTS.md#session-level-value));
the counts of rows marked `!`, `U`, and `=` beside the Quit button
(see [Log view](REQUIREMENTS.md#log-view)); a block at start, with the errors in `file_errors.txt`,
while log files need fixing by hand (see [Storage](REQUIREMENTS.md#storage)); notifications stacked
at the bottom right of the log
area, a row above the Quit button rather than over it,
and a row above the log's sideways scrollbar while it shows (Textual's ToastRack raised by
CSS, a small override of stock looks); a light
outdoors color theme (leaf and grass greens with orange warnings, in
theme.py); the footer keys and terminal size; sideways scrolling of the
form in a narrow window; selecting a log row and editing its entry in
the form (see [Editing](REQUIREMENTS.md#editing)); the log's COMMENT column filling the log's
width, or as wide as the longest COMMENT shown, apart from the form's
100-character limit, so the divider reaches the right edge (see
[Entry fields](REQUIREMENTS.md#entry-fields)); the Sort action, `f5` or a header click (see [Log view](REQUIREMENTS.md#log-view)); COMMENT's
POTA info, two settings in a Settings modal now open after setup (see
[COMMENT's POTA info](REQUIREMENTS.md#comments-pota-info)); the form's
fields in entry order, apart from the log's paper-log order (see
[Entry fields](REQUIREMENTS.md#entry-fields)); Tab between a modal's two buttons (see [Entry behavior](REQUIREMENTS.md#entry-behavior)); an
unchanged edit saving nothing and left unmarked (see [Editing](REQUIREMENTS.md#editing)). The visual layout is settled; wording tweaks
can still come up as they're noticed.

ADIF file export is built (2026-10-09; see [Export](REQUIREMENTS.md#export)): the ADIF record
module (each entry as one ADIF record, for both the file export and
the API), the export folder setting, and the Export modal (`f6`, or
the ADIF button, which replaced the Settings button). The export folder
defaults to `exports/` beside `data/`, made by the app (2026-10-11; see
[Settings](REQUIREMENTS.md#settings)).

Support for POTA's parks list is built (2026-10-10; see [Export](REQUIREMENTS.md#export),
POTA's parks list), taken before the QRZ.com API (decided 2026-10-09,
as the more straightforward): the download, offered at first start and
checked for updates from Settings; the park's name on COMMENT's label
row (with a multi-state park's states while typing or editing, built
2026-10-13), ST filled from the park, warnings on an unlisted or inactive park
and on an ST not the park's, and DXCC (and a multi-state park's
location) in the export.

The loose ends before a first release are done (2026-10-10): calendar
versioning and the release script, a changelog (CHANGELOG.md, which the
release script dates), installing with `uv tool install`, the MIT
license, DEVELOPMENT.md and RELEASING.md, a checked test suite, and the
code and tests grouped into folders (`fields/`, `screens/`, the app in
`app.py`; `tests/` mirroring them). The first release, 2026.10.10, is
made. README.md's install commands use the GitHub repository
(https://github.com/bmchandler/pota_logger, 2026-10-12).

The check for a newer release is built (2026-10-12; see [Settings](REQUIREMENTS.md#settings),
Updates): a toast at start, or an upgrade once the app quits, chosen
in Settings. Hand-tested by the operator (2026-10-13), with 2026.10.13
installed and 2026.10.13.1 on GitHub: Notify showed the toast, No
notification showed none, Notify again showed it, Automatic on Quit
upgraded cleanly, and Notify on the new release showed none. Not yet
tried by hand: a start with no network.

Next, after the first release: real use. QRZ.com API integration (see
[Export](REQUIREMENTS.md#export), QRZ.com API) is on hold until the operator has used the ADIF
export in a few real sessions, outside the development VM, importing
the files into QRZ.com. Known issues that won't be fixed are listed in
README.md's Noted issues.

Versioning is decided (2026-10-10; see [RELEASING.md](RELEASING.md)): calendar versions,
set with `uv version` and tagged together by `tag_new_version.py`
(built 2026-10-10), when the operator asks for a release.

The branch model is built (2026-10-11; see [RELEASING.md](RELEASING.md)):
`main` at the newest release, work and releases on `dev`, the release
script moving `main` forward, dev builds reporting `+dev.<commit>` and
keeping their files in `~/.local/share/pota-logger-dev/`, and
`branch_guard.py`'s hooks. Hand-tested by the operator outside the VM
(2026-10-11): a release install and an `@dev` install each set up in
their own folder, with exports defaulting to that folder's `exports/`,
and the dev build's export reporting `2026.10.11+dev.7601686b`, the
installed commit.

The Info modal is built (2026-10-12; see [Theme and keys](REQUIREMENTS.md#theme-and-keys)), and the
project is mirrored to GitHub (https://github.com/bmchandler/pota_logger),
where README.md's install commands point.

Installing with `uv tool install` is built (2026-10-10; see [Storage](REQUIREMENTS.md#storage)):
installed, the app keeps its files in `~/.local/share/pota-logger/data/`,
with a `README.txt` beside it; a clone keeps using its own `data/`.

The editing plan (decided 2026-10-04) is built: the log is where records
are checked and fixed, with no need to open a CSV. Its status column shows
each row's state, the form makes every change, and only the operator
changes a record.
