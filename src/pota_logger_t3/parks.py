import re

# Optional letter prefix, optional dash, then the park number.
PARK_PATTERN = re.compile(r"^([A-Za-z]*)-?(\d+)$")


def format_park(text: str) -> str:
    """Format PARK for display: US-<number> for a bare number or a US
    prefix with no dash (e.g. `jp234`); PREFIX-<number> otherwise, dash
    added if missing. Falls back to the text as entered, uppercased, if it
    doesn't match that shape.
    """
    park = text.strip()
    match = PARK_PATTERN.match(park)
    if not match:
        return park.upper()
    prefix, number = match.groups()
    return f"{prefix.upper() or 'US'}-{number}"
