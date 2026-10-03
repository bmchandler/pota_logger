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

Future (not now):

- QRZ.com API integration.

## Status and plan

Built: the entry form with every planned field (COMMENT included), its
field rules, blocks, and warnings, all fitting ADIF (see Entry behavior);
the log table (this session's entries as typed, marked `•`, above the
saved ones newest first, with a divider between; see Log view); CSV
storage (see Storage), with each log row and the settings file's
station callsign checked at start against the entry rules that refuse a
value, each held to exactly what the app writes, and hand-tested in Vim
and LibreOffice Calc (see Storage and Settings); the status bar; the
settings modal, with the station callsign checked like CALL and
required before any entry is saved (see Session-level value); a light
outdoors color theme (leaf and grass greens with orange warnings, in
theme.py); the footer keys and terminal size; sideways scrolling of the
form in a narrow window; editing a logged entry in the form (see
Editing). The visual layout is settled; wording tweaks
can still come up as they're noticed.

To do:

- Later, with other visual tweaks: show notifications (errors and
  warnings) higher up, at the bottom right of the log area, above the
  Settings and Quit buttons. Their long stay is good, but stacked at the
  bottom right they cover the Settings button, and leave Quit clickable
  at the edge but unreadable, which could frustrate a newer operator.
  Textual's notifications sit in its ToastRack, which CSS can move
  (e.g. a bottom margin), a small override of stock looks.
- Decouple COMMENT's input limit from the log's view of it (decided
  2026-10-03). Today the limit is what fits in the field's view (100
  characters), and the log column is that same fixed width, so a longer
  COMMENT from a file is cut off. Instead, the log's COMMENT column
  widens to the longest COMMENT shown, so the operator always sees the
  whole of each one, whatever the entry limit is now or later (see
  Storage: any length loads). The input could also take a set cap (e.g.
  100, scrolling within the field if wider than its view). Log columns
  are fixed widths because DataTable doesn't redraw rows already drawn
  when a column widens; since the log is redrawn in full on each save,
  the width could be worked out from the entries at each redraw.
- After editing is built: replace the possible-dupe warning (see
  Warnings in Entry behavior) with a check for definite dupes only
  (decided 2026-10-03). In practice "possible dupe" means little. A
  definite dupe is an entry that matches another in every column but
  COMMENT. Nothing is ever deleted automatically to be "helpful"; how
  the operator is told and how a dupe is resolved (on entry, and among
  saved rows at start) are worked out once in-app editing exists, since
  editing is likely part of resolving one. Until then, the possible-dupe
  warning stays as it is.
- Speed up the test suite (assessed 2026-10-01: 541 tests in about 2
  minutes). The 428 unit tests take under 2 seconds; the 113 app tests
  (`run_test`) take the rest, about 1 second each, plus about 0.1 second
  per `pilot.press` key. No test is out of date; all match this file.
  Options, cheapest first:
  - Fewer keypresses: `test_comment_takes_only_what_fits_in_view` types
    103 keys (11 s); fill to near the limit, then type the last few.
    `test_typed_entry_with_tab_between_fields` and
    `test_rows_drawn_in_full_without_redraw` (7 to 9 s) type on purpose
    (key-by-key entry, and a redraw bug that needed it), so they stay.
  - Run tests in parallel with pytest-xdist (a new dev dependency;
    `pytest -n auto` on 8 cores should bring it under 30 seconds). Tests
    already use their own temp dirs, so they should run in parallel as is.
  - Find why each app start takes about 1 second (profile one
    `run_test`); a fixed cost there is paid 113 times.
  - Fewer app tests where a unit test covers the same rule: each field's
    "blocks entry" test repeats its parser's messages, while the blocking
    itself (notification, focus, nothing saved) is one shared loop in
    `on_input_submitted`. A few could check that path, with the messages
    left to the unit tests. Less end-to-end coverage, so the operator
    decides.

Not built yet, in the planned order:

1. Fixing a refused log row in the app (decided 2026-10-03), building on
   Editing. Today a row refused on load (spaces around a value included)
   stays skipped until fixed by hand, and the app never tidies or
   rewrites a log file on its own, since automatic changes to a
   hand-edited file could make a slip worse (e.g. a stray quote that
   joins lines). Instead, a refused row that still splits into the right
   columns loads as far as it can, ready to fix in the entry form like
   any edit, so the operator needn't open the CSV. A row too broken to
   split (wrong number of values, a stray quote) is still fixed by hand.
   How such a row is shown in the log is decided then.

