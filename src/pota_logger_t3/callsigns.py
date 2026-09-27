import re

ALLOWED = re.compile(r"[A-Z0-9/]+")

# Prefix, a separating digit, and a suffix ending in a letter: W1ABC, 2E0ABC.
BASE_CALL = re.compile(r"[A-Z0-9]+[0-9][A-Z0-9]*[A-Z]")

MAX_SLASHES = 2


def parse_callsign(text: str) -> str:
    """Parse CALL: any case, returned uppercase. Checks only the shape:
    letters, digits, and up to two slashes, with at least one part shaped
    like a call (VE3/W1ABC/P). Prefixes aren't checked against a country
    table, so rare special-event calls still get through.

    Raises ValueError with a message suitable for showing the operator.
    """
    call = text.strip().upper()
    shown = text.strip()
    if not ALLOWED.fullmatch(call):
        raise ValueError(f"CALL {shown!r} can only use letters, digits, and /")
    if call.count("/") > MAX_SLASHES:
        raise ValueError(f"CALL {shown!r} has more than {MAX_SLASHES} slashes")
    parts = call.split("/")
    if "" in parts:
        raise ValueError(f"CALL {shown!r} has an empty part next to a /")
    if not any(BASE_CALL.fullmatch(part) for part in parts):
        raise ValueError(f"CALL {shown!r} doesn't look like a callsign, like W1ABC")
    return call
