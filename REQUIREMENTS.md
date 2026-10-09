# POTA Logger — Requirements

## Purpose

A local TUI logbook for **hunting** POTA parks, tuned for fast manual entry of
contacts first recorded by hand in a paper logbook.

Workflow: paper logbook → manual entry in this app → ADIF export → QRZ.com
ADIF import.

Reference: <https://docs.pota.app/>

## Scope

In scope:

- Logging hunter contacts (voice and CW) on US amateur bands from 80m to
  10m, including the WARC bands (3.5 to 29.7 MHz). 160m, 60m, 630m, and
  2200m are left out as impractical or rare for POTA.
- Local storage in human-readable CSV files.
- ADIF export aimed at QRZ.com import (built after the logbook itself is
  settled).

Out of scope:

- Activator features.
- Submitting logs to POTA.
- Digital modes.
- More than one call per log (decided 2026-10-06): every record holds
  the one station callsign; no OPERATOR field, and no multiple logbooks
  (not even separate logbooks under one call). A call change is rare (a
  new license class, or a call inherited) and has always meant a new
  logbook: archive the old log files, then set the new call in
  `data/settings.toml`. A club's Field Day log belongs in its own setup.

Future (not now):

- QRZ.com API integration: likely the next stage after ADIF export, if
  pursued (see Status and plan).

## Status and plan

Built: the entry form with every planned field (COMMENT included), its
field rules, blocks, and warnings, all fitting ADIF (see Entry behavior);
the log table (this session's entries as typed, marked `•`, above the
saved ones newest first, with a divider between, and saved ones edited
this session marked `✎`; see Log view); CSV
storage (see Storage), with each log row and the settings file's
station callsign checked at start against the entry rules that refuse a
value, each held to what the app writes (how a value is written fixed
on load), and hand-tested in Vim
and LibreOffice Calc (see Storage and Settings), and kept by the app as its own copy
while it runs, the only source of truth for the log files; deleting an entry (see Editing); fixing or deleting a row refused on
load, in the app, with how a value is written fixed on load (see Storage); a record ID on every log row, with rows
sharing one marked `U` (see Storage); definite dupes, blocked on Enter and
marked `=` at start (see Entry behavior); the status bar; the
settings modal, opened to set the station callsign at first start,
checked like CALL and required before any entry is saved, with every
log row held to it (see Session-level value);
the counts of rows marked `!`, `U`, and `=` beside the Quit button
(see Log view); a block at start, with the errors in `file_errors.txt`,
while log files need fixing by hand (see Storage); notifications stacked
at the bottom right of the log
area, a row above the Quit button rather than over it,
and a row above the log's sideways scrollbar while it shows (Textual's ToastRack raised by
CSS, a small override of stock looks); a light
outdoors color theme (leaf and grass greens with orange warnings, in
theme.py); the footer keys and terminal size; sideways scrolling of the
form in a narrow window; selecting a log row and editing its entry in
the form (see Editing); the log's COMMENT column filling the log's
width, or as wide as the longest COMMENT shown, apart from the form's
100-character limit, so the divider reaches the right edge (see Entry
fields); the Sort action, `f5` or a header click (see Log view); COMMENT's
POTA info, two settings in a Settings modal now open after setup (see
COMMENT's POTA info); the form's
fields in entry order, apart from the log's paper-log order (see Entry
fields); Tab between a modal's two buttons (see Entry behavior); an
unchanged edit saving nothing and left unmarked (see Editing). The visual layout is settled; wording tweaks
can still come up as they're noticed.

To do, in this order (decided 2026-10-09): an ADIF record module
(each entry as an ADIF record, needed by both of the next two); ADIF
file export (see Export); possibly QRZ.com API integration (see Export,
QRZ.com API); then support for POTA's parks list (see Export, POTA's
parks list). Known issues that won't be fixed are listed in README.md's
Noted issues.

The test suite was sped up 2026-10-05, from about 4 minutes (699 tests)
to about 40 seconds: tests run in parallel with pytest-xdist (`-n auto`
by default, in pyproject.toml), and the COMMENT limit test fills the
field to near its limit instead of typing 103 keys. Profiling an app
start (about 0.35 seconds, plus about 0.25 seconds settling before the
first key) found it almost all in Textual's own styling and layout; the
one cost of ours, the notifications' class (see above) set on the
screen, which restyled every widget, now goes on the ToastRack alone.
`test_typed_entry_with_tab_between_fields` and
`test_rows_drawn_in_full_without_redraw` (about 7 seconds each) type key
by key on purpose (key-by-key entry, and a redraw bug that needed it).
Each field's "blocks entry" app test stays, though its parser's unit
tests check the same message (decided 2026-10-05): it's what proves the
field is wired into the form's checks (`PARSERS`, `REPORTS`, focus), which
a unit test can't. Full coverage is preferred over speed; with tests in
parallel they cost about 1 to 2 seconds.

The editing plan (decided 2026-10-04) is built: the log is where records
are checked and fixed, with no need to open a CSV. Its status column shows
each row's state, the form makes every change, and only the operator
changes a record.

Also not built: ADIF export.

Ideas considered and deferred:

- A CW warning within about 1 kHz of a band edge. Left out for now: a CW
  signal is narrow, and radios differ on whether the dial shows the
  transmit frequency or is offset by the CW pitch.
- Defaulting DATE to "UTC now minus a few hours", which would suit
  operators in any time zone. The local-date default fits the current
  operator (US Eastern).
- A setting for the screenshot folder (Downloads now). Textual takes a
  folder per screenshot but doesn't expand `~` or `$HOME` and doesn't
  create missing folders, so the setting would need all of that built.