Also not built: the Sort action (see Log view) and ADIF export.

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
- A limit on digits in a callsign. ADIF sets none, and special-event
  calls use years and anniversaries (`W100AW`); the unusual-callsign
  warning covers typos like `W111111AB`.

## Entry fields

In entry order (mirrors the paper log). All times and dates are UTC.

| Field | Entered as | Stored as | Displayed as | Notes |
|---|---|---|---|---|
| FREQ | Always MHz, shorthand allowed: `14`, `14.1`, `14.0745`, `14.074.5`, `14074`, `28312456` | Integer Hz | Always in full: `14.000.000`, `14.074.500` | Never carried forward. Missing digits are filled with zeros. After a dot, up to 6 fractional MHz digits, optionally with a second dot after the 3 kHz digits (`14.1` is `14.100.000`; `14.0745` and `14.074.5` are `14.074.500`). Bare digits are the same with the dot left out; the MHz part is whichever of 1 or 2 leading digits lands in a band (`141501` is `14.150.100`, `3985` is `3.985.000`). Across 80m to 10m only one reading ever fits. Must be inside a US amateur band from 80m to 10m. |
| MODE | `SSB`, `USB`, `LSB`, or `CW`, any case | Uppercase text | Same | Defaults to `SSB` on each new entry. Typed, with no drop-down, auto-complete, or single-letter shortcuts; Tab just moves to the next field. `SSB` means the standard sideband (LSB below 10 MHz, USB above) and is what's logged away from voice edges. `USB`/`LSB` are logged near a voice edge, to record which side of the dial the signal was on. SSB with FREQ (the dial frequency) at a voice range edge or less than 3 kHz inside it is refused: log USB or LSB there. |
| CALL | Any case, e.g. `w1abc`, `VE3/w1abc/p` | Uppercase text | Same | International and slash calls allowed. Shape check only: letters, digits, and up to two `/`, no empty parts, and at least one part shaped like a call (prefix, a digit, then a suffix ending in a letter). Prefixes aren't checked against a country table, so special-event calls like `GB250RSGB` still work. Warns (see Entry behavior) when no part is in ITU's normal form: a prefix, one digit, then 1–4 letters. The prefix is 1 letter only for countries holding a whole letter (`B`, `F`, `G`, `I`, `K`, `M`, `N`, `R`, `W`), which may also use 2 letters; otherwise it's 2 characters, possibly with a digit (`VE`, `9A`, `3D`). So `W11BC` and `W100AW` warn. |
| PARK | `1234`, `464`, `JP1234`, `JP-1234`, `4X-12`, `US-4566@US-WY`, any case | POTA reference: `US-1234`, `US-0464`, `JP-1234`, `4X-0012`, `US-4566@US-WY` | Same | One park per entry. Must fit ADIF's POTA reference: PROGRAM-NUMBER, optionally @LOCATION. The program is 1 to 4 letters and digits with at least one letter; a bare number means a US park (`US`). The dash may be left out when the program ends in a letter (`jp234`). The number is 4 or 5 digits; shorter numbers get leading zeros (`464` is `US-0464`), so `4640` must be typed in full. LOCATION is a 4 to 6 character ISO 3166-2 code (`US-WY`), only for parks spanning more than one, like trails. Anything else is refused; a number over 5 digits gets its own message (`parks must be <= 5 digits`), since the rest of its shape is right. The field stays 8 characters wide, sized for common references, and scrolls up to ADIF's longest reference (17 characters); the log column is 17 wide. |
| ST | `NJ`, `NA`, or blank | Uppercase text | Same | State the park is in. Optional, even for US parks, since it isn't always clear at entry time. If given, must be a US state code (50 states plus DC) or `NA`. Not checked against the park; no park database is kept. |
| SNT | `59` / `599` | Text | Same | Comes before RCD on purpose. Digits only. The digit count follows MODE: `CW` takes exactly 3 (`599`), other modes exactly 2 (`59`), in the entry form and on load alike. A 2-digit CW report is possible but rare, and with modern radios the tone digit is nearly always 9, so a missing third digit on CW is most likely a slip in copying: it's refused (`SNT '59' needs 3 digits on CW, like 599`) and the operator adds the digit (no auto-fill). An operator whose contact needs a 2-digit CW report to confirm on QRZ.com can sort that out there. The placeholder follows MODE as a hint: `599` while MODE is `CW` (any case), `59` for any other MODE typed. It updates when leaving MODE (Tab, Shift+Tab, or a click), not on each keystroke, and goes back to `59` after a save, since MODE resets to `SSB`. Only the placeholder changes, which shows only while the field is empty: a value already typed is never cleared or changed. The non-ASCII message's example (`59, or 599 on CW`) stays as is. Each digit must be in range (RST): readability 1–5, strength 1–9, tone 1–9, so `69` or `590` is refused. |
| RCD | `59` / `599` | Text | Same | Same rules as SNT. |
| PWR | Watts as a number: `60`, `2.5`, `.5` | Decimal watts | `60W`, `2.5W`, `.5W` | Carried forward. 0.1 to 1500 watts (US legal limit). No `W` when typing. |
| DATE | `260925` (YYMMDD, years 2000–2099) | Part of the entry's UTC timestamp (`20260925` in CSV) | `2026.09.25` | Carried forward. Must be a real calendar date. Still a UTC date; only the *default* on app start is today's local date (not UTC), since the app is usually opened right after a session and the first entries typed often predate a UTC midnight rollover that's already happened locally. |
| TIME | `1953` (24-hour HHMM) | Part of the entry's UTC timestamp (`1953` in CSV) | `19:53` | Last in the top row of the form. Must be a real time, 0000 to 2359. |
| COMMENT | Free text, e.g. `POTA US-1234 NC`, `RSGB Field Day Serial #042` | Text, as entered | Same | Optional. On its own line below the other fields, as wide as that row, and takes only what fits there (currently 100 characters). Any plain ASCII character is allowed (see the non-ASCII rule in Entry behavior). Never filled in by the app from other fields, and never carried forward: it's the operator's own note, whose use changes over time. Its log column follows TIME at the same width; the log scrolls sideways to show it. Exported as ADIF `COMMENT` (what QRZ shows as Comments). |

