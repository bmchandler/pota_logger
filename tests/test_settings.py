import tomllib

import pytest

from pota_logger.settings import (
    Settings,
    StationCallsignError,
    default_export_folder,
    home_relative,
    load_settings,
    save_settings,
)


def test_load_missing_file_returns_defaults(settings_path):
    assert load_settings(settings_path) == Settings(station_callsign="")


def test_save_creates_data_dir(settings_path):
    save_settings(Settings(station_callsign="W1TST"), settings_path)
    assert settings_path.read_text() == (
        'station_callsign = "W1TST"\n'
        "new_comment_pota_info = false\n"
        "edit_comment_pota_info = false\n"
        'adif_export_folder = ""\n'
        'updates = "notify"\n'
    )


def test_round_trip(settings_path):
    save_settings(Settings(station_callsign="VE3/W1TST"), settings_path)
    assert load_settings(settings_path) == Settings(station_callsign="VE3/W1TST")


def test_save_escapes_quotes(settings_path):
    # A call never has these (the settings modal refuses them), but the
    # file stays valid TOML whatever it's given.
    save_settings(Settings(station_callsign='A"B\\C'), settings_path)
    assert tomllib.loads(settings_path.read_text())["station_callsign"] == 'A"B\\C'


def test_switches_round_trip(settings_path):
    settings = Settings("W1TST", new_comment_pota_info=True, edit_comment_pota_info=True)
    save_settings(settings, settings_path)
    assert load_settings(settings_path) == settings
    save_settings(Settings("W1TST", edit_comment_pota_info=True), settings_path)
    assert load_settings(settings_path) == Settings("W1TST", edit_comment_pota_info=True)


@pytest.mark.parametrize(
    "value, shown",
    [('"yes"', "'yes'"), ('"true"', "'true'"), ("1", "1"), ("[]", "[]")],
)
def test_switch_not_true_or_false_is_off_with_a_problem(settings_path, value, shown):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        f'station_callsign = "W1TST"\nnew_comment_pota_info = true\nedit_comment_pota_info = {value}\n'
    )
    settings = load_settings(settings_path)
    assert settings == Settings("W1TST", new_comment_pota_info=True)
    assert settings.problems == [f"edit_comment_pota_info {shown} must be true or false"]


def test_missing_switches_are_off(settings_path):
    # A file from before the switches.
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1TST"\n')
    settings = load_settings(settings_path)
    assert settings == Settings("W1TST")
    assert settings.problems == []


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
    write_settings(settings_path, 'station_callsign = " w1-tst "\n')
    with pytest.raises(StationCallsignError) as error:
        load_settings(settings_path)
    assert error.value.text == " w1-tst "


@pytest.mark.parametrize(
    "value, callsign",
    [
        ('"w1tst"', "W1TST"),
        ('"VE3/W1tst"', "VE3/W1TST"),
        ('" W1TST "', "W1TST"),
        ('" w1tst"', "W1TST"),
        # Just spaces: none set.
        ('"  "', ""),
    ],
)
def test_how_the_station_callsign_is_written_is_fixed(settings_path, value, callsign):
    write_settings(settings_path, f"station_callsign = {value}\n")
    settings = load_settings(settings_path)
    assert settings == Settings(station_callsign=callsign)
    assert settings.fixed


def test_station_callsign_as_saved_isnt_fixed(settings_path):
    write_settings(settings_path, 'station_callsign = "W1TST"\n')
    assert not load_settings(settings_path).fixed


def test_folder_round_trip(settings_path):
    settings = Settings("W1TST", adif_export_folder="~/Downloads/pota")
    save_settings(settings, settings_path)
    assert 'adif_export_folder = "~/Downloads/pota"\n' in settings_path.read_text()
    assert load_settings(settings_path) == settings


def test_folder_with_quotes_and_backslashes_round_trips(settings_path):
    settings = Settings("W1TST", adif_export_folder='C:\\Logs\\"ADIF"')
    save_settings(settings, settings_path)
    assert load_settings(settings_path) == settings


def test_missing_folder_is_none_set(settings_path):
    # A file from before the folder setting.
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1TST"\n')
    settings = load_settings(settings_path)
    assert settings.adif_export_folder == ""
    assert settings.problems == []


def test_folder_spaces_are_fixed(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1TST"\nadif_export_folder = " ~/adif "\n')
    settings = load_settings(settings_path)
    assert settings.adif_export_folder == "~/adif"
    assert settings.fixed
    assert settings.problems == []


@pytest.mark.parametrize(
    "value, problem",
    [
        ("1", "adif_export_folder 1 must be a folder, in quotes"),
        ("true", "adif_export_folder True must be a folder, in quotes"),
        (
            '"~/T\u00e9l\u00e9chargements"',
            "adif_export_folder '~/T\u00e9l\u00e9chargements' has non-ASCII characters: '\u00e9'.",
        ),
    ],
)
def test_bad_folder_is_none_set_with_a_problem(settings_path, value, problem):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(f'station_callsign = "W1TST"\nadif_export_folder = {value}\n')
    settings = load_settings(settings_path)
    assert settings.adif_export_folder == ""
    assert settings.problems == [problem]


def test_default_export_folder_is_beside_data(tmp_path):
    assert default_export_folder(tmp_path / "data") == str(tmp_path / "exports")


def test_default_export_folder_in_home_is_written_with_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    data = tmp_path / ".local/share/pota-logger/data"
    assert default_export_folder(data) == "~/.local/share/pota-logger/exports"


def test_home_relative_writes_the_home_folder_as_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert home_relative(tmp_path / "a" / "data") == "~/a/data"


def test_home_relative_leaves_a_path_outside_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert home_relative(tmp_path / "data") == str(tmp_path / "data")


def test_updates_round_trip(settings_path):
    for choice in ("none", "notify", "on_quit"):
        save_settings(Settings("W1TST", updates=choice), settings_path)
        assert load_settings(settings_path) == Settings("W1TST", updates=choice)


def test_updates_missing_is_notify(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1TST"\n')
    assert load_settings(settings_path).updates == "notify"


@pytest.mark.parametrize("value, shown", [('"yes"', "'yes'"), ("true", "True"), ("[]", "[]")])
def test_updates_not_a_choice_is_none_with_a_problem(settings_path, value, shown):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(f'station_callsign = "W1TST"\nupdates = {value}\n')
    settings = load_settings(settings_path)
    assert settings.updates == "none"
    assert settings.problems == [
        f'updates {shown} must be one of "none", "notify", "on_quit"'
    ]
