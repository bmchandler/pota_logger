from datetime import date

import pytest

from pota_logger_t3.dates import format_date, parse_date


@pytest.mark.parametrize(
    "text, expected",
    [
        ("260923", date(2026, 9, 23)),
        (" 260923 ", date(2026, 9, 23)),
        ("000101", date(2000, 1, 1)),
        ("991231", date(2099, 12, 31)),
        ("280229", date(2028, 2, 29)),  # leap year
    ],
)
def test_parse_date(text, expected):
    assert parse_date(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "2609",
        "2609231",
        "20260923",  # full year isn't accepted
        "26-09-23",
        "abcdef",
        "260900",
        "260001",
        "261301",
        "260230",
        "270229",  # not a leap year
    ],
)
def test_parse_date_rejects(text):
    with pytest.raises(ValueError):
        parse_date(text)


def test_not_a_real_date_message():
    with pytest.raises(ValueError, match="isn't a real date"):
        parse_date("260230")


def test_format_date():
    assert format_date(date(2026, 9, 3)) == "2026.09.03"
