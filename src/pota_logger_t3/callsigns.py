def parse_callsign(text: str) -> str:
    """Parse CALL: any case. Returned uppercase."""
    return text.strip().upper()
