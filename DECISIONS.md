# POTA Logger — Design decisions

Ideas considered and deferred, and ideas decided against. The product
rules themselves are in [REQUIREMENTS.md](REQUIREMENTS.md); release
decisions are in [RELEASING.md](RELEASING.md).

## Ideas considered and deferred

- A CW warning within about 1 kHz of a band edge. Left out for now: a CW
  signal is narrow, and radios differ on whether the dial shows the
  transmit frequency or is offset by the CW pitch.
- Defaulting DATE to "UTC now minus a few hours", which would suit
  operators in any time zone. The local-date default fits the current
  operator (US Eastern).
- A Keys help panel (Textual's, from the command palette). Textual's
  input fields already use ctrl+k (delete to the end), and overriding
  stock bindings is avoided, so it was dropped with the palette.
- Lining the narrow form's scrollbar up exactly with the input boxes.
  Textual's input borders put the visible edge partway into a cell, so
  it would take non-stock input borders; the stock look was kept.
- Dates before 2000 (or after 2099). The entry form's YYMMDD covers
  2000 to 2099, and log rows outside it are refused on load, so an edit
  can't change their year. Decided 2026-10-10 to leave it so: importing
  older logs isn't planned, and nothing before 2000 needs logging.
- Bulk edits (e.g. PWR across a session) and undo: not planned. Entries
  are copied from paper one at a time, so bulk edits add little and
  raise the risk of mistakes; an entry is fixed by editing or deleting
  it. Revisit only if real use calls for them.
- A limit on digits in a callsign. ADIF sets none, and special-event
  calls use years and anniversaries (`W100AW`); the unusual-callsign
  warning covers typos like `W111111AB`.
- A full ADIF export (every entry) in the Export modal, as a backup
  or for another logging program. Meanwhile a date range from the
  oldest DATE does the same.

## Ideas decided against

- PARK as a comma list of parks (`1234,2345,3456`), mirroring ADIF's
  `POTA_REF`, for a 2-fer or more in one entry. Kept as an idea when the
  ADIF export was planned (2026-10-09), since `POTA_REF` takes a list;
  dropped 2026-10-13. A hunter's park credit comes from the activator's
  log, so the list would only tidy the operator's own export, and the
  other parks already go in COMMENT (see [Entry behavior](REQUIREMENTS.md#entry-behavior), multi-park
  activations). It would have changed the log column, the load checks,
  the dupe check, sorting, COMMENT's POTA info, and ST (parks in
  different states). A separate field for extra parks was set aside
  earlier: it needs room in the form, and a fixed number of fields would
  cap the parks.
- `f1` opening Info over a modal or block (decided 2026-10-13): extra
  code for little value; like the app's other keys, it doesn't.
