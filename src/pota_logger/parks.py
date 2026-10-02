import re

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
