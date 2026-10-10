# Changelog

What changed in each release, newest first. Versions are dates
(`YYYY.M.D`; see [RELEASING.md](RELEASING.md)). Changes not released yet
are under Unreleased.

## 2026.10.10

### Added

- ADIF export (`f6`, or the ADIF button): a date range of the log, as
  one ADIF file in the export folder set in Settings, for import into
  QRZ.com or another logbook. Refused while any row is marked `!`, `U`,
  or `=`.
- POTA's parks list: offered for download at first start, and checked
  for updates from Settings. With it, the park's name shows beside
  COMMENT, ST is filled in from the park, an unlisted or inactive park
  and an ST not the park's get warnings, and the export adds each
  park's DXCC entity.
- Install with `uv tool install`; an installed app keeps its files in
  `~/.local/share/pota-logger/data/`, with a `README.txt` beside them
  summing up the files and the hand-editing rules. Uninstalling leaves
  them in place.
- MIT license.
- DEVELOPMENT.md (running from source, tests, the code's layout) and
  RELEASING.md (making a release).

### Changed

- PARK refuses ADIF's `@` location form (`US-4566@US-WY`); the export
  adds the location from ST for a park in several states.

## MVP

Tagged `MVP` (2026-10-08): the first complete version, for copying a
paper hunter log into CSV files.

- Entry form: FREQ, MODE, CALL, PARK, ST, SNT, RCD, PWR, DATE, TIME, and
  COMMENT, with shorthand entry (FREQ by band, bare park numbers, DATE
  as YYMMDD), each field checked as ADIF allows, and anything that
  can't be right refused.
- Warnings, saveable with Enter, for what's probably wrong but could be
  real: an unusual callsign, a future date and time, a voice mode in a
  CW range, a sideband running outside the voice range, and a US state
  on a non-US park.
- Definite dupes blocked; settings to fill COMMENT with POTA info.
- Storage in plain CSV, one file per UTC date, each row with a record
  ID; every file checked at start, with only how a value is written
  fixed, and rows breaking a rule shown marked `!` to fix in the app.
  Shared IDs marked `U`, saved dupes `=`, and their counts shown.
- The log: this session's entries above the saved ones, newest first;
  selecting, editing (`f3`), and deleting (`f4`) entries; Sort (`f5`,
  or a header click).
- One station callsign per log, set in Settings (`F2`) and checked at
  start.
- A light outdoors color theme, a status bar with UTC and local clocks,
  and screenshots (`Ctrl+S`).
