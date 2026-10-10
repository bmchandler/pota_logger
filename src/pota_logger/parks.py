import re
from dataclasses import dataclass

# ADIF's POTARef: PROGRAM-NUMBER[@LOCATION]. The program is 1 to 4
# characters with at least one letter; the number is 4 or 5 digits
# (shorter ones get leading zeros here). The location (an ISO 3166-2
# code, for parks spanning more than one, e.g. trails) is the ADIF
# export's to add, from ST (decided 2026-10-10): ST holds the same fact,
# so it isn't typed. Without a dash, the number is the trailing run of
# digits.
PARK_PATTERN = re.compile(
    r"(?:(?P<program>[A-Z0-9]{1,4})-|(?P<bare>[A-Z0-9]{0,3}[A-Z]))?"
    r"(?P<number>[0-9]+)"
)
PROGRAM_LETTER = re.compile(r"[A-Z]")

# ADIF's longest POTA reference as PARK takes it (no @LOCATION), e.g.
# ABCD-12345. POTA's references appear to follow ADIF's, so it's
# assumed to be POTA's limit too.
MAX_LENGTH = 10

US_PROGRAM = "US"
NUMBER_LENGTH = 4
MAX_NUMBER_LENGTH = 5


def parse_park(text: str) -> str:
    """Parse PARK into a POTA reference: `1234` is `US-1234`, `jp234` is
    `JP-0234`. The `@LOCATION` form is refused (see PARK_PATTERN).

    Raises ValueError with a message suitable for showing the operator.
    """
    park = text.strip().upper()
    if "@" in park:
        raise ValueError(f"PARK {text.strip()!r}: @ form not accepted for input; ADIF export only")
    match = PARK_PATTERN.fullmatch(park)
    program = match and (match["program"] or match["bare"] or US_PROGRAM)
    if not match or not PROGRAM_LETTER.search(program):
        raise ValueError(
            f"PARK {text.strip()!r} isn't a POTA park; use a form like 1234 or JP-1234"
        )
    # Its own message: the shape is right, so "use a form like" would
    # look like it already does.
    if len(match["number"]) > MAX_NUMBER_LENGTH:
        raise ValueError(
            f"PARK {text.strip()!r} isn't a POTA park; parks must be <= "
            f"{MAX_NUMBER_LENGTH} digits"
        )
    return f"{program}-{match['number'].zfill(NUMBER_LENGTH)}"


# A park in POTA's parks list (parks_list.py), by its reference.


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
