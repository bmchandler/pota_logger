import textwrap
from collections.abc import Mapping
from datetime import UTC, datetime

from pota_logger.dates import format_date, format_time
from pota_logger.freq import band_name, format_freq, voice_range
from pota_logger.parks import Park, listed_park, park_states
from pota_logger.sidebands import signal_edges
from pota_logger.states import US_STATES

CONFIRM_HINT = "Esc to correct, or confirm with Enter."


# A warning's width inside its modal, for lines of no set length.
MESSAGE_WIDTH = 42


# Each check takes the entry being saved, the entries logged so far, and
# POTA's parks list (none without one), and returns a warning message or
# None.


def future_time(
    values: dict, logged: list[dict], parks: Mapping[str, Park] = {}
) -> str | None:
    """Warn when DATE plus TIME is later than now, UTC."""
    when = datetime.combine(values["DATE"], values["TIME"], UTC)
    if when <= datetime.now(UTC):
        return None
    return (
        f"{format_date(values['DATE'])} {format_time(values['TIME'])} UTC is in the future.\n"
        f"{CONFIRM_HINT}"
    )


def voice_outside_range(
    values: dict, logged: list[dict], parks: Mapping[str, Park] = {}
) -> str | None:
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


def state_on_non_us_park(
    values: dict, logged: list[dict], parks: Mapping[str, Park] = {}
) -> str | None:
    """Warn when a non-US park has a US state in ST (blank is fine)."""
    park = values["PARK"]
    if park.startswith("US-") or values["ST"] not in US_STATES:
        return None
    return f"{park} is a non-US park, so ST is likely blank.\n{CONFIRM_HINT}"


def park_not_listed(
    values: dict, logged: list[dict], parks: Mapping[str, Park] = {}
) -> str | None:
    """Warn on a park POTA's list doesn't have (it may be new), or marks
    inactive. Not without a list.
    """
    if not parks:
        return None
    park = values["PARK"]
    reference = park.split("@")[0]
    listed = listed_park(parks, park)
    if listed is None:
        return (
            f"{reference} isn't in POTA's parks list.\n"
            "It may be new: Check for Updated in\n"
            "Settings (f2) to get the latest list.\n"
            f"{CONFIRM_HINT}"
        )
    if not listed.active:
        return f"{reference} is inactive in POTA's parks list.\n{CONFIRM_HINT}"
    return None


def state_not_the_parks(
    values: dict, logged: list[dict], parks: Mapping[str, Park] = {}
) -> str | None:
    """Warn when ST isn't one of the park's states (its location's, if
    one names a state). Blank is fine; so is any ST for a park with no
    US state, or not listed.
    """
    state, park = values["ST"], values["PARK"]
    states = park_states(parks, park)
    if not state or not states or state in states:
        return None
    if len(states) <= 2:
        where = " or ".join(states)
    else:
        where = f"{', '.join(states[:-1])}, or {states[-1]}"
    message = f"{park.split('@')[0]} is in {where}, not {state}."
    return f"{textwrap.fill(message, MESSAGE_WIDTH)}\n{CONFIRM_HINT}"
