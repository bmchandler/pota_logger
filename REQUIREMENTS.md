# POTA Logger T3 — Requirements

## Purpose

A local TUI logbook for **hunting** POTA parks, tuned for fast manual entry of
contacts first recorded by hand in a paper logbook.

Workflow: paper logbook → manual entry in this app → ADIF export → QRZ.com
ADIF import.

Reference: <https://docs.pota.app/>

## Scope

In scope:

- Logging hunter contacts (voice and CW).
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
| FREQ | `14.074`, `14.074.5`, `14.074.55` (MHz.kHz.sub-kHz) | Integer Hz | Trailing zeros trimmed: `14.074`, `14.074.5`, `14.074.55` | Never carried forward. |
| MODE | `SSB`, `USB`, `LSB`, `CW` | Text | Same | Defaults to `SSB` on each new entry. USB/LSB are for non-standard sideband near band edges. |
| CALL | Free text, e.g. `W1ABC`, `VE3/W1ABC` | Uppercase text | Same | International and slash calls allowed. |
| PARK | `1234` or `JP-1234` | Full reference, e.g. `US-1234` | Bare number for US, full reference otherwise | Bare number means `US-`. One park per entry. |
| ST | `NJ` | Text | Same | State the park is in. |
| SNT | `59` / `599` | Text | Same | Comes before RCD on purpose. |
| RCD | `59` / `599` | Text | Same | |
| PWR | `60W` or `60` | Integer watts | `60W` | Carried forward. |
| TIME | `1953` (HHMM) | Part of the entry's UTC timestamp | `1953` | Entered last. |

Session-level values:

- **UTC date:** carried forward. It's set when it changes, and each entry's
  timestamp combines it with that entry's HHMM time.
- **Station callsign:** the operator's own call. It's shown in a top status
  area and recorded on each entry (ADIF `STATION_CALLSIGN`). It's set in the
  settings modal.

## Settings

- A settings modal holds app-wide settings, starting with the station
  callsign. Future settings go there too.

## Entry behavior

- Fields can be filled and edited in any order before an entry is saved.
- An entry can't be saved until every required field is filled in and valid.
- Only UTC date and power carry forward to the next entry. Everything else is
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
- One CSV file per UTC date, named by date (e.g. `data/2026-09-24.csv`).
- Column names use the same shorthand and order as the entry fields:
  `FREQ, MODE, CALL, PARK, ST, SNT, RCD, PWR, TIME`, then
  `STATION_CALLSIGN`.
- Values are stored in their "Stored as" form, e.g. FREQ `14074500`,
  PARK `US-1234`, PWR `60`, TIME `1953`.
- Dates and times are UTC everywhere, in both storage and entry. An entry's
  full timestamp is its file's date plus its TIME.
- Files should stay readable and editable by hand.
- If a hand edit breaks loading, show an error naming the offending file and
  row number.

## Export

- ADIF, aimed at QRZ.com import. Field details (e.g. `SIG`/`SIG_INFO` vs
  `POTA_REF`, and station and operator fields) are worked out when export is
  built.

## Open questions

- Where settings are saved.
