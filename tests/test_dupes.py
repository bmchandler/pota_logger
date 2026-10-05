from datetime import date, time
from decimal import Decimal

import pytest

from pota_logger.dupes import is_dupe

LOGGED = {
    "FREQ": 14_285_500,
    "MODE": "USB",
    "CALL": "W1ABC",
    "PARK": "US-1234",
    "ST": "NJ",
    "SNT": "59",
    "RCD": "57",
    "PWR": Decimal("60"),
    "DATE": date(2026, 9, 25),
    "TIME": time(19, 53),
    "COMMENT": "",
    "STATION_CALLSIGN": "W1TST",
    "UUIDv4": "1b4e28ba-2fa1-4d2b-883f-0016d3cca427",
}

# An entry as the form checks it: no ID yet.
NEW = {name: value for name, value in LOGGED.items() if name != "UUIDv4"}


def test_same_in_every_column_but_comment_is_a_dupe():
    other = LOGGED | {"CALL": "K2DEF"}
    assert is_dupe(NEW | {"COMMENT": "Loud"}, [other, LOGGED])


@pytest.mark.parametrize(
    "change",
    [
        {"FREQ": 14_285_501},
        {"MODE": "LSB"},
        {"CALL": "W1ABD"},
        {"PARK": "US-1235"},
        {"ST": ""},
        {"SNT": "58"},
        {"RCD": "58"},
        {"PWR": Decimal("5")},
        {"DATE": date(2026, 9, 26)},
        {"TIME": time(19, 54)},
        {"STATION_CALLSIGN": "W1ABC"},
    ],
)
def test_any_other_difference_is_not_a_dupe(change):
    assert not is_dupe(NEW | change, [LOGGED])


def test_power_written_another_way_is_the_same():
    assert is_dupe(NEW | {"PWR": Decimal("60.0")}, [LOGGED])


def test_empty_log_has_no_dupe():
    assert not is_dupe(NEW, [])
