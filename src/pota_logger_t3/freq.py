# US amateur allocations from 80m to 10m, as (low, high) Hz, inclusive.
# No two bands share a bare-digit reading, so bare entry is never ambiguous.
US_BANDS = [
    (3_500_000, 4_000_000),  # 80m
    (7_000_000, 7_300_000),  # 40m
    (10_100_000, 10_150_000),  # 30m
    (14_000_000, 14_350_000),  # 20m
    (18_068_000, 18_168_000),  # 17m
    (21_000_000, 21_450_000),  # 15m
    (24_890_000, 24_990_000),  # 12m
    (28_000_000, 29_700_000),  # 10m
]

FORMAT_HINT = "14.074, 14.0745, 14.074.5, or 14074"


def in_us_band(hz: int) -> bool:
    return any(low <= hz <= high for low, high in US_BANDS)


def parse_freq(text: str) -> int:
    """Parse a frequency as entered, always in MHz, into Hz.

    Missing digits are filled with zeros.
    With a dot, everything after it is fractional MHz, up to 6 digits,
    optionally split after the kHz digits by a second dot:
    14.1 -> 14.100.000, 14.0745 -> 14.074.500, 14.074.5 -> 14.074.500.
    Bare digits are the same with the dot left out; the MHz part is
    whichever of 1 or 2 leading digits lands in a US band:
    14 -> 14.000.000, 141501 -> 14.150.100, 3985 -> 3.985.000.

    Raises ValueError with a message suitable for showing the operator.
    """
    text = text.strip()
    if "." in text:
        candidates = [_parse_dotted(text)]
    elif text.isdigit():
        candidates = _bare_candidates(text)
    else:
        raise ValueError(f"FREQ {text!r} should look like {FORMAT_HINT}")

    for hz in candidates:
        if in_us_band(hz):
            return hz
    raise ValueError(f"FREQ {text!r} isn't in a US amateur band (80m to 10m)")


def _parse_dotted(text: str) -> int:
    mhz, _, fraction = text.partition(".")
    if "." in fraction:
        khz, _, sub = fraction.partition(".")
        if len(khz) != 3:
            raise ValueError(f"FREQ {text!r}: a second dot goes after 3 kHz digits, as in 14.074.5")
        fraction = khz + sub
    if not mhz.isdigit() or (fraction and not fraction.isdigit()):
        raise ValueError(f"FREQ {text!r} should look like {FORMAT_HINT}")
    if len(fraction) > 6:
        raise ValueError(f"FREQ {text!r} has more than 6 digits after the MHz")
    return _to_hz(mhz, fraction)


def _bare_candidates(digits: str) -> list[int]:
    """Each reading of digits with the dot after 1 or 2 MHz digits."""
    return [
        _to_hz(digits[:split], digits[split:])
        for split in (1, 2)
        if split <= len(digits) and len(digits) - split <= 6
    ]


def _to_hz(mhz: str, fraction: str) -> int:
    return int(mhz) * 1_000_000 + int(fraction.ljust(6, "0"))


def format_freq(hz: int) -> str:
    """Format Hz as MHz.kHz.Hz, e.g. 14000000 -> 14.000.000."""
    mhz, rest = divmod(hz, 1_000_000)
    khz, sub = divmod(rest, 1_000)
    return f"{mhz}.{khz:03d}.{sub:03d}"
