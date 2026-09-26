def parse_freq(text: str) -> int:
    """Parse a frequency as entered into Hz.

    Dotted form is MHz.kHz.Hz, with the kHz and Hz parts left-aligned:
    14 -> 14.000.000, 14.1 -> 14.100.000, 14.123.4 -> 14.123.400.
    Bare digits are MHz up to 3 digits (14), or Hz from 7 digits (28312456).

    Raises ValueError with a message suitable for showing the operator.
    """
    text = text.strip()
    parts = text.split(".")
    if not all(part.isdigit() for part in parts) or len(parts) > 3:
        raise ValueError(f"FREQ {text!r} should look like 14.074, 14.074.5, or 14074500")

    if len(parts) == 1:
        digits = parts[0]
        if len(digits) <= 3:
            hz = int(digits) * 1_000_000
        elif len(digits) >= 7:
            hz = int(digits)
        else:
            raise ValueError(f"FREQ {text!r} is ambiguous; use 14.074 or 14074000")
    else:
        mhz, *rest = parts
        if any(len(part) > 3 for part in rest):
            raise ValueError(f"FREQ {text!r} has more than 3 digits after a dot")
        khz, sub = (rest + ["0"])[:2]
        hz = int(mhz) * 1_000_000 + int(khz.ljust(3, "0")) * 1_000 + int(sub.ljust(3, "0"))

    if hz == 0:
        raise ValueError("FREQ can't be zero")
    return hz


def format_freq(hz: int) -> str:
    """Format Hz as MHz.kHz.Hz, e.g. 14000000 -> 14.000.000."""
    mhz, rest = divmod(hz, 1_000_000)
    khz, sub = divmod(rest, 1_000)
    return f"{mhz}.{khz:03d}.{sub:03d}"