Session-level value:

- **Station callsign:** the operator's own call. It's shown in a top status
  area and recorded on each entry (ADIF `STATION_CALLSIGN`). It's set in the
  settings modal.
  Same shape check as CALL (letters, digits, up to two `/`, shaped like a
  call), uppercased; saving anything else is refused and the modal stays
  open. An unusual call (same rule as CALL, e.g. `W11BC`, `W100AW`) opens
  the same unusual-callsign warning as CALL, where it can be corrected:
  Enter saves, Esc goes back to the settings modal.
- **Required:** no entry can be saved without a station callsign set.
  While none is set, the status bar shows `NOCALL` and the usual warning
  modal, used as a block, reads `A transmitting station callsign` / `is
  required.` / `Press Enter to go to Settings.`, with no way to save
  anyway, no Esc, and one button, Settings: Enter opens the settings
  modal. It shows when the app starts with none set (first run, or a
  `data/settings.toml` with none, a bad one, or invalid TOML), and when
  Settings is left with none: saved with the call cleared (the blank is
  saved) or cancelled with none set. From there, Enter opens Settings
  again; F2 does nothing while it's up. On Enter in the form with none
  set, it shows too, and the entry stays in the form (Settings always
  ends with a call set, so this is a safety net). Ctrl+Q quits from
  anywhere (stock Textual, and works in any modal), for an operator not
  ready to set it yet. Ctrl+C stays stock (it doesn't quit).

## Settings

- A settings modal holds app-wide settings, starting with the station
  callsign. Future settings go there too.
- Settings are saved in `data/settings.toml`.
- At start, the file is checked like the log files (see Storage).
  Invalid TOML is reported as `Couldn't read <file>:
  <error>`. The station callsign gets CALL's checks that refuse a value
  (plain ASCII, then its shape), with CALL's messages naming the
  `station_callsign` key: `<file>: station_callsign 'W1' doesn't look
  like a callsign, like W1ABC`. A hand edit is held to the strictest
  rule: the call must be exactly as the app saves it, so spaces around
  it (`station_callsign ' W1ABC ' should have no spaces, like W1ABC`)
  and lowercase (`station_callsign 'w1abc' should be uppercase, like
  W1ABC`) are refused, not tidied up on load. Either way the app
  starts with no call set, so the station-callsign block follows (see
  Session-level value). A refused call opens in Settings, ready to
  correct (most likely a slip, and the modal gets noticed where a
  notification may not); it's there again if Settings is cancelled,
  until a call is saved, which rewrites the file. Saving uppercases it,
  as usual. An unusual call (`W100AW`) loads without a warning: a value
  from a file is taken as meant. Only an empty call (`""`) means none is
  set yet; one of just spaces is refused too.

## Theme and keys

- The app always uses its own light outdoors theme; there's no theme
  switching.
- The footer shows `^q Quit`, `f2 Settings`, `f3 Edit` (see Editing),
  and `^s Screenshot` (saves an SVG of the screen to the Downloads
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
- Only DATE and PWR carry forward to the next entry. Everything else is
  entered fresh each time (MODE resets to `SSB`).
- Multi-park activations: each park is a separate entry.
- Entries may be typed in any time order, with no warning. The paper log
  isn't always in time order (an entry is sometimes finished after later
  ones), and typing it 1:1 keeps it easy to double-check.
- Warnings flag entries that are probably, but not certainly, wrong. The
  first Enter opens a warning modal instead of saving; Enter there
  confirms, and Esc goes back to the form without saving, on the field
  to fix. When several warnings apply, they come one after another.
  - **Unusual CALL** (see CALL): reads `W11BC is an unusual callsign.` /
    `Correct and/or confirm with Enter.` and holds the call, ready to
    edit. Enter saves the entry with the call as it is in the modal (still
    shape-checked).
  - **Possible dupe:** CALL, PARK, DATE, band, and mode type (voice or
    CW; SSB, USB, and LSB count as voice) all match an entry already
    logged, since POTA counts that contact once. Reads `Possible dupe:
    W1ABC at US-1234,` / `20m voice, already logged at 19:53.` ("dupe",
    the usual shorthand, not "duplicate"). Checks every entry in the log
    files, plus those saved this session. Esc goes back to CALL. To be
    replaced by a definite-dupe check after editing is built (see To do).
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
    Blank or `NA` is fine. Esc goes back to ST.
  - **Future date/time:** DATE plus TIME is later than the current UTC
    time. Esc goes back to DATE.

## Editing

- `f3 Edit` edits the entry highlighted in the log (reached with Tab and
  the arrow keys, or a click). Any entry can be edited, this session's or
  saved.
- Its values show in the entry form as they'd be typed (FREQ
  `14.285.500`, PARK `US-1234`, PWR `0.5`, DATE `260925`, TIME `1953`),
  and the form's top border reads `Editing record - Esc to cancel` in the
  warning color. The border takes the row of the form's top margin, so
  nothing on screen moves. Whatever the form held (an entry partly
  typed) is put aside.
