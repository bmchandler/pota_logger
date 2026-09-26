from datetime import date


def parse_date(text: str) -> date:
    """Parse a UTC date entered as YYMMDD, in 2000-2099: 260923 -> 2026-09-23.

    Raises ValueError with a message suitable for showing the operator.
    """
    text = text.strip()
    if len(text) != 6 or not text.isdigit():
        raise ValueError(f"DATE {text!r} should be YYMMDD, like 260923")
    try:
        return date(2000 + int(text[:2]), int(text[2:4]), int(text[4:]))
    except ValueError:
        raise ValueError(f"DATE {text!r} isn't a real date") from None


def format_date(value: date) -> str:
    """Format a date for display: 2026-09-23 -> 2026.09.23."""
    return value.strftime("%Y.%m.%d")
