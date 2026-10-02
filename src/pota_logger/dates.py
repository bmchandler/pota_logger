from datetime import date, time


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


def default_date() -> str:
    """DATE's default value on app start: today's *local* date as YYMMDD.

    Local, not UTC: the app is typically started right after a session
    ends, when the UTC date has often already rolled over from the date
    most of the entries actually happened on.
    """
    return date.today().strftime("%y%m%d")


def parse_time(text: str) -> time:
    """Parse a UTC time entered as 24-hour HHMM: 2123 -> 21:23.

    Raises ValueError with a message suitable for showing the operator.
    """
    text = text.strip()
    if len(text) != 4 or not text.isdigit():
        raise ValueError(f"TIME {text!r} should be HHMM, like 2123")
    try:
        return time(int(text[:2]), int(text[2:]))
    except ValueError:
        raise ValueError(f"TIME {text!r} isn't a real time (0000 to 2359)") from None


def format_time(value: time) -> str:
    """Format a time for display: 21:23."""
    return value.strftime("%H:%M")
