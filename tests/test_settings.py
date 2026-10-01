import tomllib

import pytest

from pota_logger_t3.settings import Settings, StationCallsignError, load_settings, save_settings


def test_load_missing_file_returns_defaults(settings_path):
    assert load_settings(settings_path) == Settings(station_callsign="")


def test_save_creates_data_dir(settings_path):
    save_settings(Settings(station_callsign="W1TST"), settings_path)
    assert settings_path.read_text() == 'station_callsign = "W1TST"\n'


def test_round_trip(settings_path):
    save_settings(Settings(station_callsign="VE3/W1TST"), settings_path)
    assert load_settings(settings_path) == Settings(station_callsign="VE3/W1TST")


def test_save_escapes_quotes(settings_path):
    # A call never has these (the settings modal refuses them), but the
    # file stays valid TOML whatever it's given.
    save_settings(Settings(station_callsign='A"B\\C'), settings_path)
    assert tomllib.loads(settings_path.read_text()) == {"station_callsign": 'A"B\\C'}


def test_missing_key_uses_default(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("# empty\n")
    assert load_settings(settings_path) == Settings()


def test_invalid_toml_raises(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1TST\n')
    with pytest.raises(tomllib.TOMLDecodeError):
        load_settings(settings_path)


def write_settings(settings_path, text: str) -> None:
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(text)


def test_empty_station_callsign_means_none_set(settings_path):
    write_settings(settings_path, 'station_callsign = ""\n')
    assert load_settings(settings_path) == Settings(station_callsign="")


def test_station_callsign_loads(settings_path):
    write_settings(settings_path, 'station_callsign = "VE3/W1TST"\n')
    assert load_settings(settings_path) == Settings(station_callsign="VE3/W1TST")


def test_unusual_station_callsign_loads_as_meant(settings_path):
    write_settings(settings_path, 'station_callsign = "W100AW"\n')
    assert load_settings(settings_path) == Settings(station_callsign="W100AW")


@pytest.mark.parametrize(
    "value, message",
    [
        ('"W1"', "station_callsign 'W1' doesn't look like a callsign, like W1ABC"),
        ('"W1TST/"', "station_callsign 'W1TST/' has an empty part next to a /"),
        ('"W1-TST"', "station_callsign 'W1-TST' can only use letters, digits, and /"),
        ('"W1TSÉ"', "station_callsign 'W1TSÉ' has non-ASCII characters: 'É'."),
        ("1234", "station_callsign '1234' doesn't look like a callsign, like W1ABC"),
        ('"w1tst"', "station_callsign 'w1tst' should be uppercase, like W1TST"),
        ('"VE3/W1tst"', "station_callsign 'VE3/W1tst' should be uppercase, like VE3/W1TST"),
        ('" W1TST "', "station_callsign ' W1TST ' should have no spaces around it, like W1TST"),
        ('"W1TST "', "station_callsign 'W1TST ' should have no spaces around it, like W1TST"),
        ('"  "', "station_callsign '  ' should be empty, with no spaces"),
        ('"W1 TST"', "station_callsign 'W1 TST' can only use letters, digits, and /"),
        ('"W1TST\\t"', "station_callsign 'W1TST\\t' has non-ASCII characters: '\\t'."),
        ('"W1TST🙂"', "station_callsign 'W1TST🙂' has non-ASCII characters: '🙂'."),
    ],
)
def test_bad_station_callsign_is_refused(settings_path, value, message):
    write_settings(settings_path, f"station_callsign = {value}\n")
    with pytest.raises(StationCallsignError) as error:
        load_settings(settings_path)
    assert str(error.value) == message


def test_refused_station_callsign_keeps_the_text_to_fix(settings_path):
    write_settings(settings_path, 'station_callsign = " w1tst "\n')
    with pytest.raises(StationCallsignError) as error:
        load_settings(settings_path)
    assert error.value.text == " w1tst "
