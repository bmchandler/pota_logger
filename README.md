# POTA Logger

A keyboard-first terminal logbook for **hunting** [Parks on the Air](https://docs.pota.app/)
contacts. It's built for copying a paper log into the computer quickly and
accurately: type each line as it's written, and the app checks it as you go.

The intended workflow is paper log → POTA Logger → ADIF export → QRZ.com import.

It runs in a terminal (built with [Textual](https://textual.textualize.io/)),
stores everything in plain CSV files you can open in a text editor or
spreadsheet, and needs no internet connection.

Scope: hunter contacts only (not activating), voice (SSB, USB, LSB) and CW, on
US amateur bands from 80m to 10m, WARC bands included.

## Features

### Fast entry

- One row of fields, those typed on every entry first: FREQ, CALL, PARK, ST,
  SNT, RCD, TIME, then PWR, DATE, and MODE (carried forward; MODE starts
  as `SSB`), with COMMENT on the line below. Tab moves between fields, and
  Enter saves. The log keeps paper-log order: FREQ, MODE, CALL, PARK, ST,
  SNT, RCD, PWR, DATE, TIME, COMMENT.
- Shorthand typing:
  - FREQ in MHz, with digits left out: `14.074.5`, `14.0745`, `14074`, and
    `141501` (read as 14.150.100) all work.
  - PARK as a bare number for US parks: `464` becomes `US-0464`, and `jp1234`
    becomes `JP-1234`.
  - DATE as `YYMMDD`, TIME as `HHMM`, and any case for MODE and CALL.
- PWR, DATE, and MODE carry over to the next entry. MODE starts as `SSB` when
  the app opens.
- DATE starts as today's local date, which suits typing up a session right
  after it's over. All dates and times are UTC.
- SNT and RCD hint `599` when MODE is CW, and `59` otherwise.

### Checks as you type

The app sorts mistakes into two kinds:

- **Blocked:** values that can't be right, such as a frequency outside a band,
  a report digit out of range, SSB at a voice-band edge (log USB or LSB there),
  anything ADIF doesn't allow, or non-ASCII characters. The field is focused,
  with a message saying what's wrong.
- **Warned:** values that are probably wrong but could be real, such as an
  unusual callsign, a voice signal outside the voice range, a state on a
  non-US park, or a time in the future. Enter saves anyway; Esc goes back to
  fix it. A real but odd contact copied from paper can always be saved.
  Tab moves between a modal's Back and Confirm buttons, and Enter then
  presses the one highlighted.

### Dupes

An entry that matches one already logged in every column except COMMENT is
blocked as a duplicate. No two real contacts match to the minute, frequency,
and reports, so it's the same paper line typed twice. To add a note to a
logged contact, edit that record's COMMENT.

### The log

- The log below the form shows this session's entries in the order typed,
  to check line by line against the paper. Saved entries follow, newest
  first.
- **F5** sorts the log by the column the cursor is in, or click a column
  header (not while a row is selected). The first sort is ascending;
  again reverses it. DATE sorts by date and time, so DATE twice gives
  the usual newest-first order; TIME sorts by time of day alone. Entries typed
  after a sort go on top, as typed. Refused (`!`) rows stay at the top.
  The next start shows the usual order.

### Export

- **F6** (or the ADIF button) opens Export, to write an ADIF file for
  QRZ.com's ADIF import. Set the folder first, in Settings (**F2**, which
  also works from Export). From and To are UTC dates, typed like DATE
  (YYMMDD); they start as this session's dates, or the latest date
  logged. Enter (or the Export button) writes
  `pota_<created>_<from>_<to>.adi` (UTC, e.g.
  `pota_20261009195312_20261009_20261009.adi`) there, the records in time
  order; Esc cancels.
- Export waits until no row is marked `!`, `U`, or `=`, anywhere in the
  log: fix or delete those first, so a mistake doesn't reach QRZ.com.
- Each record carries the park as `POTA_REF` and as `SIG`/`SIG_INFO`,
  and ST as `STATE` (left out when blank). The record ID isn't exported.
- The first column marks each row's status:

  | Mark | Meaning |
  |---|---|
  | `•` | Typed this session |
  | `✎` | Edited this session |
  | `!` | Refused when loading: a value doesn't follow the rules (select it to see why) |
  | `U` | Shares its record ID with another row: saved twice, or two versions of one record |
  | `=` | A duplicate of another saved row |

### Selecting, editing, and deleting

- Double-click a row, or Tab into the log and press Enter, to select it. The
  form shows it read-only.
- **F3** edits the selected record in the form. Enter saves it, through the
  same checks as a new entry. If nothing changed, Enter just steps back, as
  Esc does, and the record isn't marked edited.
- **F4** deletes it, after a confirmation that takes Enter twice. There is no
  undo.
- **Esc** steps back: from editing to selected, then to nothing selected,
  with what you were typing before put back.
- Refused (`!`), `U`, and `=` rows list what's wrong, or where the other
  copies are, below COMMENT. Fix them with edit or delete, without opening
  the files.

### Settings and keys

- At first start, Settings opens to set your station callsign. No entry
  can be saved until one is set, and every record stores it. A log holds
  one call: a row with another call is refused, to fix by hand. When your
  call changes, start a new log: move the old log files out of `data/`,
  then set the new call in `data/settings.toml`.
- **F2** opens Settings, with two checkboxes, both
  off at first, and a folder:
  - `New: Pre-populate COMMENT with POTA info.`: a new entry's COMMENT
    starts as `POTA `, and becomes `POTA US-1234 NJ` (or `POTA US-1234`
    with no state) as you leave PARK and ST. Anything you type after that
    is kept when PARK or ST change.
  - `Edit: Update COMMENT with POTA info.`: editing a record updates the
    same info, if its COMMENT starts with it.
  - `ADIF export folder`: where ADIF exports go, like `~/Downloads`. It
    must already exist: none is created, so a typo is caught.
- **Ctrl+S** saves a screenshot (SVG) to your Downloads folder.
- **Ctrl+Q** quits.

## Your data

Logs live in the `data/` folder, one CSV file per UTC date, named
`YYYYMMDD.csv` (for example `data/20261001.csv`). Settings are in
`data/settings.toml`. The folder is ignored by git, so your logs stay out of
the code history.

Every file is loaded and checked when the app starts. A row that breaks a
rule isn't silently fixed or dropped: it shows in the log marked `!`, to fix
or delete in the app. A row too broken to read (wrong number of columns, a
stray quote) is left in the file for you to fix by hand: the app won't
start until it's fixed, and lists each one, by file and row, in
`data/file_errors.txt`. A file the app can't write blocks it the same
way.

When the app starts, it changes a file on its own only to fix how a value
is written, never what it means: spaces around a value, its case (`w1abc`
as `W1ABC`), and a number written another way (`.5` as `0.5`). A COMMENT is
never changed. A row with a blank record ID also gets a new one. The call in
`data/settings.toml` gets the same fixes for spaces and case.

### Hand-editing the data files

The files are meant to stay readable and editable in a text editor (like
Vim) or a spreadsheet (like LibreOffice Calc). The app holds them to the
form it writes, so that a slip gets caught instead of guessed at. Only how a
value is written (spaces, case, a number's form) is fixed for you.

**Do:**

- **Close the app first.** While it runs, the app is the only source of
  truth for the files: its next save overwrites changes made by anything
  else.
- **Keep the header row exactly as it is:**
  `FREQ,MODE,CALL,PARK,ST,SNT,RCD,PWR,DATE,TIME,COMMENT,STATION_CALLSIGN,UUIDv4`
- **Put each record in the file for its DATE.** DATE must match the file
  name. To move a record to another day, edit its DATE in the app, which
  moves it for you.
- **Write values the way the app does:**

  | Column | Write it as | Not |
  |---|---|---|
  | FREQ | Hz: `14074500` | `14.074.5` |
  | MODE | `SSB`, `USB`, `LSB`, or `CW` | `FT8` |
  | CALL, STATION_CALLSIGN | Uppercase: `W1ABC` | |
  | PARK | Full reference: `US-0464` | `464`, `US464` |
  | ST | A state code, or empty | `XX`, `NA` |
  | SNT, RCD | 2 digits (3 on CW): `59`, `599` | |
  | PWR | Watts: `60`, `0.5` | `60W` |
  | DATE | `YYYYMMDD`: `20261001` | `2026-10-01`, `10/01/2026` |
  | TIME | 4 digits, `HHMM`: `0053` | `53`, `00:53` |

- **Leave UUIDv4 empty on a row you add by hand** (end the line with a
  comma). The app fills in a new ID when it starts.
- **Quote a COMMENT that contains a comma or a double quote**, CSV style:
  `"Nice, loud"`. A double quote inside it is written twice: `"He said ""hi"""`.
- **In a spreadsheet, keep TIME as text,** so `0053` doesn't turn into `53`.
  A spreadsheet's byte-order mark and `\r\n` line endings are fine.
- **Save as UTF-8 CSV.**

**Don't:**

- **Don't copy a row to make a new record without emptying its UUIDv4.**
  Two rows with one ID are taken as one record saved twice, and marked `U`.
- **Don't make up or change an ID.** Leave it empty and let the app make one.
- **Don't start or end a COMMENT with a space.** Spaces inside it are fine.
- **Don't use non-ASCII characters** (accents, curly quotes, full-width
  digits, emoji) or line breaks inside a value.
- **Don't add, remove, rename, or reorder columns.**
- **Don't name other files in `data/` like `YYYYMMDD.csv`,** or they'll be
  read as logs. Other names are ignored.

If something's off, start the app: it tells you which file and row, and
what's wrong.

## Status

Built: everything above.

Not built yet:

- QRZ.com API upload (maybe)
- POTA's parks list (filling ST, park names)

Scope, field rules, and the plan live in [REQUIREMENTS.md](REQUIREMENTS.md).

## Noted issues

Not every issue is listed here: only ones that won't be fixed, so you
know not to expect a fix, and any you need to know about to keep your
log safe.

| Issue | Status | Reason |
| --- | --- | --- |
| A notification can lose its bottom row spacer at a couple of window widths. | Will Not Fix | Low impact, cosmetic. Fix more correct upstream. |
