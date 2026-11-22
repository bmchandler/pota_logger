---
name: hand-test-data
description: >
  Rules for writing hand-test records into POTA Logger's data/ files by
  hand: how to mark a COMMENT that narrates how a QSO came about when
  that origin didn't literally happen (Simulated / $ / SIM), when a row
  may read plainly, and which calls are safe. Use when creating or
  editing test rows in data/ by hand. Only do this when the user
  explicitly asks for hand-test data.
---

# Hand-test data

Only create rows in `data/` when the user explicitly asks. `data/` is
git-ignored, so these rows stay out of the repo — but they must still be
honest about how they came to exist, so a made-up row can never be taken
for a real contact.

## The marking rule

A COMMENT saying how a record came about is marked when that didn't
literally happen, so it can't be taken for the real thing:

- `Simulated hand-added in Calc` — preferred, when there's room.
- `$Hand-added in Calc` — when short of room (`$`: S for simulated, and
  ASCII).
- `SIM Hand-added in Calc` — where `$` might clash with something.

A row really made that way (e.g. in Vim, run from the terminal) reads
plainly. A plain fact about the row as written (`ID in uppercase`) is not
a narration of origin and needs no mark.

## Callsigns (hard rule)

Use calls chosen to look made up, like `W1TST` or `W1ABC`; never a real
call, never the maintainer's, never one copied from a real log. See the
privacy rules in DEVELOPMENT.md and CLAUDE.md.
