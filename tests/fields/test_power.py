from decimal import Decimal

import pytest

from pota_logger.fields.power import format_power, parse_power


@pytest.mark.parametrize(
    "text, watts",
    [
        ("60", Decimal("60")),
        (" 60 ", Decimal("60")),
        ("5", Decimal("5")),
        ("2.5", Decimal("2.5")),
        (".5", Decimal("0.5")),
        ("0.5", Decimal("0.5")),
        (".1", Decimal("0.1")),
        ("100.", Decimal("100")),
        ("1500", Decimal("1500")),
    ],
)
def test_parse_power(text, watts):
    assert parse_power(text) == watts


@pytest.mark.parametrize("text", ["", "60W", "60w", "W", "abc", "-5", "1,500", "1e2", "."])
def test_parse_power_rejects_non_numbers(text):
    with pytest.raises(ValueError, match="should be watts as a number"):
        parse_power(text)


@pytest.mark.parametrize("text", ["0", ".05", "0.09", "1500.1", "1501", "2000"])
def test_parse_power_rejects_out_of_range(text):
    with pytest.raises(ValueError, match="between .1 and 1500 watts"):
        parse_power(text)


@pytest.mark.parametrize(
    "watts, text",
    [
        (Decimal("60"), "60W"),
        (Decimal("100"), "100W"),
        (Decimal("1500"), "1500W"),
        (Decimal("2.5"), "2.5W"),
        (Decimal("2.50"), "2.5W"),
        (Decimal("0.5"), ".5W"),
        (Decimal("0.1"), ".1W"),
        (Decimal("60.0"), "60W"),
    ],
)
def test_format_power(watts, text):
    assert format_power(watts) == text
