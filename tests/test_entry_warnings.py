from datetime import UTC, date, datetime, time, timedelta

import pytest

from pota_logger.entry_warnings import (
    future_time,
    state_on_non_us_park,
    voice_outside_range,
)


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
