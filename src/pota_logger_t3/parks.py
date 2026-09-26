def format_park(text: str) -> str:
    """Format PARK for display: a bare number becomes US-<number>; anything
    else (already a full reference like JP-1234) is shown as entered.
    """
    park = text.strip()
    if park.isdigit():
        return f"US-{park}"
    return park
