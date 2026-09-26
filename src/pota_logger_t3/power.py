import re
from decimal import Decimal

MIN_WATTS = Decimal("0.1")
MAX_WATTS = Decimal("1500")  # US legal limit

NUMBER = re.compile(r"\d+(\.\d*)?|\.\d+")


def parse_power(text: str) -> Decimal:
    """Parse PWR as watts, 0.1 to 1500: 60 -> 60, .5 -> 0.5.

    Raises ValueError with a message suitable for showing the operator.
    """
    text = text.strip()
    if not NUMBER.fullmatch(text):
        raise ValueError(f"PWR {text!r} should be watts as a number, like 60 or .5")
    watts = Decimal(text)
    if not MIN_WATTS <= watts <= MAX_WATTS:
        raise ValueError(f"PWR {text!r} should be between .1 and 1500 watts")
    return watts


def format_power(watts: Decimal) -> str:
    """Format watts for display: 60 -> 60W, 0.5 -> .5W, 2.50 -> 2.5W."""
    number = format(watts.normalize(), "f")
    if number.startswith("0."):
        number = number[1:]
    return f"{number}W"
