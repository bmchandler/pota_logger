from datetime import UTC, date, datetime, time, timedelta

from pota_logger_t3.entry_warnings import future_time


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
