import re
from collections.abc import Mapping
from dataclasses import dataclass

from pota_logger.states import US_STATES

# ADIF's POTARef: PROGRAM-NUMBER[@LOCATION]. The program is 1 to 4
# characters with at least one letter; the number is 4 or 5 digits
# (shorter ones get leading zeros here); the location is a 4 to 6
# character ISO 3166-2 code, for parks spanning more than one (e.g. trails).
# Without a dash, the number is the trailing run of digits.
PARK_PATTERN = re.compile(
    r"(?:(?P<program>[A-Z0-9]{1,4})-|(?P<bare>[A-Z0-9]{0,3}[A-Z]))?"
    r"(?P<number>[0-9]+)"
    r"(?:@(?P<location>[A-Z0-9-]{4,6}))?"
)
PROGRAM_LETTER = re.compile(r"[A-Z]")

# ADIF's longest POTA reference, e.g. ABCD-12345@US-ABC.
MAX_LENGTH = 17

US_PROGRAM = "US"
NUMBER_LENGTH = 4
MAX_NUMBER_LENGTH = 5


def parse_park(text: str) -> str:
    """Parse PARK into a POTA reference: `1234` is `US-1234`, `jp234` is
    `JP-0234`, `us-4566@us-wy` is `US-4566@US-WY`.

    Raises ValueError with a message suitable for showing the operator.
    """
    park = text.strip().upper()
    match = PARK_PATTERN.fullmatch(park)
    program = match and (match["program"] or match["bare"] or US_PROGRAM)
    if not match or not PROGRAM_LETTER.search(program):
        raise ValueError(
            f"PARK {text.strip()!r} isn't a POTA park; use a form like 1234, JP-1234, "
            "or US-4566@US-WY"
        )
    # Its own message: the shape is right, so "use a form like" would
    # look like it already does.
    if len(match["number"]) > MAX_NUMBER_LENGTH:
        raise ValueError(
            f"PARK {text.strip()!r} isn't a POTA park; parks must be <= "
            f"{MAX_NUMBER_LENGTH} digits"
        )
    reference = f"{program}-{match['number'].zfill(NUMBER_LENGTH)}"
    if match["location"]:
        reference += f"@{match['location']}"
    return reference


# A park in POTA's parks list (parks_list.py), and lookups in it.


@dataclass(frozen=True)
class Park:
    """A park as POTA's list gives it: its name, whether it's active, its
    DXCC entity's number ("" if none), and the US states it's in (`NC`,
    without POTA's `US-`; none outside the US).
    """

    name: str
    active: bool
    dxcc: str
    states: tuple[str, ...]


def listed_park(parks: Mapping[str, Park], park: str) -> Park | None:
    """The listed park for PARK as parsed (`US-4566@US-WY` is US-4566's),
    or None if it isn't listed.
    """
    return parks.get(park.split("@")[0])


def park_states(parks: Mapping[str, Park], park: str) -> tuple[str, ...]:
    """The US states a park (PARK as parsed) is in: the location's, when
    one names a state (`US-4566@US-WY` is WY, as the operator said where),
    otherwise the list's (none for a park not listed).
    """
    listed = listed_park(parks, park)
    if listed is None:
        return ()
    _, _, location = park.partition("@")
    if location.startswith("US-") and location[3:] in US_STATES:
        return (location[3:],)
    return listed.states
