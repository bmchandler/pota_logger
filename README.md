# POTA Logger

A keyboard-first terminal logbook for **hunting** [Parks on the Air](https://docs.pota.app/)
contacts. It's built for copying a paper log into the computer quickly and
accurately: type each line as it's written, and the app checks it as you go.

The intended workflow is paper log → POTA Logger → ADIF export → QRZ.com import.
ADIF export isn't built yet.

It runs in a terminal (built with [Textual](https://textual.textualize.io/)),
stores everything in plain CSV files you can open in a text editor or
spreadsheet, and needs no internet connection.

Scope: hunter contacts only (not activating), voice (SSB, USB, LSB) and CW, on
US amateur bands from 80m to 10m, WARC bands included.

## Features

### Fast entry

- One row of fields in paper-log order: FREQ, MODE, CALL, PARK, ST, SNT, RCD,
  PWR, DATE, TIME, with COMMENT on the line below. Tab moves between fields,
  and Enter saves.
- Shorthand typing:
  - FREQ in MHz, with digits left out: `14.074.5`, `14.0745`, `14074`, and
    `141501` (read as 14.150.100) all work.
  - PARK as a bare number for US parks: `464` becomes `US-0464`, and `jp1234`
    becomes `JP-1234`.
  - DATE as `YYMMDD`, TIME as `HHMM`, and any case for MODE and CALL.
- PWR and DATE carry over to the next entry. MODE starts each entry as `SSB`.
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

### Dupes

An entry that matches one already logged in every column except COMMENT is
blocked as a duplicate. No two real contacts match to the minute, frequency,
and reports, so it's the same paper line typed twice. To add a note to a
logged contact, edit that record's COMMENT.

### The log

- The log below the form shows this session's entries in the order typed,
  to check line by line against the paper. Saved entries follow, newest
  first.
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
  same checks as a new entry.
- **F4** deletes it, after a confirmation that takes Enter twice. There is no
  undo.
- **Esc** steps back: from editing to selected, then to nothing selected,
  with what you were typing before put back.
- Refused (`!`), `U`, and `=` rows list what's wrong, or where the other
  copies are, below COMMENT. Fix them with edit or delete, without opening
  the files.

### Settings and keys

- **F2** opens Settings, which holds your station callsign. No entry can be
  saved until one is set, and every record stores the station callsign it
  was logged with.
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

The app changes a file on its own in only one case: a row with a blank
record ID gets a new one when the app starts.

### Hand-editing the data files

The files are meant to stay readable and editable in a text editor (like
Vim) or a spreadsheet (like LibreOffice Calc). The app holds them to exactly
the form it writes, so that a slip gets caught instead of guessed at.

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
  | FREQ | Hz: `14074500` | `14.074.5`, `014074500` |
  | MODE | `SSB`, `USB`, `LSB`, or `CW` | `usb` |
  | CALL, STATION_CALLSIGN | Uppercase: `W1ABC` | `w1abc` |
  | PARK | Full reference: `US-0464` | `464`, `us-0464` |
  | ST | A state code, `NA`, or empty | `nj` |
  | SNT, RCD | 2 digits (3 on CW): `59`, `599` | |
  | PWR | Watts: `60`, `0.5` | `.5`, `60.0`, `60W` |
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
  An uppercase ID is read, but the row is refused until it's saved in
  lowercase.
- **Don't put spaces around a value,** for example `, W1ABC,`. Spaces inside a
  COMMENT are fine.
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

- ADIF export (for QRZ.com import)
- Sorting the log by any column

Scope, field rules, and the plan live in [REQUIREMENTS.md](REQUIREMENTS.md).

## Noted issues

Not every issue is listed here: only ones that won't be fixed, so you
know not to expect a fix, and any you need to know about to keep your
log safe.

| Issue | Status | Reason |
| --- | --- | --- |
| A notification can lose its bottom row spacer at a couple of window widths. | Will Not Fix | Low impact, cosmetic. Fix more correct upstream. |
