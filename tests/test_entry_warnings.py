from datetime import UTC, date, datetime, time, timedelta

import pytest

from pota_logger.entry_warnings import (
    future_time,
    park_not_listed,
    state_not_the_parks,
    state_on_non_us_park,
    voice_outside_range,
)
from pota_logger.parks import Park


def when(moment: datetime) -> dict:
    return {"DATE": moment.date(), "TIME": time(moment.hour, moment.minute)}


def test_past_time_has_no_warning():
    assert future_time({"DATE": date(2026, 9, 25), "TIME": time(19, 53)}, []) is None


def test_current_minute_has_no_warning():
    assert future_time(when(datetime.now(UTC)), []) is None


def test_future_time_warns():
    assert future_time({"DATE": date(2099, 12, 31), "TIME": time(19, 53)}, []) == (
        "2099.12.31 19:53 UTC is in the future.\nEsc to correct, or confirm with Enter."
    )


def test_later_today_warns():
    assert future_time(when(datetime.now(UTC) + timedelta(minutes=2)), []) is not None


@pytest.mark.parametrize(
    "mode, freq",
    [
        ("SSB", 14_285_000),
        ("SSB", 14_150_000),  # right on the edge; SSB there is refused before warnings
        ("USB", 21_200_000),
        ("USB", 21_447_000),
        ("LSB", 21_450_000),
        ("LSB", 21_203_000),
        ("CW", 14_074_000),
        ("CW", 10_120_000),
    ],
)
def test_voice_inside_range_has_no_warning(mode, freq):
    assert voice_outside_range({"MODE": mode, "FREQ": freq}, []) is None


@pytest.mark.parametrize(
    "mode, freq",
    [
        ("USB", 14_074_500),  # CW/data range
        ("SSB", 14_074_500),
        ("SSB", 10_120_000),  # 30m has no voice range
        ("LSB", 21_200_000),  # signal 21.197-21.200
        ("LSB", 21_202_999),
        ("USB", 21_450_000),  # signal 21.450-21.453
        ("USB", 21_447_001),
    ],
)
def test_voice_outside_range_warns(mode, freq):
    assert voice_outside_range({"MODE": mode, "FREQ": freq}, []) is not None


def test_voice_outside_range_message():
    assert voice_outside_range({"MODE": "USB", "FREQ": 21_450_000}, []) == (
        "USB on 21.450.000 runs outside\n15m's voice range.\n"
        "Esc to correct, or confirm with Enter."
    )


@pytest.mark.parametrize(
    "park, state",
    [("US-1234", "NJ"), ("US-4566@US-WY", "WY"), ("JP-1234", "")],
)
def test_state_on_park_without_warning(park, state):
    assert state_on_non_us_park({"PARK": park, "ST": state}, []) is None


def test_state_on_non_us_park_warns():
    assert state_on_non_us_park({"PARK": "JP-1234", "ST": "NJ"}, []) == (
        "JP-1234 is a non-US park, so ST is likely blank.\nEsc to correct, or confirm with Enter."
    )


PARKS = {
    "US-0001": Park("Acadia National Park", True, "291", ("ME",)),
    "US-0002": Park("Old Park", False, "291", ("ME",)),
    "US-4566": Park(
        "California National Historic Trail",
        True,
        "291",
        ("CA", "CO", "ID", "KS", "MO", "NE", "NV", "OR", "UT", "WY"),
    ),
    "US-0003": Park("Trail", True, "291", ("DC", "MD")),
    "JA-0001": Park("Rishiri-Rebun-Sarobetsu National Park", True, "339", ()),
}


@pytest.mark.parametrize("park", ["US-0001", "US-4566@US-WY", "JA-0001"])
def test_listed_active_park_has_no_warning(park):
    assert park_not_listed({"PARK": park}, [], PARKS) is None


def test_no_park_warning_without_a_list():
    assert park_not_listed({"PARK": "US-9999"}, []) is None


@pytest.mark.parametrize("park", ["US-9999", "US-9999@US-WY"])
def test_park_not_in_the_list_warns(park):
    assert park_not_listed({"PARK": park}, [], PARKS) == (
        "US-9999 isn't in POTA's parks list.\n"
        "It may be new: Check for Updated in\n"
        "Settings (f2) to get the latest list.\n"
        "Esc to correct, or confirm with Enter."
    )


def test_inactive_park_warns():
    assert park_not_listed({"PARK": "US-0002"}, [], PARKS) == (
        "US-0002 is inactive in POTA's parks list.\nEsc to correct, or confirm with Enter."
    )


@pytest.mark.parametrize(
    "park, state",
    [
        ("US-0001", "ME"),
        ("US-0001", ""),
        ("US-4566", "NV"),
        ("US-4566@US-WY", "WY"),
        # Not this check's: no US state, or not listed.
        ("JA-0001", "NJ"),
        ("US-9999", "NJ"),
    ],
)
def test_state_of_the_park_has_no_warning(park, state):
    assert state_not_the_parks({"PARK": park, "ST": state}, [], PARKS) is None


def test_no_state_warning_without_a_list():
    assert state_not_the_parks({"PARK": "US-0001", "ST": "NJ"}, []) is None


def test_state_not_the_parks_warns():
    assert state_not_the_parks({"PARK": "US-0001", "ST": "NJ"}, [], PARKS) == (
        "US-0001 is in ME, not NJ.\nEsc to correct, or confirm with Enter."
    )


def test_state_not_one_of_the_parks_warns():
    assert state_not_the_parks({"PARK": "US-0003", "ST": "NJ"}, [], PARKS) == (
        "US-0003 is in DC or MD, not NJ.\nEsc to correct, or confirm with Enter."
    )


def test_state_not_the_locations_warns():
    # The location says where, though NV is one of the trail's.
    assert state_not_the_parks({"PARK": "US-4566@US-WY", "ST": "NV"}, [], PARKS) == (
        "US-4566 is in WY, not NV.\nEsc to correct, or confirm with Enter."
    )


def test_many_states_wrap_to_the_modal():
    message = state_not_the_parks({"PARK": "US-4566", "ST": "NJ"}, [], PARKS)
    assert message == (
        "US-4566 is in CA, CO, ID, KS, MO, NE, NV,\n"
        "OR, UT, or WY, not NJ.\n"
        "Esc to correct, or confirm with Enter."
    )
