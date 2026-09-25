import tomllib

import pytest

from pota_logger_t3.settings import Settings, load_settings, save_settings


def test_load_missing_file_returns_defaults(settings_path):
    assert load_settings(settings_path) == Settings(station_callsign="")


def test_save_creates_data_dir(settings_path):
    save_settings(Settings(station_callsign="W1TST"), settings_path)
    assert settings_path.read_text() == 'station_callsign = "W1TST"\n'


def test_round_trip(settings_path):
    save_settings(Settings(station_callsign="VE3/W1TST"), settings_path)
    assert load_settings(settings_path) == Settings(station_callsign="VE3/W1TST")


def test_round_trip_escapes_quotes(settings_path):
    save_settings(Settings(station_callsign='A"B\\C'), settings_path)
    assert load_settings(settings_path) == Settings(station_callsign='A"B\\C')


def test_missing_key_uses_default(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("# empty\n")
    assert load_settings(settings_path) == Settings()


def test_invalid_toml_raises(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1TST\n')
    with pytest.raises(tomllib.TOMLDecodeError):
        load_settings(settings_path)
