# 50 states plus DC, matching ADIF's STATE values for the USA.
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
    "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI",
    "WY",
}  # fmt: skip

NOT_APPLICABLE = "NA"


def parse_state(text: str) -> str:
    """Parse ST: a US state code, NA, or blank. Returned uppercase.

    Raises ValueError with a message suitable for showing the operator.
    """
    state = text.strip().upper()
    if state and state != NOT_APPLICABLE and state not in US_STATES:
        raise ValueError(f"ST {text.strip()!r} isn't a US state; use a code like NJ, NA, or blank")
    return state
