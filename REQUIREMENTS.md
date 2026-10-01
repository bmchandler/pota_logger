# POTA Logger T3 — Requirements

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
storage (see Storage), with each log row checked at start against the
entry rules that refuse a value; the status bar; the settings
modal, with the station callsign checked like CALL; a light
outdoors color theme (leaf and grass greens with orange warnings, in
theme.py); the footer keys and terminal size; sideways scrolling of the
form in a narrow window. The visual layout is settled; wording tweaks
can still come up as they're noticed.

To do:

- Hand-test loading after editing a log file by hand (in Vim or ST4, and
  after a spreadsheet save): a fixed row loads, a broken row is skipped
  with a notification naming the file and row. Tried so far: a comma at
  the start of a line, a wrong TIME, and an extra header column were
  reported; MODE, ST, SNT, RCD, and PWR against their rules were not,
  and now are (still to re-test by hand, along with COMMENT).
- Log rows must hold the stored form: a value the entry form would
  accept in a short form is refused in a file, with an error. E.g. PARK
  `1234` is refused (only `US-1234` or `JP-1234` style loads); the bare
  number is for the entry form only. Today it loads as `US-1234`. The
  same goes for every other short form, e.g. a lowercase CALL, ST, or
  MODE (`w1abc`, `nj`, `usb`) is refused rather than loaded uppercase.
- No entry can be saved without a station callsign set. Since the
  start, entries could be saved with none set (the status bar shows
  `NOCALL` and the row's STATION_CALLSIGN is blank); that was never
  intended. On Enter with no station callsign set, the usual warning
  modal (used here as a block) says "A transmitting station callsign is
  required. Press Enter to go to Settings", with no way to save anyway
  and no Esc: Enter opens the settings modal, and the entry stays in the
  form. The call is also required on first run: the app opens on that
  modal when none is set, and when Settings is left with the call
  cleared (or cancelled with none set), it goes back to the modal, then
  Settings again. Ctrl+Q quits from anywhere (stock Textual, and works
  in any modal), for an operator not ready to set it yet. Ctrl+C stays
  stock (it doesn't quit). Once it's built,
  a blank STATION_CALLSIGN in a log row is refused on load too (today
  it's allowed, for rows saved before a call was set).
- The station callsign in `data/settings.toml` is checked at start with
  CALL's shape rules and messages, as the settings modal already does,
  and a bad one is reported naming the file (item 1 in the plan below).
- A log row whose DATE doesn't match its file's name (`YYYYMMDD.csv`) is
  refused on load, with an error naming the file and row.
- SNT and RCD placeholders follow MODE, as a hint: `599` while MODE is
  `CW` (any case), back to `59` for any other MODE (`SSB`, `USB`, `LSB`,
  or anything else typed). Only the placeholder changes, which shows only
  while the field is empty: a value already typed in SNT or RCD is never
  cleared or changed. The non-ASCII message's example (`59, or 599 on
  CW`) stays as is. Open when built: whether the placeholder updates as
  MODE is typed or when leaving MODE.

Not built yet, in the planned order:

1. Checking data files at start. Operators (especially once the app is
   shared) may hand-edit `data/settings.toml` or the log CSVs, so at
   start every file is checked against the same rules as entry, and the
   operator is notified of anything wrong, naming the file and line or
   row. One standard for all data files, extending the CSV rule in
   Storage. Only the entry rules that refuse a value apply: warnings are
   for the entry form only, and a value from a file is taken as meant.
   Done for log rows (see Storage). Still to do: the station callsign in
   `data/settings.toml`, where only invalid TOML is reported so far and
   a bad callsign loads as is. Comes before editing, so loading is a
   safety net for the rows editing rewrites.
2. Editing a saved entry. After storage, since its hard parts are storage
   ones: rewriting a CSV row, moving an entry to another date's file when
   DATE changes, and re-checking dupes against the saved log.

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
| SNT | `59` / `599` | Text | Same | Comes before RCD on purpose. Digits only. The digit count follows MODE: `CW` takes exactly 3 (`599`), other modes exactly 2 (`59`), in the entry form and on load alike. A 2-digit CW report is possible but rare, and with modern radios the tone digit is nearly always 9, so a missing third digit on CW is most likely a slip in copying: it's refused (`SNT '59' needs 3 digits on CW, like 599`) and the operator adds the digit (no auto-fill). An operator whose contact needs a 2-digit CW report to confirm on QRZ.com can sort that out there. Each digit must be in range (RST): readability 1–5, strength 1–9, tone 1–9, so `69` or `590` is refused. |
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
  Enter saves, Esc goes back to the settings modal. Blank is allowed, and
  shows as `NOCALL`.

## Settings

- A settings modal holds app-wide settings, starting with the station
  callsign. Future settings go there too.
- Settings are saved in `data/settings.toml`.

## Theme and keys

- The app always uses its own light outdoors theme; there's no theme
  switching.
- The footer shows `^q Quit`, `f2 Settings`, and `^s Screenshot` (saves
  an SVG of the screen to the Downloads folder).
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
    files, plus those saved this session. Esc goes back to CALL.
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

## Log view

- Entries typed this session are shown at the top, in the order they were
  entered, even when their times are out of order, so they can be checked
  line by line against the paper log. Each new one goes below the last,
  and the log scrolls to keep it in view.
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
- If a hand edit breaks loading, show an error naming the offending file and
  row number (see "Checking data files at start" in Status and plan): a
  wrong header row (the file is skipped), a file that isn't UTF-8 text
  (skipped), or a row that fails a check (the row is skipped). Skipped
  rows stay in the file, to be fixed by hand.
- A row's checks, stopping at the first problem: the number of values;
  non-ASCII in any column; a blank column other than ST, COMMENT, or
  STATION_CALLSIGN; FREQ, PWR, and DATE in their stored form (FREQ in Hz,
  DATE as YYYYMMDD; e.g. TIME `53`, as a spreadsheet may save `0053`, is
  refused rather than read as 05:03); then each field's entry rules that
  refuse a value (FREQ in a band, MODE, CALL and STATION_CALLSIGN's shape,
  PARK, ST, SNT and RCD against MODE, PWR's range, TIME, and SSB near a
  voice edge). Entry warnings (unusual call, possible dupe, and the rest)
  aren't checked: a saved entry was confirmed when entered, or edited by
  hand on purpose.
- A value the entry form would accept in another form loads as that
  field's stored form, as entry would store it: e.g. PARK `1234` loads
  as `US-1234`, a lowercase call as uppercase. The file isn't changed.
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
