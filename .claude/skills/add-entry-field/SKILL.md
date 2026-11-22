---
name: add-entry-field
description: >
  Add a new logbook entry field to POTA Logger, or change an existing
  field's validation. Covers the fields/ parse_/format_ module, the ASCII
  check, wiring into entry_form.py (FIELDS, PARSERS, OPTIONAL, DEFAULTS,
  CARRY_FORWARD, WARNINGS) and app.py (FORMATTERS, DISPLAY_LENGTHS), the
  block-vs-warn decision, unit tests plus one app wiring test, and
  recording the rule in REQUIREMENTS.md. Use when adding or changing a
  logbook field's rules. NOT for non-field changes.
---

# Add (or change) an entry field

## The rule is a product requirement, not yours to invent

The field's validation rule — what's valid, what's refused, what only
warns — belongs in [REQUIREMENTS.md](../../../REQUIREMENTS.md), the
source of truth for field rules. Write or update the rule there in the
same change (Entry fields, and Entry behavior if it blocks or warns).
This skill is the mechanics of wiring a field that honors the rule, not
the rule itself.

## The field module (`fields/<name>.py`)

- `parse_<name>(text)` returns the stored value, or raises `ValueError`
  with the exact message shown to the operator. Use ham shorthand
  ("dupe", not "duplicate"); a warning message ends with "Esc to
  correct, or confirm with Enter." and uses explicit line breaks.
- `format_<name>(value)` only if the field displays differently from how
  it's stored.
- Any new text input gets the ASCII check (`check_ascii`,
  `fields/ascii_text.py`) before its own rules: Python's `isdigit()` and
  `\d` also match non-ASCII digits like ５ and ².
- Entry fits ADIF: input must always fit the ADIF standard, whatever QRZ
  or other logbooks accept.

## Wiring

- `entry_form.py`: `FIELDS` (name, placeholder, longest value) in entry
  order; `ROW_FIELDS`/`ENTRY_ORDER` for the top row, or keep it below
  like COMMENT. Then `PARSERS` (entry order), or `REPORTS` if it depends
  on MODE. Add to `OPTIONAL`, `DEFAULTS`, `CARRY_FORWARD`, `WARNINGS` as
  the field needs.
- Column order for the log table and CSV is `LOG_FIELDS` /
  `LOG_ROW_FIELDS`, not `FIELDS` — use it wherever column order matters.
- `app.py`: `FORMATTERS` and `DISPLAY_LENGTHS` for the log table.

## Block vs warn

Decide per the project's rule — block only what can't be right or what
ADIF rejects; warn what's odd-but-real (the operator copies a paper log,
so a real but odd contact must stay saveable). See
[DEVELOPMENT.md, Entry checks: block vs warn](../../../DEVELOPMENT.md#entry-checks-block-vs-warn).
A warning is a check in `entry_warnings.py` listed in `WARNINGS`, shown
in `warning_screen.py`; it takes the entry, the entries logged so far,
and the parks list.

## Tests

- Field rules and messages: unit tests in `tests/fields/` (near-instant).
- Keep ONE app test proving the field is wired into the form's checks
  (`PARSERS`/`REPORTS`/focus) — a unit test can't prove the wiring.

## Finish

Record the rule in REQUIREMENTS.md in the same change. The skill/doc
itself is dev-only (no release); a new user-visible field earns a
CHANGELOG.md line under `## Unreleased` and a release.