- A Keys help panel (Textual's, from the command palette). Textual's
  input fields already use ctrl+k (delete to the end), and overriding
  stock bindings is avoided, so it was dropped with the palette.
- Lining the narrow form's scrollbar up exactly with the input boxes.
  Textual's input borders put the visible edge partway into a cell, so
  it would take non-stock input borders; the stock look was kept.
- Dates before 2000 (or after 2099). The entry form's YYMMDD covers
  2000 to 2099, and log rows outside it are refused on load, so an edit
  can't change their year. Reassess closer to release, e.g. for importing
  older logs from ADIF: take them gracefully, or still refuse them if
  that's much simpler.
- Bulk edits (e.g. PWR across a session) and undo: not planned. Entries
  are copied from paper one at a time, so bulk edits add little and
  raise the risk of mistakes; an entry is fixed by editing or deleting
  it. Revisit only if real use calls for them.
- A limit on digits in a callsign. ADIF sets none, and special-event
  calls use years and anniversaries (`W100AW`); the unusual-callsign
  warning covers typos like `W111111AB`.
- PARK as a comma list of parks (`1234,2345,3456`), mirroring ADIF's
  `POTA_REF`, for a 2-fer or more in one entry (see Entry behavior,
  multi-park activations). The better path if multi-park entries become
  worth it: the input already scrolls, so the form wouldn't change, but
  the log column, the load checks, the dupe check, sorting, COMMENT's
  POTA info, and ST (parks in different states) all would. A separate
  field for extra parks was set aside: it needs room in the form, and a
  fixed number of fields would cap the parks.

## Entry fields

In paper-log order, the order of the log table's columns and the CSV
files'. The form's top row takes them in entry order instead (decided
2026-10-08): FREQ, CALL, PARK, ST, SNT, RCD, TIME, PWR, DATE, MODE. The
fields typed on every entry come first, without a Tab past a field that
rarely changes; PWR (changes now and then in a session), DATE (once a
session, or twice across a UTC midnight), and MODE (nearly always the
same all session) come last, so Enter is usually pressed before reaching
them. COMMENT stays below the row. All times and dates are UTC.

| Field | Entered as | Stored as | Displayed as | Notes |
|---|---|---|---|---|
| FREQ | Always MHz, shorthand allowed: `14`, `14.1`, `14.0745`, `14.074.5`, `14074`, `28312456` | Integer Hz | Always in full: `14.000.000`, `14.074.500` | Never carried forward. Missing digits are filled with zeros. After a dot, up to 6 fractional MHz digits, optionally with a second dot after the 3 kHz digits (`14.1` is `14.100.000`; `14.0745` and `14.074.5` are `14.074.500`). Bare digits are the same with the dot left out; the MHz part is whichever of 1 or 2 leading digits lands in a band (`141501` is `14.150.100`, `3985` is `3.985.000`). Across 80m to 10m only one reading ever fits. Must be inside a US amateur band from 80m to 10m. |
| MODE | `SSB`, `USB`, `LSB`, or `CW`, any case | Uppercase text | Same | `SSB` at app start, then carried forward (decided 2026-10-08: a session switched to CW is likely CW throughout). Typed, with no drop-down, auto-complete, or single-letter shortcuts; Tab just moves to the next field. Last in the top row of the form. `SSB` means the standard sideband (LSB below 10 MHz, USB above) and is what's logged away from voice edges. `USB`/`LSB` are logged near a voice edge, to record which side of the dial the signal was on. SSB with FREQ (the dial frequency) at a voice range edge or less than 3 kHz inside it is refused: log USB or LSB there. |
| CALL | Any case, e.g. `w1abc`, `VE3/w1abc/p` | Uppercase text | Same | International and slash calls allowed. Shape check only: letters, digits, and up to two `/`, no empty parts, and at least one part shaped like a call (prefix, a digit, then a suffix ending in a letter). Prefixes aren't checked against a country table, so special-event calls like `GB250RSGB` still work. Warns (see Entry behavior) when no part is in ITU's normal form: a prefix, one digit, then 1–4 letters. The prefix is 1 letter only for countries holding a whole letter (`B`, `F`, `G`, `I`, `K`, `M`, `N`, `R`, `W`), which may also use 2 letters; otherwise it's 2 characters, possibly with a digit (`VE`, `9A`, `3D`). So `W11BC` and `W100AW` warn. |
| PARK | `1234`, `464`, `JP1234`, `JP-1234`, `4X-12`, `US-4566@US-WY`, any case | POTA reference: `US-1234`, `US-0464`, `JP-1234`, `4X-0012`, `US-4566@US-WY` | Same | One park per entry. Must fit ADIF's POTA reference: PROGRAM-NUMBER, optionally @LOCATION. The program is 1 to 4 letters and digits with at least one letter; a bare number means a US park (`US`). The dash may be left out when the program ends in a letter (`jp234`). The number is 4 or 5 digits; shorter numbers get leading zeros (`464` is `US-0464`), so `4640` must be typed in full. LOCATION is a 4 to 6 character ISO 3166-2 code (`US-WY`), only for parks spanning more than one, like trails. Anything else is refused; a number over 5 digits gets its own message (`parks must be <= 5 digits`), since the rest of its shape is right. The field stays 8 characters wide, sized for common references, and scrolls up to ADIF's longest reference (17 characters); the log column is 17 wide. |
| ST | `NJ`, or blank | Uppercase text | Same | State the park is in. Optional, even for US parks, since it isn't always clear at entry time. If given, must be a US state code (50 states plus DC). Blank, not `NA`, for a park outside the US (decided 2026-10-08): QRZ.com and similar logbooks leave the state blank there, and have no field for a POTA location like `BB-PH` (which can go in COMMENT). Not checked against the park; no park database is kept until POTA's parks list is supported (see Export, POTA's parks list). |
| SNT | `59` / `599` | Text | Same | Comes before RCD on purpose. Digits only. The digit count follows MODE: `CW` takes exactly 3 (`599`), other modes exactly 2 (`59`), in the entry form and on load alike. A 2-digit CW report is possible but rare, and with modern radios the tone digit is nearly always 9, so a missing third digit on CW is most likely a slip in copying: it's refused (`SNT '59' needs 3 digits on CW, like 599`) and the operator adds the digit (no auto-fill). An operator whose contact needs a 2-digit CW report to confirm on QRZ.com can sort that out there. The placeholder follows MODE as a hint: `599` while MODE is `CW` (any case), `59` for any other MODE typed. It updates when leaving MODE (Tab, Shift+Tab, or a click), not on each keystroke, and stays as it was after a save, since MODE carries forward. With MODE last in the form, a new session's first CW entry shows `59` while the reports are typed; the digit check on Enter catches a missing third digit. Only the placeholder changes, which shows only while the field is empty: a value already typed is never cleared or changed. The non-ASCII message's example (`59, or 599 on CW`) stays as is. Each digit must be in range (RST): readability 1–5, strength 1–9, tone 1–9, so `69` or `590` is refused. |
| RCD | `59` / `599` | Text | Same | Same rules as SNT. |
| PWR | Watts as a number: `60`, `2.5`, `.5` | Decimal watts | `60W`, `2.5W`, `.5W` | Carried forward. 0.1 to 1500 watts (US legal limit). No `W` when typing. |
| DATE | `260925` (YYMMDD, years 2000–2099) | Part of the entry's UTC timestamp (`20260925` in CSV) | `2026.09.25` | Carried forward. Must be a real calendar date. Still a UTC date; only the *default* on app start is today's local date (not UTC), since the app is usually opened right after a session and the first entries typed often predate a UTC midnight rollover that's already happened locally. |
| TIME | `1953` (24-hour HHMM) | Part of the entry's UTC timestamp (`1953` in CSV) | `19:53` | Must be a real time, 0000 to 2359. |
| COMMENT | Free text, e.g. `POTA US-1234 NC`, `RSGB Field Day Serial #042` | Text, as entered | Same | Optional. On its own line below the other fields, as wide as that row, and takes only what fits there (currently 100 characters). Any plain ASCII character is allowed (see the non-ASCII rule in Entry behavior). Never carried forward: it's the operator's own note, whose use changes over time. Filled in by the app only with its POTA info, when Settings turns that on (see COMMENT's POTA info below). Its log column follows TIME and fills the rest of the log's width (beside its vertical scrollbar, when shown), so the columns and the divider reach the right edge; it widens past that for the longest COMMENT shown, so each is seen whole, a longer one from a file included, and is never narrower than its header. The log scrolls sideways when it's wider than the window. The column is worked out again on each redraw of the log (each save, edit, or delete) and when the log's width changes (the window resized, or the vertical scrollbar coming or going), keeping the cursor, selection, and scroll. Exported as ADIF `COMMENT` (what QRZ shows as Comments). |

Session-level value:

- **Station callsign:** the operator's own call. It's shown in a top status
  area and recorded on each entry (ADIF `STATION_CALLSIGN`). It's set in the
  settings modal at first start, and only then: a log holds one call (see
  Scope), so once one is set, Settings (F2, or the Settings button)
  opens without it (decided 2026-10-08). A call change means a new log:
  archive the log files, then edit `data/settings.toml` by hand.
- **One call per log** (decided 2026-10-06): every log row's
  STATION_CALLSIGN must be the station callsign, checked at start; a row
  with another call is refused (see Storage) and fixed by hand. So the
  log files are loaded only once a call is set: at first start, the log
  stays empty behind the station-callsign block until a call is saved.
  Same shape check as CALL (letters, digits, up to two `/`, shaped like a
  call), uppercased; saving anything else is refused and the modal stays
  open, with why below the call in the error color (as the form shows
  problems below COMMENT), only after a Save that couldn't, and gone
  once the call is edited. An unusual call (same rule as CALL, e.g. `W11BC`, `W100AW`) opens
  the same unusual-callsign warning as CALL, where it can be corrected:
  Enter saves, Esc goes back to the settings modal.
- **Required:** no entry can be saved without a station callsign set.
  While none is set, the status bar shows `NOCALL` and the usual warning
  modal, used as a block, reads `A valid callsign for transmitting` /
  `station is required.` / `Press Enter to go to Settings.`, with no way
  to save
  anyway, no Esc, and one button, Settings: Enter opens the settings
  modal. It shows when the app starts with none set (first run, or a
  `data/settings.toml` with none, a bad one, or invalid TOML), and when
  Settings is left with none: saved with the call cleared (the blank is
  saved) or cancelled with none set. From there, Enter opens Settings
  again. On Enter in the form with none
  set, it shows too, and the entry stays in the form (Settings always
  ends with a call set, so this is a safety net). Ctrl+Q quits from
  anywhere (stock Textual, and works in any modal), for an operator not
  ready to set it yet. Ctrl+C stays stock (it doesn't quit).

## Settings

- A settings modal holds app-wide settings: the station callsign while
  none is set (see Session-level value), then two checkboxes (stock
  Textual: Space or Enter toggles one), both off by default, since
  others may not want them. A box shows its X only when checked (decided
  2026-10-08; stock, a dimmed X shows when unchecked too, which reads as
  checked):
  `New: Pre-populate COMMENT with POTA info.` and
  `Edit: Update COMMENT with POTA info.` (see COMMENT's POTA info). It
  opens at first start, from the station-callsign block, and after that
  with F2 or the Settings button, showing only the checkboxes. Save (or
  Enter in the call) saves them all; Esc or Cancel changes nothing.
- In `data/settings.toml` they're `new_comment_pota_info` and
  `edit_comment_pota_info`, `true` or `false`; a missing one is off (a
  file from before them). Anything else (`"yes"`) is off and blocks at
  start like a log file needing fixing by hand (see Storage):
  `<file>: new_comment_pota_info 'yes' must be true or false`. Fixing the
  call's spaces or case isn't saved then, as saving would hide the
  problem.
- Settings are saved in `data/settings.toml`.
- At start, the file is checked like the log files (see Storage).
  Invalid TOML is reported as `Couldn't read <file>:
  <error>`. The station callsign gets CALL's checks that refuse a value
  (plain ASCII, then its shape), with CALL's messages naming the
  `station_callsign` key: `<file>: station_callsign 'W1' doesn't look
  like a callsign, like W1ABC`. As in a log file (see Storage), how the
  call is written is fixed at start, and the file saved again, with no
  message (decided 2026-10-07; they were refused): spaces around it and
  its case (` w1abc ` as `W1ABC`). If the file can't be written, the
  call is still used as fixed, and fixed again at the next start. A
  refused call leaves the app
  starting with no call set, so the station-callsign block follows (see
  Session-level value), with the problem between its two parts, in the
  error color, after a blank line and before one, full path included
  (where `data/` is isn't obvious); it stays each time the block comes
  back until Settings is saved, which rewrites the file. (Decided
  2026-10-05; it was a notification at start.) A refused call opens in Settings, ready to
  correct (most likely a slip); it's there again if Settings is cancelled,
  until a call is saved, which rewrites the file. Saving uppercases it,
  as usual. An unusual call (`W100AW`) loads without a warning: a value
  from a file is taken as meant. Only an empty call (`""`, or just spaces)
  means none is set yet.

## COMMENT's POTA info

Decided 2026-10-08. QRZ.com doesn't show POTA info, so the operator tags
an entry's COMMENT with it, which Settings can have the app fill in.

- `New: Pre-populate COMMENT with POTA info.`: a new entry's COMMENT
  starts as `POTA ` (a space to type on after), at start, after each
  save, and when the setting is turned on with COMMENT blank. On leaving
  PARK or ST (Tab, Shift+Tab, or a click), and on Enter (which doesn't
  leave the field), it's rewritten from the values as they read:
  `POTA US-1234 NJ`, `POTA US-1234` (or `POTA BB-0010`) with ST blank or
  not a state, and `POTA ` again until PARK reads. An ST typed before
  PARK waits for it (no `POTA NJ`). Turned off, a COMMENT that's still
  just the app's goes blank.
- `Edit: Update COMMENT with POTA info.`: while editing a saved entry,
  its COMMENT is rewritten the same way if it starts with the POTA info
  its PARK and ST give; otherwise (blank, or other text) it's left alone.
- Only the POTA info at the start of COMMENT is rewritten; whatever
  follows it is kept (`POTA US-1234 NJ Great signal` with PARK 5678 is
  `POTA US-5678 NJ Great signal`). Once that info is changed by hand, or
  something is typed after a bare `POTA ` (most likely the info itself),
  COMMENT is the operator's and isn't changed, unless it already starts
  with the info PARK and ST give, which the app then takes as its own
  (so `POTA US-1234 NJ` typed by hand isn't repeated). A rewrite that
  wouldn't fit COMMENT's limit is skipped.
- QRZ has no field for a POTA location like `BB-PH`; it can go in
  COMMENT, typed after the info.

## Theme and keys

- The app always uses its own light outdoors theme; there's no theme
  switching.
- The footer shows `^q Quit`, `f2 Settings`, `f3 Edit` and `f4 Delete`
  (see Editing), `f5 Sort` (see Log view), and `^s Screenshot` (saves an SVG of the screen to the Downloads
  folder).
- The footer's right end shows the terminal size as columns x rows
  (`120x30`), updated live as the window is resized.
- No command palette (Textual's ctrl+p): "palette" is unfamiliar to most
  operators.

## Entry behavior

- Entries must fit the ADIF standard, since ADIF export is the goal:
  anything ADIF doesn't allow in a field is refused, whatever QRZ or other
  logbooks accept. Anything ADIF allows is accepted, unless a field's rules
  here say otherwise.
- Every field, the station callsign, and the call in the unusual-CALL
  modal take only plain ASCII (codes 32 to 126: every character on a US
  keyboard), checked before the field's own rules. Anything else (`５`,
  `é`, `°`, curly quotes, emoji) is refused, naming each character once,
  in order: `SNT '５９' has non-ASCII characters: '５', '９'.` / `Use plain
  ASCII, like 59, or 599 on CW.` The example is the field's placeholder
  (COMMENT has none, so its message ends after the characters). No
  multi-language support is planned.
- Fields can be filled and edited in any order before an entry is saved.
- When the window is narrower than the entry form (107 columns today:
  the top row plus its margins), the form gets a horizontal scrollbar,
  starting at the fields' left column, with a blank row above and below
  it (moving the log down two rows); moving to a field scrolls it into
  view.
  At full width the scrollbar goes away. The form and the log scroll
  separately.
- An entry can't be saved until every required field is filled in and valid.
  ST and COMMENT are the only optional fields.
- Only DATE, PWR, and MODE carry forward to the next entry (MODE starts
  as `SSB` at app start). Everything else is entered fresh each time.
- Multi-park activations (decided 2026-10-09): one entry per contact,
  under the park the activator is spotted at (as the POTA site lists
  it), with the other parks in COMMENT (`POTA US-1234 NC, US-2345,
  US-3456`; typed after the app's POTA info, so it keeps updating). One
  entry per park isn't an option: QRZ.com takes entries with the same
  CALL, BAND, MODE, DATE, and TIME as dupes and keeps only one. Hunters
  get park credit from the activator's log, not their own. PARK as a
  list is a deferred idea (see Status and plan).
- Entries may be typed in any time order, with no warning. The paper log
  isn't always in time order (an entry is sometimes finished after later
  ones), and typing it 1:1 keeps it easy to double-check.
- A definite dupe is blocked (built 2026-10-05): an entry matching one
  already logged (in the log files, or saved this session) in every
  column but COMMENT and the record ID: FREQ to the Hz, MODE, CALL, PARK,
  ST, SNT, RCD, PWR, DATE, TIME, and STATION_CALLSIGN. No two real
  contacts match like that, so it's the same paper line typed twice; a
  differing COMMENT most likely means a note to add to the one logged.
  - It's checked after the field rules and the sideband, before the
    unusual-CALL modal, and again after that modal (the call may be
    changed there).
  - A modal reads `Excluding COMMENT, attempted save` / `will result in
    a duplicate record.` / `See DATE & TIME to locate other record.` For
    an edit it goes on: `Change field value(s), or Esc out to` /
    `cancel.`, then, after a blank line, `WARNING:` / `Updated COMMENT
    will be lost after` / `escaping out.` (a new entry has nothing to
    cancel, and keeps what was typed). "Excluding COMMENT" makes clear
    that a different COMMENT with everything else the same isn't a
    different record. Its only button is `Roger Roger`; Enter or Esc
    closes it too. Nothing is saved, and the form is back as it was: a
    new entry as typed, or an edit still open with its changes. An
    edited entry isn't checked against itself.
  - Keeping a contact one minute apart from another (otherwise the same)
    is deliberate: rare, but real (a second try at a rare DX station
    after conditions improve, or to be sure one gets confirmed).
  - It replaced a possible-dupe warning (CALL, PARK, DATE, band, and
    voice/CW matching, as POTA counts that contact once), which meant
    little in practice.
  - At start, saved entries that are definite dupes of each other are
    marked `=` (see Log view), and counted beside the Quit button
    (`3 records are dupes, marked =`, or `= 3 dupes` when narrow; see
    Log view). A selected one lists its
    other copies below COMMENT, in the error color, under `Excluding
    COMMENT, duplicate record(s) exist:`: first any sharing its record ID
    (see Storage), then its dupes, one line per COMMENT, the same one
    first: `- Another record has same COMMENT.` (`- 2 other records have
    same COMMENT.`), `- Another record has COMMENT 'QSB'.`, or `- Another
    record without a COMMENT.`; last, `Edit field values (f3) or delete
    (f4) as makes sense.` No field gets the invalid border. Nothing is
    deleted automatically; deleting or editing one so it differs clears
    the other's mark. Refused rows aren't compared, as their values are
    text as found.
  - STATION_CALLSIGN is one of the columns compared. An entry the same
    as a logged one but for the station callsign can't come up: every
    record holds the one call (multiple calls are out of scope; see
    Scope).
- Warnings flag entries that are probably, but not certainly, wrong. The
  first Enter opens a warning modal instead of saving; Enter there
  confirms, and Esc goes back to the form without saving, on the field
  to fix. When several warnings apply, they come one after another. In
  any modal with two buttons (Back and Confirm, Try again, or Delete),
  Tab and Shift+Tab move between them, Back first (decided 2026-10-08);
  neither is highlighted at first, so Enter confirms until Tab picks one,
  and then presses the one highlighted. A one-button modal's button is
  for the mouse.
  - **Unusual CALL** (see CALL): reads `W11BC is an unusual callsign.` /
    `Correct and/or confirm with Enter.` and holds the call, ready to
    edit. Enter saves the entry with the call as it is in the modal (still
    shape-checked).
  - **Voice outside the voice range:** a voice signal runs outside its
    band's US voice (phone) range, using the Extra class edges (the
    widest): 80m 3.600, 40m 7.125, 20m 14.150, 17m 18.110, 15m 21.200, 12m
    24.930, 10m 28.300 MHz, each up to the top of the band. 30m has no
    voice range. A sideband takes 3 kHz beside the dial frequency: USB
    above it, LSB below, so 21.200 LSB and 21.450 USB warn while 21.200
    USB and 21.450 LSB don't. SSB is checked at the dial frequency only,
    since it's refused near edges. CW is fine anywhere. Esc goes back to
    FREQ.
  - **State on a non-US park:** PARK isn't a US park but ST is a US state.
    Blank is fine. Esc goes back to ST.
  - **Future date/time:** DATE plus TIME is later than the current UTC
    time. Esc goes back to DATE.

## Editing

- Selecting a log row: double-click a cell, or Enter on the highlighted
  cell (DataTable's stock select, for keyboard use: Tab into the log,
  arrow to a row, Enter). The whole row is then shown with the darker
  highlight of the focused cursor, kept while the form has focus. The
  form shows that entry's values, read-only (Textual's stock disabled
  fields, with no placeholders, since a hint in a dimmed field reads like
  a value), and focus stays in the log. Up and Down move the selection,
  and the form follows. Whatever the form held (an entry partly typed) is
  put aside. With no row selected, the log looks as before (the cell
  highlight, the divider over the first saved row).
- Once a row is selected, a single click on another row selects it
  (stock DataTable: with a row cursor, a click moves it). A habitual
  double-click there can select the wrong row: the first click selects,
  the form changes height when the two rows list different refused-row
  problems (or one lists none), the log shifts, and the second click lands
  on whatever row moved under it. Kept as stock (decided 2026-10-04):
  DataTable has no click-to-select option, and the alternatives (a
  single click that only highlights, select on the first click with a
  fixed space for the problem list, or the list over the log) each cost
  more than one click once selecting. Revisit if newer operators trip
  on it.
- `f3 Edit` edits the selected entry; with none selected it says
  `Double-click a record or press Enter when log area has focus first.`
  (The log's cell highlight is always there, so Enter only selects once
  Tab or Shift+Tab has moved focus to the log.) Any entry can be edited,
  this session's or saved.
- Its values show in the entry form as they'd be typed (FREQ
  `14.285.500`, PARK `US-1234`, PWR `0.5`, DATE `260925`, TIME `1953`),
  focus goes to FREQ, and the form's top border reads `Editing record -
  Esc to cancel` in the warning color. The border takes the row of the
  form's top margin, so nothing on screen moves.
- While editing, the form has focus: the log can't take it (so Tab stays
  in the form), and its highlight stays on the entry being edited, even
  if another row is clicked. The log still scrolls with the mouse wheel,
  to read other entries.
- Enter saves the change through every check and warning a new entry
  gets, except that the entry isn't checked against itself (an
  unchanged entry is no dupe). If, once each field reads (so `7.03` is
  `7.030.000`), nothing changed, Enter just goes back to the row
  selected, as Esc does (decided 2026-10-08): no dupe block or warning,
  nothing written, and no `✎` mark (one already there stays). A field
  that doesn't read is still refused first. A refused row (`!`) always
  saves, changed or not, as saving is what fixes it.
- Esc steps back one level at a time: from editing to the row still
  selected (changes dropped, no prompt; focus back in the log), then to
  no row selected, with the form's entry put aside back, and focus on the
  field last typed in.
- A saved edit stays on its row, selected, and keeps its place in the log
  until the next start, even if DATE or TIME changed. A saved entry
  (from the log files at start) is marked `✎` once edited; this
  session's entries keep their `•`. It keeps the station callsign it was logged
  with.
- In its file, only its row changes; every other line stays exactly as
  it was (refused rows, and a spreadsheet's `\r\n` endings or byte-order
  mark, included). The file is written to a temporary file that's then
  swapped in, so a crash can't leave it half-written. A changed DATE
  moves the entry to that date's file: it's added there first, then
  removed from the old one, so a crash in between leaves a dupe rather
  than losing it.
- A COMMENT longer than the field takes (from a file) is kept whole: it
  can be shortened, but nothing can be added to it.
- `f4 Delete` deletes the selected entry (with none selected it says the
  same as `f3`), editing or not: the edit goes with it. A confirm modal
  names it (`Delete this record?`, then e.g. `K1BBB on 7.030.000 CW`,
  `2026.09.25 19:00 UTC`, `Gone is gone: there's no undo.`) and takes
  Enter (or its Delete button) twice, so a quick delete still works but
  one stray Enter doesn't: its last line reads `Enter twice to delete,
  or Esc to keep it.`, then `Enter again to delete, or Esc to keep it.`
  Esc (or Back) keeps it, still selected. Gone is gone: no trash file
  or undo; backups are the operator's (e.g. a scheduled backup, or git
  in `data/`). Only its row leaves its file, as with a change, and a
  failed write gets the same modal. Afterwards nothing is selected, and
  the form is ready for a new entry, with what it held before put back.

## Log view

- Entries typed this session are shown at the top, in the order they were
  entered, even when their times are out of order, so they can be checked
  line by line against the paper log. Each new one goes below the last,
  and the log scrolls to keep it in view. It's highlighted, not selected,
  so the form stays ready for the next entry; Tab into the log and Enter
  selects it (see Editing).
- The log's first column, with no header, holds a one-character status
  marker. `•` marks entries typed this session, `✎` saved entries edited
  this session, `!` rows refused on load, `U` saved entries that share
  their record ID with another (see Storage), and `=` saved entries that
  are definite dupes of another (see Entry behavior). One mark per row:
  `!` first, then `U`, then `=`, then `✎`. Marks aren't saved: `•` and
  `✎` are gone on the next start, while `!`, `U`, and `=` come back
  until fixed. The column moves with its row when the log is sorted, so the
  marks survive a Sort. Later it may show other states, like an entry
  not yet uploaded to QRZ.
- Rows marked `!`, `U`, or `=` are counted to the left of the Quit
  button, in the error color, one line per mark in that order, and only
  while there are any: `1 record refused, marked !`, `4 records share a
  record ID, marked U`, `3 records are dupes, marked =` (`1 record
  shares a record ID, marked U`, `1 record is a dupe, marked =`: a lone
  `U` or `=` is left when its copy has a mark that comes first). Terse,
  as diagnostic status lines: no hint to select a row, no period. When
  any line doesn't fit (in a window narrower than about 56 columns), all
  three take a short form: `! 1 refused`, `U 4 share an ID`, `= 3
  dupes`. The
  counts follow the log as rows are fixed or deleted, and a line goes
  once its count is 0. (Decided 2026-10-05; they were notifications at
  start, which went after 30 seconds and could cover each other.)
- Below them, any rows refused on load, marked `!` (see Storage), then
  the saved entries (from the log files at start), newest first by UTC
  timestamp (DATE, then TIME). Entries with the same
  timestamp keep their file order. On the next start, this session's
  entries are sorted in with the rest.
- A thin divider separates this session's entries, as typed, from the
  sorted saved ones below: the first saved row is overlined across the
  whole row, so the line sits on the cell edge between the two rows (an
  underline sat partway up a highlighted row, at the font's underline
  position). There's none until an entry is typed, or when nothing is
  saved yet. A terminal without overline support shows no divider, rather
  than something that looks like a glitch. The divider goes away on
  sorting (nothing is in typed order any more), while the `•` marks stay,
  and comes back with the next entry typed.
- Every value is shown as entered, brackets included (e.g. a COMMENT of
  `RSGB [bold]Field[/bold] Day`); nothing in a cell is read as styling.
- **Sort** (decided 2026-10-07) orders the log by a column: `f5 Sort`
  sorts by the column the log's cell cursor is in (it's always shown,
  even while the form has focus), and a click on a column header sorts
  by that one, for the mouse (DataTable's stock header click, which does
  nothing on its own). Both work only with the cell cursor, while no row
  is selected (nor editing): a selected row's highlight covers the whole
  row, so there's no column to sort by (`f5 Sort` is dimmed in the
  footer then; decided 2026-10-07). The first sort by a column is ascending (A to Z,
  low to high, oldest first); sorting by it again reverses it, and
  another column starts ascending again. The sorted column's header
  shows `▲` (ascending) or `▼` (descending) after its name, or in the
  cell's right padding when the column has no room for a space and the
  arrow (`ST▲`). Values are compared as values, not as shown: FREQ, PWR,
  DATE, and TIME as numbers, dates, and times (7 MHz before 14 MHz),
  text ignoring case. Entries alike in the column go by timestamp
  (oldest first ascending, newest first descending).
- DATE and TIME (decided 2026-10-07, keep as is): DATE sorts by the full
  timestamp, date and then time of day, so DATE descending is the
  usual newest-first order, the way back to it after other sorts (apart
  from refused rows, still on top, and this session's entries, now
  sorted in). TIME sorts by time of day alone, across dates, then by
  date: ascending, 0100 on 2026.09.24, 0100 on 2026.09.25, then 2300 on
  2026.09.24, 2300 on 2026.09.25. Entries with the same timestamp keep
  the order they had. The marker column has no
  header and doesn't sort: `f5` with the cursor there does nothing.
- A Sort takes in every entry, this session's included (their typed
  order is lost, as after a restart; they keep their `•`). Entries typed
  after it go above the sorted ones, as typed, with the divider back, so
  what was just typed is always in view; the next Sort takes them in
  too. Rows refused on load stay at the top, in file order, whatever the
  sort, as their values may not read. The cursor goes to the top of the
  sorted column. An edit saved after a sort keeps its place, as always. The
  cursor keeps its column when an entry is saved or deleted, so `f5`
  right after typing sorts by the same column again. The sort lasts until
  the app is closed; the next start shows the usual order.

## Storage

- CSV files only. No SQLite.
- Stored in a `data/` folder under the project.
- One CSV file per UTC date, named `YYYYMMDD.csv` (e.g. `data/20260924.csv`).
- `data/` is ignored by git, so logs stay out of the code history.
- Column names use the same shorthand and order as the log table (see
  Entry fields):
  `FREQ, MODE, CALL, PARK, ST, SNT, RCD, PWR, DATE, TIME, COMMENT`, then
  `STATION_CALLSIGN` and `UUIDv4` (the record ID).
- Record IDs (built 2026-10-05). Each row's `UUIDv4` is a random UUID
  (version 4), written lowercase with hyphens
  (`1b4e28ba-2fa1-4d2b-883f-0016d3cca427`), that never changes, so the
  app can tell one record saved twice from two contacts that look alike.
  A new entry gets a fresh one when saved; an edit, a DATE move included,
  keeps it. It's never shown in the log or the form.
  - Why: an edit that changes DATE is two writes (added to the new
    date's file, then removed from the old one). If the second write
    fails and the operator gives up, or the app dies between the two,
    both files hold the entry, its before and after differing in DATE,
    which no dupe check would catch; with the ID, both are marked `U`.
  - Adding a row is skipped when that exact row, ID included, is already
    in its file, so saving an edit again after a failed move can't add it
    twice. If the edit was changed before saving again, both versions
    are kept (and marked `U` at the next start), rather than one dropped
    where the log doesn't show it.
  - At start, saved entries sharing an ID are marked `U`, and counted
    beside the Quit button (`4 records share a record ID, marked U`,
    or `U 4 share an ID`; see Log view). A
    selected one lists the other copies
    below COMMENT, in the error color, under `Excluding COMMENT,
    duplicate record(s) exist:`, at the top of that list (any definite
    dupes follow; see Entry behavior), one line each: `- Same UUIDv4 in
    20260925.csv, also same in every column.` (a row copied, a file
    merged twice) or `- Same UUIDv4 in 20260926.csv, with a different
    DATE and TIME.` (an unfinished move, or two versions of one record);
    either way it's a form of duplicate, so the heading stays. Then `Edit
    field values (f3) or delete (f4) as makes sense.` No field gets the
    invalid border:
    either copy may be the right one. Which to keep is the operator's
    call; nothing is resolved automatically. Deleting a copy clears the
    other's mark. A refused row sharing an ID keeps its `!`, and lists
    the copies under its problems.
  - A blank ID (a row added by hand) is filled in with a new one at
    start, refused rows included, and the file rewritten: the ID goes at
    the end of the row's last line (where a blank ID, written as nothing
    or `""`, sits, as the last column), and every other byte of the file
    stays as it was (unless the row's values are fixed on load too; see
    Storage). An ID can't be fixed in the app (it has no field) and is
    tedious and error-prone to make by hand. If the file
    can't be written, the app blocks at start until it's fixed (`Couldn't
    write to file or directory.` / `Check permissions.`; see the file
    errors block in Storage), listing it in `file_errors.txt` (`<file>:
    couldn't save changes made on load: Permission denied. Check
    permissions.`); the changes are made again at the next start.
  - An ID that isn't blank must be a UUID as the app writes it, or the
    row is refused (`UUIDv4 'abc' should be a UUID as the app writes it,
    like 1b4e28ba-2fa1-4d2b-883f-0016d3cca427. Saving gives it a new
    one.`): fixed in the app, it gets a new ID. A typo that still leaves a
    valid UUID makes the row look like a new record; that isn't caught.
  - Uppercase is read as the same ID, as the UUID standard (RFC 9562)
    reads it, though it writes lowercase; macOS's `uuidgen` writes
    uppercase, so a hand-added row may have one. It's made lowercase on
    load, like any value's case (see Storage), so it matches a lowercase
    copy of itself for the `U` mark. Other
    forms Python reads as a UUID (no hyphens, braces, `urn:uuid:`) are
    refused as not an ID.
  - No upgrade of existing files: before the first release, `data/` is
    cleared as needed.
  - Considered instead: a journal file noting each move until it's done
    (repairs on its own at start, but a second file and more startup
    logic); one file per year (a move is one write, but gives up daily
    files); and a possible-dupe warning across nearby dates (false
    alarms on real contacts alike in every field). UUID version 7 or a
    ULID would sort by when the entry was typed, which means little for
    entries copied from paper later. Version 4's 122 random bits make
    a chance collision negligible, even across merged files.
- Values are stored in their "Stored as" form, e.g. FREQ `14074500`,
  PARK `US-1234` or `JP-1234` (the full reference, whatever was typed),
  PWR `60` or `0.5`, DATE `20260925`, TIME `1953`.
- Dates and times are UTC everywhere, in both storage and entry. An entry's
  full timestamp is its DATE plus its TIME, and it's stored in the file named
  for its DATE.
- Files should stay readable and editable by hand.
- Each entry is added to its date's file when saved (Enter), and every
  log file is loaded at start. A new file starts with the header row.
- While it runs, the app is the only source of truth for the log files.
  It keeps each file's lines as loaded (refused rows and files with a
  wrong header included) and writes every save from that copy, the whole
  file through a temporary file swapped in. So a change made to a log
  file by another program while the app is open is overwritten, never
  merged, and an edit saves even if its row moved in the file. Other
  programs and scripts may read the files while the app runs; edits
  belong before or after. There's no checking for other programs' lock
  or swap files: on Linux an open file is rarely locked, so the app's
  write usually succeeds; if an editor or spreadsheet then saves over
  it, that's left to the operator.
- A file that isn't UTF-8 text isn't kept, so nothing is saved to it
  (`Couldn't save the entry: <file> isn't plain text (UTF-8), so it's
  left for a fix by hand`); the entry stays in the form.
- If a file can't be written, nothing changes and a modal says so:
  `Couldn't save to 20260925.csv:`, then for a permissions error
  `Permission Denied - Check file system permissions on file.`, or for
  anything else `Close all programs that have the file open. Changes
  made there will be lost, so copy them somewhere first if desired.
  Never edit a raw log during app use.`, and last `Enter to try again,
  or Esc to go back.` Esc leaves a new entry typed
  in the form, or an edit in edit mode. When an edit moves an entry to
  another date's file and only the old file fails, trying again finishes
  just that part; given up, both files hold it (a dupe, not a loss,
  marked `U` at the next start). Saving the edit again doesn't add it to
  the new date's file twice (see Record IDs).
- Written with `\n` line endings; a COMMENT with a comma or quote is
  quoted, CSV style (`"Nice, loud"`). If a hand edit left the last line
  without its line break, one is added before appending.
- Loading accepts what a spreadsheet may add when saving: a UTF-8
  byte-order mark, `\r\n` line endings, and blank lines.
- Operators (especially once the app is shared) may hand-edit the log
  files or `data/settings.toml`, so at start every data file is checked
  against the entry rules that refuse a value: one standard for all data
  files (see Settings for its file). Warnings are for the entry form
  only; a value from a file is taken as meant.
- If a hand edit breaks loading, show an error naming the offending file
  and row number: a wrong header row (the file is skipped), a file that
  isn't UTF-8 text (skipped), or a row that fails a check. Skipped rows
  and files stay in the file, to be fixed by hand.
- What the app can't show or write blocks it at start, until fixed by
  hand (decided 2026-10-05): a skipped row or file can't be seen in the
  log, so a contact in it is easily logged again, missed by the dupe
  check, and left out of an export. A modal with Quit as its only button
  (Enter, or ctrl+q) reads `Manual data correction required.` for rows or
  files that can't be read, `Couldn't write to file or directory.` /
  `Check permissions.` for record IDs that couldn't be written (both,
  when both), then `See <data folder>/file_errors.txt`, a blank line,
  and `Fix the files, then start the app again.` `file_errors.txt`, in
  `data/` beside the log files (and not read as one), has a header
  (`Written by pota-logger at start, 2026-10-05 21:03 UTC.` / `Fix these
  by hand, then start the app again.`, then a blank line), then one error
  per line, naming the file and row (`<file> row 4: has 14 values,
  should have 13`). It's rewritten at each start with errors, and
  removed at a start with none, so it never outlives them. If it can't
  be written either, the modal says `Couldn't write to file or
  directory.` / `Check permissions.` and ends `Fix the permissions, then
  start the app again.` instead. What the app can show (rows marked `!`,
  `U`, `=`) is fixed in the app instead, and the settings file's
  problems keep their own flow (see Settings).
- A row that fails a check but still splits into the right columns is
  refused, not skipped, and every problem in it is found (each column on
  its own; a check that depends on a column at fault is left out: SNT and
  RCD on MODE, the sideband on FREQ and MODE, the file on DATE). It shows
  in the log marked `!`, with its values as they are in the file. All
  refused rows sit at the top of the saved entries, in file order,
  whatever they were refused for (a DATE or TIME that doesn't read has
  no place in the sorted order, and at the top they're seen). Rather
  than a notification per row, they're counted beside the Quit
  button: `2 records refused, marked !` (`! 2 refused` when narrow; see
  Log view).
- A selected refused row lists its problems below COMMENT, in the error
  color, under `Refused from 20260925.csv row 4:`, one line each (`- TIME
  '53' should be HHMM, like 2123.`), and each field at fault gets
  Textual's stock invalid border (dimmed while read-only; it goes once
  the field is changed). The form grows by those lines, moving the log
  down, only while a refused row is selected. The list stays as found in
  the file while editing; Enter runs the entry checks as usual. A problem
  that saving fixes on its own says how: `Saving makes it US-1234.`
  whenever the entry form would take the value as shown there (a short
  form, or FREQ `14.250`, read as MHz), or `Saving moves it to 20260924.csv.` (a
  DATE in another date's file).
- The form shows a refused row's FREQ, PWR, and DATE as they'd be typed
  when they read (FREQ `7030000` as `7.030.000`), and every other value
  as it is in the file (TIME `53` stays `53`: it could be 00:53 or
  05:03). It's edited (`f3`) like any entry, through every entry check,
  and its save replaces its lines in its file (or moves it to its DATE's
  file); then it's marked `✎`, its list goes, and it joins the entries
  checked for dupes. Its STATION_CALLSIGN, which has no field in the
  form, is saved as the station callsign, which it is; one that
  doesn't read at all, or
  is another call, is listed with `Manually correct CSV log file.`
  (`- STATION_CALLSIGN 'W1XYZ' doesn't match the station callsign,
  W1TST. Manually correct CSV log file.`), and `f3` says so too. It can be deleted
  (`f4`) like any entry. A row too broken to split (wrong number of
  values, a stray quote) is skipped, and blocks the app at start until
  fixed by hand (see above).
- At start, the app fixes how a value is written, never what it means
  (decided 2026-10-07): spaces around a value, its case (`w1abc` as
  `W1ABC`, an uppercase record ID as lowercase), and a number written
  another way (FREQ `014285500`, PWR `.5` or `60.0`) are fixed in every
  row that splits into columns, refused or not, and that row's lines
  are rewritten, with no message. It's how a value is written, so
  nothing is lost or guessed. COMMENT, the operator's own note, is never
  changed. Anything that changes what's written stays as found, and the
  row is refused, to fix in the app: a short form the entry form takes
  (PARK `1234` as `US-1234`), FREQ `14.250` in MHz, or a DATE in
  another date's file. Filling in a blank record ID (see Record IDs) is
  the only other change the app makes to a log file on its own. (It
  used to refuse these too, and rewrite nothing, so automatic changes
  couldn't make a slip worse, e.g. a stray quote joining lines; a row
  too broken to split into columns is still left as it is.)
- Otherwise a hand edit is held to the strictest rule: every value must
  be written as the app writes it. `data/settings.toml`'s call gets the
  same fixes (see Settings).
- A row's checks, stopping at the first problem: the number of values;
  each column in order for non-ASCII, then spaces before or after a
  COMMENT (`COMMENT 'Loud ' should have no spaces around it, like
  Loud`; spaces inside it are fine, and other columns' are fixed on
  load); a blank column other than ST or
  COMMENT (STATION_CALLSIGN included, as no entry is saved without one;
  a blank UUIDv4 is filled in first, see Record IDs);
  FREQ, PWR, and DATE as numbers (FREQ in Hz, DATE as YYYYMMDD in 2000
  to 2099, the years the entry form's YYMMDD takes, so an edit keeps the
  year; e.g. TIME `53`, as a spreadsheet may save `0053`, is refused
  rather than read as 05:03); each field's entry rules that refuse a
  value (FREQ in a band, MODE, CALL and STATION_CALLSIGN's shape, PARK,
  ST, SNT and RCD against MODE, PWR's range, TIME), and UUIDv4 as the
  app writes it, in either case; each value in its
  stored form, the "Stored as" column in Entry fields: any other form
  the entry form would take is refused (`PARK '1234' should be
  'US-1234' in a log file`, likewise PARK `US1234`); DATE matching the
  file's name (`DATE '20260924' should match the file name,
  20260925.csv`); then SSB near a voice edge. Entry warnings (unusual
  call and the rest) aren't checked: a saved entry was confirmed when
  entered, or edited by hand on purpose. Definite dupes aren't refused
  either, just marked `=` (see Entry behavior). COMMENT's length
  isn't checked either: the entry form's limit (100 characters today) is
  just what fits in view, not a rule about the data (ADIF sets no
  limit), and it moves whenever the form's width does. If the field were
  later narrowed to, say, 80, every saved 100-character COMMENT would be
  refused on load; widened, nothing breaks either way. So any length
  loads.
- Other files in `data/` (anything not named `YYYYMMDD.csv`) are ignored.

## Export

- ADIF, aimed at QRZ.com import (and other logging programs, like
  KLog). Settled or known so far:
  - COMMENT exports as ADIF `COMMENT`, not `NOTES` (what QRZ shows as
    Comments).
  - PARK is already a full ADIF POTA reference. It exports as
    `POTA_REF` and as `SIG` (`POTA`) with `SIG_INFO` (the reference),
    all three (decided 2026-10-09): QRZ.com's ADIF export says ADIF
    3.1.1, from before `POTA_REF` (3.1.4), and records in the
    operator's QRZ log from other programs carry `SIG`/`SIG_INFO`;
    `POTA_REF` is for programs on the current standard. ADIF's
    `POTA_REF` takes a comma list of parks; `SIG_INFO` is a plain
    string, by convention one park.
  - Exports a date range (decided 2026-10-08), not the whole log. It
    defaults to the dates of this session's entries (from the earliest
    to the latest, if they span several), or, with none this session,
    the most recent DATE logged (from and to the same date). The
    operator can change the range.
  - Export is refused while the log isn't clean (decided 2026-10-08):
    any row marked `!`, `U`, or `=` must be resolved first, even when
    it falls outside the range. A problem is easy to fix locally, but
    once in QRZ.com or another log it has to be fixed there too, and
    the two logs kept in agreement.
  - Tracking which records were exported isn't planned for ADIF; it
    belongs with QRZ.com API integration (see QRZ.com API below).
  - Open (operator mulling it over): `f6` likely opens an export modal
    (range, then export), and the Export button may replace the big
    Settings button beside Quit, since Settings is rarely changed after
    setup and stays on `f2`. Where the file goes and its name are also
    still open.
  - MODE `USB`/`LSB` export as `MODE` SSB with `SUBMODE` USB/LSB (ADIF
    lists them as submodes of SSB); `SSB` and `CW` are modes.
  - A blank ST means no state: `STATE` is left out.
  - ST exports as `STATE` when filled (decided 2026-10-09): the park's
    state, as the POTA site lists it with the spot (and later the parks
    list), which is ADIF's meaning (the contacted station's location).
    Several of the operator's QRZ records show the activator's home
    state, from a callsign lookup (by the logging program that uploaded
    them, or QRZ's own; not recorded), where the park is in another.
    Whether QRZ fills a blank `STATE`, or county (`CNTY`), grid, and QTH
    beside a sent one, on ADIF import or by API is unknown: a US POTA
    record uploaded with no state (2024) has none on QRZ, nor
    a name, QTH, or county; editing and saving a record on QRZ's site
    may fill them. Telling a POTA contact from the activator's home
    address is left to QRZ.
  - PWR is the operator's power: `TX_PWR` in watts.
  - The station callsign is `STATION_CALLSIGN`.
  - Two contacts a minute apart, otherwise the same, stay separate on
    QRZ.com: its import report defines a dupe as the same CALL, BAND,
    MODE, and DATE with TIME_ON the same to the minute. Its docs page
    says within 30 minutes instead, unconfirmed: the operator's QRZ log
    holds same-call, band, and mode FT8 contacts 2 to 11 minutes apart
    (uploaded by API or ADIF file, which isn't recorded). An incoming
    dupe replaces an unconfirmed record and is ignored for a confirmed
    one.
  - So re-exporting an edited entry replaces its QRZ.com record only
    if CALL, BAND, MODE, DATE, and TIME are unchanged and the record
    isn't confirmed; otherwise QRZ keeps the old record (beside a new
    one, if those changed). A candidate for README.md's Noted issues,
    and a reason for tracking with the API (see QRZ.com API).
  - QRZ.com refuses a record whose CALL it can't place in a DXCC entity
    (tried 2026-10-09 with `Q1TST`: "DXCC could not be determined"), so
    test records need real-looking calls. It stores every field it's
    sent, even ones it doesn't use ("Lossless ADIF"), and gives them back
    on export. Records must fall inside the QRZ logbook's date range,
    and `STATION_CALLSIGN` must match the logbook's call.
  - The record ID (`UUIDv4`) isn't exported. If ADIF import ever needs
    to match records already logged, it would go in an
    `APP_<PROGRAM>_<FIELD>` field, ADIF's place for a program's own data.
    QRZ.com would keep it (Lossless ADIF).
- QRZ.com API (notes for the possible stage after ADIF export, from
  QRZ's Logbook API page, 2026-10-09): INSERT takes one QSO as an ADIF
  record, so the ADIF record module serves both. INSERT fails on a dupe
  unless `OPTION=REPLACE`, which overwrites even a confirmed QSO. It
  returns QRZ's `LOGID`, and DELETE takes LOGIDs, so keeping each
  record's LOGID would let edits and deletes reach QRZ (the tracking
  left out of ADIF export). FETCH filters by date range, call, and
  changed-since. Needs the operator's subscription (the operator has
  one), the logbook's API key (a secret: kept in settings, never shown
  or logged), and a user agent like `AppName/version`; QRZ publishes no
  rate limits. No sandbox was found: QRZ's API Checker page
  (logbook.qrz.com/apicheck) works on a real logbook, so testing by hand
  would use a separate logbook under the operator's call with a suffix
  never used on air (a suffix makes a new call, with its own logbook,
  key, and date range; a same-call logbook can't overlap dates), kept
  out of awards. App tests fake QRZ's responses.
- POTA's parks list (decided 2026-10-09, after ADIF export and possibly
  the API): `all_parks_ext.csv` from pota.app (about 96,000 parks, 9
  MB; columns reference, name, active, entityId (DXCC), locationDesc,
  latitude, longitude, grid), kept in `data/pota/`. Optional: offered
  as a download at first-time setup, with a way to download a fresh
  copy later; the app works fully without it and only does more with
  it: fill ST for a park in one state, warn when ST isn't one of the
  park's (`locationDesc` can list several: `US-DC,US-MD,US-WV`), show
  the park's name, warn on a park not in the list (it may be new, so
  never a block), and give the export a DXCC number. It would be the
  app's only network use, made only when the operator chooses.
  - It's served from Amazon S3 through CloudFront and seems rebuilt
    nightly (no schedule is published). A download is the whole list as
    it stands. Save the server's `ETag` and `Last-Modified` with the
    copy, and refresh with a conditional request (`If-None-Match`), so
    an unchanged list comes back as a small "not modified" reply, which
    keeps load and bandwidth down for POTA's volunteers; show the
    copy's date beside the refresh. The `ETag` is the file's MD5 (it
    matched a download on 2026-10-09), so it changes only with the
    content, and checking the copy's MD5 against it catches a damaged
    or hand-edited copy (then download afresh). Deleting the copy drops
    the saved `ETag` too. A forced full download costs POTA well under a
    cent, so it's fine to offer.
  - POTA's per-park API (`api.pota.app/park/US-1048`, JSON with the same
    fields) is unofficial and undocumented, so the list is preferred.
