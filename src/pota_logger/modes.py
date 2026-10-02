MODES = ["SSB", "USB", "LSB", "CW"]


def parse_mode(text: str) -> str:
    """Parse MODE: one of SSB, USB, LSB, or CW, any case. Returned uppercase.

    Raises ValueError with a message suitable for showing the operator.
    """
    mode = text.strip().upper()
    if mode not in MODES:
        raise ValueError(f"MODE {text.strip()!r} should be SSB, USB, LSB, or CW")
    return mode
