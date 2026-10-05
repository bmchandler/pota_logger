# Columns a definite dupe may differ in; it matches in every other one.
IGNORED = {"COMMENT", "UUIDv4"}

# The modal on Enter when an entry is a definite dupe, for a new entry and
# for an edit. It closes back to the form, the entry as typed.
NEW_DUPE_MESSAGE = (
    "Excluding COMMENT, attempted save\n"
    "will result in a duplicate record.\n"
    "See DATE & TIME to locate other record."
)
EDIT_DUPE_MESSAGE = NEW_DUPE_MESSAGE + (
    "\n"
    "Change field value(s), or Esc out to\n"
    "cancel.\n"
    "\n"
    "WARNING:\n"
    "Updated COMMENT will be lost after\n"
    "escaping out."
)

# The modal's only button; Enter or Esc closes it too.
DUPE_BUTTON = "Roger Roger"


def dupe_key(entry: dict) -> tuple:
    """What a definite dupe matches in: every column but COMMENT and the
    record ID, STATION_CALLSIGN included.
    """
    return tuple(sorted((name, value) for name, value in entry.items() if name not in IGNORED))


def is_dupe(values: dict, logged: list[dict]) -> bool:
    """Whether `values` (with its STATION_CALLSIGN) is a definite dupe of a
    logged entry: no two real contacts match in every column, so it's the
    same one entered twice.
    """
    key = dupe_key(values)
    return any(dupe_key(entry) == key for entry in logged)