- Enter saves the change through every check and warning a new entry
  gets, except that the entry isn't checked against itself (an unchanged
  entry is no possible dupe). Esc cancels. Either way, the form gets back
  what it held, and focus goes back where it was. `f3` on another row
  while editing switches to that one.
- The entry keeps its place in the log until the next start, even if
  DATE or TIME changed, and the highlight stays on it; this session's
  entries keep their `•`. It keeps the station callsign it was logged
  with.
- In its file, only its row changes; every other line stays exactly as
  it was (refused rows, and a spreadsheet's `\r\n` endings or byte-order
  mark, included). The file is written to a temporary file that's then
  swapped in, so a crash can't leave it half-written. A changed DATE
  moves the entry to that date's file: it's added there first, then
  removed from the old one, so a crash in between leaves a dupe rather
  than losing it.
- If its row isn't in its file as loaded (edited by hand while the app
  was open), nothing is saved: `Couldn't save the change: <file> no
  longer holds this entry as it was loaded`, and the form stays in edit
  mode, to cancel or try again after a restart.
- A COMMENT longer than the field takes (from a file) is kept whole: it
  can be shortened, but nothing can be added to it.

## Log view

- Entries typed this session are shown at the top, in the order they were
  entered, even when their times are out of order, so they can be checked
  line by line against the paper log. Each new one goes below the last,
  and the log scrolls to keep it in view. It's highlighted, so `f3` edits
  the entry just typed (see Editing).
- The log's first column, with no header, holds a one-character status
  marker. For now, `•` marks entries typed this session; it isn't saved,
  so it's gone on the next start. The column moves with its row when the
  log is sorted, so the marks survive a Sort. Later it may show other
  states, like an entry not yet uploaded to QRZ.
- Below them, the saved entries (from the log files at start) are shown
  newest first by UTC timestamp (DATE, then TIME). Entries with the same
  timestamp keep their file order. On the next start, this session's
  entries are sorted in with the rest.
- A thin divider separates this session's entries, as typed, from the
  sorted saved ones below: the first saved row is overlined across the
  whole row, so the line sits on the cell edge between the two rows (an
  underline sat partway up a highlighted row, at the font's underline
  position). There's none until an entry is typed, or when nothing is
  saved yet. A terminal without overline support shows no divider, rather
  than something that looks like a glitch. When the planned Sort is
  built, the divider goes away on sorting (nothing is in typed order any
  more), while the `•` marks stay.
