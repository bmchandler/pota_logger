from datetime import UTC, datetime

from pota_logger_t3.dates import format_date, format_time
from pota_logger_t3.freq import band_name, format_freq, voice_range
from pota_logger_t3.sidebands import signal_edges
from pota_logger_t3.states import US_STATES

CONFIRM_HINT = "Esc to correct, or confirm with Enter."


# Each check takes the entry being saved and the entries logged so far, and
# returns a warning message or None.


def possible_dupe(values: dict, logged: list[dict]) -> str | None:
    """Warn when CALL, PARK, DATE, band, and voice/CW all match a logged
    entry: POTA counts that contact only once.
    """
    earlier = next((entry for entry in logged if dupe_key(entry) == dupe_key(values)), None)
    if earlier is None:
        return None
    call, park, _, band, mode_type = dupe_key(values)
    return (
        f"Possible dupe: {call} at {park},\n"
        f"{band} {mode_type}, already logged at {format_time(earlier['TIME'])}.\n"
        f"{CONFIRM_HINT}"
    )


def dupe_key(values: dict) -> tuple:
    mode_type = "CW" if values["MODE"] == "CW" else "voice"
    return (
        values["CALL"],
        values["PARK"],
        values["DATE"],
        band_name(values["FREQ"]),
        mode_type,
    )


def future_time(values: dict, logged: list[dict]) -> str | None:
    """Warn when DATE plus TIME is later than now, UTC."""
    when = datetime.combine(values["DATE"], values["TIME"], UTC)
    if when <= datetime.now(UTC):
        return None
    return (
        f"{format_date(values['DATE'])} {format_time(values['TIME'])} UTC is in the future.\n"
        f"{CONFIRM_HINT}"
    )


def voice_outside_range(values: dict, logged: list[dict]) -> str | None:
    """Warn when a voice signal runs outside its band's voice range: below
    it (in the CW/data range), or past an edge on the logged sideband.
    """
    mode, freq = values["MODE"], values["FREQ"]
    if mode == "CW":
        return None
    edges = voice_range(freq)
    signal_low, signal_high = signal_edges(freq, mode)
    if edges is not None and edges[0] <= signal_low and signal_high <= edges[1]:
        return None
    return (
        f"{mode} on {format_freq(freq)} runs outside\n"
        f"{band_name(freq)}'s voice range.\n"
        f"{CONFIRM_HINT}"
    )


def state_on_non_us_park(values: dict, logged: list[dict]) -> str | None:
    """Warn when a non-US park has a US state in ST (blank or NA is fine)."""
    park = values["PARK"]
    if park.startswith("US-") or values["ST"] not in US_STATES:
        return None
    return f"{park} is a non-US park, so ST is likely blank.\n{CONFIRM_HINT}"
