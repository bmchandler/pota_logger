from datetime import datetime
from pathlib import Path

from pota_logger.screens.screenshot_screen import screenshot_name, typed_path


def test_screenshot_name_from_the_date_and_time():
    assert screenshot_name(datetime(2026, 1, 5, 9, 3, 7)) == "pota-logger_260105_090307.svg"


def test_typed_path_expands_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert typed_path("~/a/b.svg") == tmp_path / "a" / "b.svg"


def test_typed_path_not_from_the_root_is_in_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert typed_path("a/b.svg") == tmp_path / "a" / "b.svg"


def test_typed_path_from_the_root_kept():
    assert typed_path("/srv/b.svg") == Path("/srv/b.svg")
