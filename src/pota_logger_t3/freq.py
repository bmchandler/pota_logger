def parse_freq(text: str) -> int:
    """Parse a frequency as entered, always in MHz, into Hz.

    Missing digits are filled with zeros.
    With a dot, everything after it is fractional MHz, up to 6 digits,
    optionally split after the kHz digits by a second dot:
    14.1 -> 14.100.000, 14.0745 -> 14.074.500, 14.074.5 -> 14.074.500.
    Bare digits are MHz with the dots left out, grouped from the right:
    14 -> 14.000.000, 14074 -> 14.074.000, 14074123 -> 14.074.123.

    Raises ValueError with a message suitable for showing the operator.
    """
    text = text.strip()
    mhz, dot, fraction = text.partition(".")
    if "." in fraction:
        khz, _, sub = fraction.partition(".")
        if len(khz) != 3:
            raise ValueError(f"FREQ {text!r}: a second dot goes after 3 kHz digits, as in 14.074.5")
        fraction = khz + sub
    if not mhz.isdigit() or (fraction and not fraction.isdigit()):
        raise ValueError(f"FREQ {text!r} should look like 14.074, 14.0745, 14.074.5, or 14074")
    if len(fraction) > 6:
        raise ValueError(f"FREQ {text!r} has more than 6 digits after the MHz")

    if dot:
        hz = int(mhz) * 1_000_000 + int(fraction.ljust(6, "0"))
    elif len(mhz) <= 3:
        hz = int(mhz) * 1_000_000
    elif len(mhz) <= 6:
        hz = int(mhz) * 1_000
    else:
        hz = int(mhz)

    if hz == 0:
        raise ValueError("FREQ can't be zero")
    return hz


def format_freq(hz: int) -> str:
    """Format Hz as MHz.kHz.Hz, e.g. 14000000 -> 14.000.000."""
    mhz, rest = divmod(hz, 1_000_000)
    khz, sub = divmod(rest, 1_000)
    return f"{mhz}.{khz:03d}.{sub:03d}"
