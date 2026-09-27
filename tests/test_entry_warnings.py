from datetime import UTC, date, datetime, time, timedelta

from pota_logger_t3.entry_warnings import future_time, voice_in_cw_range


def when(moment: datetime) -> dict:
    return {"DATE": moment.date(), "TIME": time(moment.hour, moment.minute)}


def test_past_time_has_no_warning():
    assert future_time({"DATE": date(2026, 9, 25), "TIME": time(19, 53)}) is None


def test_current_minute_has_no_warning():
    assert future_time(when(datetime.now(UTC))) is None


def test_future_time_warns():
    assert future_time({"DATE": date(2099, 12, 31), "TIME": time(19, 53)}) == (
        "2099.12.31 19:53 UTC is in the future.\nEsc to correct, or confirm with Enter."
    )


def test_later_today_warns():
    assert future_time(when(datetime.now(UTC) + timedelta(minutes=2))) is not None


def test_voice_in_voice_range_has_no_warning():
    assert voice_in_cw_range({"MODE": "SSB", "FREQ": 14_285_000}) is None


def test_cw_anywhere_has_no_warning():
    assert voice_in_cw_range({"MODE": "CW", "FREQ": 14_285_000}) is None
    assert voice_in_cw_range({"MODE": "CW", "FREQ": 10_120_000}) is None


def test_voice_in_cw_range_warns():
    assert voice_in_cw_range({"MODE": "USB", "FREQ": 14_074_500}) == (
        "USB on 14.074.500 is outside 20m's voice range.\nEsc to correct, or confirm with Enter."
    )


def test_voice_on_30m_warns():
    assert voice_in_cw_range({"MODE": "SSB", "FREQ": 10_120_000}).startswith(
        "SSB on 10.120.000 is outside 30m's voice range."
    )