- Every value is shown as entered, brackets included (e.g. a COMMENT of
  `RSGB [bold]Field[/bold] Day`); nothing in a cell is read as styling.
- A **Sort** action (planned) orders the log by any column when the
  operator asks for it. It sorts every entry, this session's included, so
  their typed order is lost, just as after a restart. How it's triggered
  and whether it toggles newest/oldest are decided when it's built.

## Storage

- CSV files only. No SQLite.
- Stored in a `data/` folder under the project.
- One CSV file per UTC date, named `YYYYMMDD.csv` (e.g. `data/20260924.csv`).
- `data/` is ignored by git, so logs stay out of the code history.
- Column names use the same shorthand and order as the entry fields:
  `FREQ, MODE, CALL, PARK, ST, SNT, RCD, PWR, DATE, TIME, COMMENT`, then
  `STATION_CALLSIGN`.
- Values are stored in their "Stored as" form, e.g. FREQ `14074500`,
  PARK `US-1234` or `JP-1234` (the full reference, whatever was typed),
  PWR `60` or `0.5`, DATE `20260925`, TIME `1953`.
- Dates and times are UTC everywhere, in both storage and entry. An entry's
  full timestamp is its DATE plus its TIME, and it's stored in the file named
  for its DATE.
- Files should stay readable and editable by hand.
- Each entry is appended to its date's file when saved (Enter), and every
  log file is loaded at start. A new file starts with the header row.
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
  isn't UTF-8 text (skipped), or a row that fails a check (the row is
  skipped). Skipped rows stay in the file, to be fixed by hand.
- A hand edit is held to the strictest rule: every value must be
  written exactly as the app writes it, so nothing is tidied up on load.
- A row's checks, stopping at the first problem: the number of values;
  each column in order for non-ASCII, then spaces before or after the
  value (`CALL ' W1ABC' should have no spaces around it, like W1ABC`;
  spaces inside a COMMENT are fine); a blank column other than ST or
  COMMENT (STATION_CALLSIGN included, as no entry is saved without one);
  FREQ, PWR, and DATE as numbers (FREQ in Hz, DATE as YYYYMMDD in 2000
  to 2099, the years the entry form's YYMMDD takes, so an edit keeps the
  year; e.g. TIME `53`, as a spreadsheet may save `0053`, is refused
  rather than read as 05:03); each field's entry rules that refuse a
  value (FREQ in a band, MODE, CALL and STATION_CALLSIGN's shape, PARK,
  ST, SNT and RCD against MODE, PWR's range, TIME); each value in its
  stored form, the "Stored as" column in Entry fields: lowercase is
  refused (`MODE 'usb' should be uppercase, like USB`), and so is any
  other form the entry form would take, or a number written another way
  (`PARK '1234' should be 'US-1234' in a log file`, likewise PARK
  `US1234`, PWR `.5` or `60.0`, FREQ `014285500`); DATE matching the
  file's name (`DATE '20260924' should match the file name,
  20260925.csv`); then SSB near a voice edge. Entry warnings (unusual
  call, possible dupe, and the rest) aren't checked: a saved entry was
  confirmed when entered, or edited by hand on purpose. COMMENT's length
  isn't checked either: the entry form's limit (100 characters today) is
  just what fits in view, not a rule about the data (ADIF sets no
  limit), and it moves whenever the form's width does. If the field were
  later narrowed to, say, 80, every saved 100-character COMMENT would be
  refused on load; widened, nothing breaks either way. So any length
  loads.
- Other files in `data/` (anything not named `YYYYMMDD.csv`) are ignored.

## Export

- ADIF, aimed at QRZ.com import. Field details (e.g. `SIG`/`SIG_INFO` vs
  `POTA_REF`, and station and operator fields) are worked out when export is
  built. Settled or known so far:
  - COMMENT exports as ADIF `COMMENT`, not `NOTES` (what QRZ shows as
    Comments).
  - PARK is already a full ADIF POTA reference, for `POTA_REF`.
  - MODE `USB`/`LSB` export as `MODE` SSB with `SUBMODE` USB/LSB (ADIF
    lists them as submodes of SSB); `SSB` and `CW` are modes.
  - ST `NA` means no state: `STATE` is left out.
  - PWR is the operator's power: `TX_PWR` in watts.
  - The station callsign is `STATION_CALLSIGN`.
