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

## Entry fields

In entry order (mirrors the paper log). All times and dates are UTC.

| Field | Entered as | Stored as | Displayed as | Notes |
|---|---|---|---|---|
| FREQ | Always MHz, shorthand allowed: `14`, `14.1`, `14.0745`, `14.074.5`, `14074`, `28312456` | Integer Hz | Always in full: `14.000.000`, `14.074.500` | Never carried forward. Missing digits are filled with zeros. After a dot, up to 6 fractional MHz digits, optionally with a second dot after the 3 kHz digits (`14.1` is `14.100.000`; `14.0745` and `14.074.5` are `14.074.500`). Bare digits are the same with the dot left out; the MHz part is whichever of 1 or 2 leading digits lands in a band (`141501` is `14.150.100`, `3985` is `3.985.000`). Across 80m to 10m only one reading ever fits. Must be inside a US amateur band from 80m to 10m. |
| MODE | `SSB`, `USB`, `LSB`, `CW` | Text | Same | Defaults to `SSB` on each new entry. USB/LSB are for non-standard sideband near band edges. |
| CALL | Free text, e.g. `W1ABC`, `VE3/W1ABC` | Uppercase text | Same | International and slash calls allowed. |
| PARK | `1234` or `JP-1234` | Full reference, e.g. `US-1234` | Bare number for US, full reference otherwise | Bare number means `US-`. One park per entry. |
| ST | `NJ`, `NA`, or blank | Uppercase text | Same | State the park is in. Optional, even for US parks, since it isn't always clear at entry time. If given, must be a US state code (50 states plus DC) or `NA`. Not checked against the park; no park database is kept. |
| SNT | `59` / `599` | Text | Same | Comes before RCD on purpose. |
| RCD | `59` / `599` | Text | Same | |
| PWR | `60W` or `60` | Integer watts | `60W` | Carried forward. |
| DATE | `260925` (YYMMDD, years 2000–2099) | Part of the entry's UTC timestamp (`20260925` in CSV) | `2026.09.25` | Carried forward. Must be a real calendar date. |
| TIME | `1953` (24-hour HHMM) | Part of the entry's UTC timestamp (`1953` in CSV) | `19:53` | Entered last. Must be a real time, 0000 to 2359. |

Session-level value:

- **Station callsign:** the operator's own call. It's shown in a top status
  area and recorded on each entry (ADIF `STATION_CALLSIGN`). It's set in the
  settings modal.

## Settings

- A settings modal holds app-wide settings, starting with the station
  callsign. Future settings go there too.
- Settings are saved in `data/settings.toml`.

## Entry behavior

- Fields can be filled and edited in any order before an entry is saved.
- An entry can't be saved until every required field is filled in and valid.
  ST is the only optional field.
- Only DATE and PWR carry forward to the next entry. Everything else is
  entered fresh each time (MODE resets to `SSB`).
- Multi-park activations: each park is a separate entry.
- Warn, but don't block, when an entry's time is earlier than the previous
  entry's on the same date. This catches entries typed out of order or a
  missed midnight UTC date change.

## Log view

- Entries stay in the order they were entered. There's no automatic sorting,
  so the log can be checked line by line against the paper log.
- A **Sort** action orders entries by UTC timestamp when the operator asks for
  it.

## Storage

- CSV files only. No SQLite.
- Stored in a `data/` folder under the project.
- One CSV file per UTC date, named `YYYYMMDD.csv` (e.g. `data/20260924.csv`).
- `data/` is ignored by git, so logs stay out of the code history.
- Column names use the same shorthand and order as the entry fields:
  `FREQ, MODE, CALL, PARK, ST, SNT, RCD, PWR, DATE, TIME`, then
  `STATION_CALLSIGN`.
- Values are stored in their "Stored as" form, e.g. FREQ `14074500`,
  PARK `US-1234`, PWR `60`, DATE `20260925`, TIME `1953`.
- Dates and times are UTC everywhere, in both storage and entry. An entry's
  full timestamp is its DATE plus its TIME, and it's stored in the file named
  for its DATE.
- Files should stay readable and editable by hand.
- If a hand edit breaks loading, show an error naming the offending file and
  row number.

## Export

- ADIF, aimed at QRZ.com import. Field details (e.g. `SIG`/`SIG_INFO` vs
  `POTA_REF`, and station and operator fields) are worked out when export is
  built.
