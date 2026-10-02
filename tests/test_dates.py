from datetime import date, time

import pytest

from pota_logger import dates
from pota_logger.dates import default_date, format_date, format_time, parse_date, parse_time


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


def test_default_date_is_todays_local_date(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 9, 3)

    monkeypatch.setattr(dates, "date", FixedDate)
    assert default_date() == "260903"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2123", time(21, 23)),
        (" 2123 ", time(21, 23)),
        ("0000", time(0, 0)),
        ("0005", time(0, 5)),
        ("2359", time(23, 59)),
    ],
)
def test_parse_time(text, expected):
    assert parse_time(text) == expected


@pytest.mark.parametrize(
    "text",
    ["", "212", "21234", "21:23", "abcd", "2400", "2360", "9999", "-123"],
)
def test_parse_time_rejects(text):
    with pytest.raises(ValueError):
        parse_time(text)


def test_not_a_real_time_message():
    with pytest.raises(ValueError, match="isn't a real time"):
        parse_time("2400")


def test_format_time():
    assert format_time(time(9, 5)) == "09:05"
