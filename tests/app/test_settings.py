"""The Settings modal: the station callsign, switches, and export folder."""

import pytest
from textual.widgets import Button, Checkbox, Input, Label, Static

from pota_logger.app import PotaLoggerApp
from pota_logger.screens.callsign_warning_screen import CallsignWarningScreen
from pota_logger.screens.parks_offer_screen import ParksOfferScreen
from pota_logger.screens.settings_screen import SettingsScreen
from pota_logger.settings import Settings, load_settings, save_settings

from tests.app.helpers import (
    ENTRY,
    ENTRY_ROW,
    SETTING_LABELS,
    checkbox_marks,
    exports,
    field_values,
    fill,
    folder_problem,
    open_settings_with,
    required_message,
    setting_labels,
    settings_problem,
    station_callsign,
    table_rows,
)


async def test_no_station_callsign_opens_on_required_block(settings_path):
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        assert app.screen.id == "station-callsign-required"
        assert required_message(app) == (
            "A valid callsign for transmitting\nstation is required.\n"
            "Press Enter to go to Settings."
        )
        assert [b.label.plain for b in app.screen.query(Button)] == ["Settings"]
        assert station_callsign(app) == "NOCALL"
        # No Esc, and F2 doesn't stack Settings over it.
        await pilot.press("escape", "f2")
        assert app.screen.id == "station-callsign-required"
        await pilot.press("enter")
        assert isinstance(app.screen, SettingsScreen)
        app.screen.query_one("#station-callsign-input", Input).value = "w1tst"
        await pilot.press("enter")
        # Then the parks list is offered (skipped here).
        assert isinstance(app.screen, ParksOfferScreen)
        await pilot.press("escape")
        assert len(app.screen_stack) == 1
        assert app.focused.id == "field-freq"
        assert station_callsign(app) == "W1TST"
        expected = Settings("W1TST", adif_export_folder=exports(settings_path))
        assert load_settings(settings_path) == expected


async def test_settings_cancelled_with_no_call_goes_back_to_block(settings_path):
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        await pilot.press("enter", "escape")
        assert app.screen.id == "station-callsign-required"
        await pilot.press("enter")
        assert isinstance(app.screen, SettingsScreen)


async def test_ctrl_q_quits_from_required_block(settings_path):
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+q")
        assert app.return_code == 0


async def test_enter_with_no_station_callsign_keeps_entry_and_asks_for_one(app, settings_path):
    async with app.run_test() as pilot:
        # Not reachable through Settings, which always ends with a call
        # set; a guard so no row is saved without one.
        app.settings = Settings()
        fill(app, ENTRY)
        await pilot.press("enter")
        assert app.screen.id == "station-callsign-required"
        await pilot.press("enter")
        app.screen.query_one("#station-callsign-input", Input).value = "W1ABC"
        await pilot.press("enter")
        assert table_rows(app) == []
        assert field_values(app) == ENTRY
        await pilot.press("enter")
        assert table_rows(app) == [ENTRY_ROW]
    row = (settings_path.parent / "20260925.csv").read_text().splitlines()[1]
    assert row.rsplit(",", 1)[0].endswith(",W1ABC")


async def test_loads_saved_callsign(app):
    async with app.run_test():
        assert station_callsign(app) == "W1TST"


async def test_settings_is_f2_with_no_button(app):
    # The footer's f2 is a click away; the buttons are ADIF and Quit.
    async with app.run_test() as pilot:
        assert [str(button.label) for button in app.query("#button-bar Button")] == ["ADIF", "Quit"]
        await pilot.press("f2")
        assert isinstance(app.screen, SettingsScreen)
        assert app.focused.id == "new_comment_pota_info"


async def test_settings_after_setup_hide_the_call(app):
    # A log holds one call, so it isn't changed in Settings.
    async with app.run_test() as pilot:
        await pilot.press("f2")
        assert not app.screen.query("#station-callsign-input")
        assert setting_labels(app) == SETTING_LABELS
        assert [box.value for box in app.screen.query(Checkbox)] == [False, False]


async def test_checkbox_x_shows_only_when_checked(app):
    async with app.run_test() as pilot:
        await pilot.press("f2")
        assert checkbox_marks(app) == [" ", " "]
        await pilot.press("space")
        assert checkbox_marks(app) == ["X", " "]
        await pilot.press("space")
        assert checkbox_marks(app) == [" ", " "]


async def test_settings_at_first_start_show_the_call_and_the_rest(no_call_app):
    app = no_call_app
    async with app.run_test() as pilot:
        await pilot.press("enter")
        assert app.focused.id == "station-callsign-input"
        assert setting_labels(app) == SETTING_LABELS


async def test_settings_saved_after_setup_keep_the_call(app, settings_path):
    async with app.run_test() as pilot:
        # Space toggles the focused checkbox (stock), Enter too.
        await pilot.press("f2", "space", "tab", "enter")
        await pilot.click("#save")
        assert not isinstance(app.screen, SettingsScreen)
        assert station_callsign(app) == "W1TST"
        expected = Settings(
            "W1TST",
            new_comment_pota_info=True,
            edit_comment_pota_info=True,
            adif_export_folder=exports(settings_path),
        )
        assert app.settings == expected
        assert load_settings(settings_path) == expected


async def test_settings_saved_at_first_start_with_the_call(no_call_app, settings_path):
    app = no_call_app
    async with app.run_test() as pilot:
        await pilot.press("enter", *"w1tst", "tab", "space")
        await pilot.click("#save")
        expected = Settings(
            "W1TST", new_comment_pota_info=True, adif_export_folder=exports(settings_path)
        )
        assert load_settings(settings_path) == expected


async def test_settings_after_setup_save_the_export_folder(app, settings_path, home):
    async with app.run_test() as pilot:
        await pilot.press("f2")
        assert str(app.screen.query_one("#folder-label", Label).render()) == "ADIF export folder"
        app.screen.query_one("#folder-input", Input).value = " ~/adif "
        await pilot.click("#save")
        assert not isinstance(app.screen, SettingsScreen)
        expected = Settings("W1TST", adif_export_folder="~/adif")
        assert app.settings == expected
        assert load_settings(settings_path) == expected


async def test_enter_in_the_export_folder_saves(app, settings_path, home):
    async with app.run_test() as pilot:
        await pilot.press("f2", "tab", "tab", *"~/adif", "enter")
        assert not isinstance(app.screen, SettingsScreen)
        assert load_settings(settings_path).adif_export_folder == "~/adif"


@pytest.mark.parametrize(
    "folder, problem",
    [
        ("~/deve/adif", "ADIF export folder '~/deve/adif' doesn't exist."),
        ("~/adif/notes.txt", "ADIF export folder '~/adif/notes.txt' isn't a folder."),
    ],
)
async def test_export_folder_must_exist(app, settings_path, home, folder, problem):
    # None is made: a typo would send files somewhere unexpected.
    (home / "adif" / "notes.txt").write_text("")
    async with app.run_test() as pilot:
        await pilot.press("f2")
        app.screen.query_one("#folder-input", Input).value = folder
        await pilot.click("#save")
        assert isinstance(app.screen, SettingsScreen)
        assert app.focused.id == "folder-input"
        assert folder_problem(app) == problem
        assert load_settings(settings_path).adif_export_folder == exports(settings_path)
    assert not (home / "deve").exists()


async def test_blank_export_folder_saves_as_the_default(settings_path):
    save_settings(Settings("W1TST", adif_export_folder="~/gone"), settings_path)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        await pilot.press("f2")
        app.screen.query_one("#folder-input", Input).value = ""
        await pilot.click("#save")
        assert not isinstance(app.screen, SettingsScreen)
        assert app.settings.adif_export_folder == exports(settings_path)
    assert load_settings(settings_path).adif_export_folder == exports(settings_path)
    assert (settings_path.parent.parent / "exports").is_dir()


async def test_first_start_makes_data_and_shows_the_default_export_folder(no_call_app, settings_path):
    exports_dir = settings_path.parent.parent / "exports"
    async with no_call_app.run_test() as pilot:
        assert exports_dir.is_dir()
        assert settings_path.parent.is_dir()
        assert not settings_path.exists()
        await pilot.press("enter")
        folder = no_call_app.screen.query_one("#folder-input", Input).value
        assert folder == exports(settings_path) == str(exports_dir)
        await pilot.press(*"w1tst", "enter")
    assert load_settings(settings_path).adif_export_folder == exports(settings_path)


async def test_blank_export_folder_in_file_is_set_to_the_default(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1TST"\n')
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert app.settings.adif_export_folder == exports(settings_path)
    assert load_settings(settings_path).adif_export_folder == exports(settings_path)
    assert (settings_path.parent.parent / "exports").is_dir()


async def test_default_export_folder_is_written_with_tilde_in_home(home):
    settings_path = home / ".local/share/pota-logger/data/settings.toml"
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert app.settings.adif_export_folder == "~/.local/share/pota-logger/exports"
    assert (home / ".local/share/pota-logger/exports").is_dir()


async def test_default_export_folder_once_set_isnt_made_again(settings_path):
    exports_dir = settings_path.parent.parent / "exports"
    save_settings(Settings("W1TST", adif_export_folder=str(exports_dir)), settings_path)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert app.settings.adif_export_folder == str(exports_dir)
    assert not exports_dir.exists()


async def test_export_folder_stays_unset_when_the_default_cant_be_made(settings_path):
    # A file in its place.
    save_settings(Settings("W1TST"), settings_path)
    (settings_path.parent.parent / "exports").write_text("")
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert app.settings.adif_export_folder == ""
    assert load_settings(settings_path).adif_export_folder == ""


async def test_non_ascii_default_export_folder_is_left_unset(tmp_path):
    settings_path = tmp_path / "T\u00e9l\u00e9" / "data" / "settings.toml"
    save_settings(Settings("W1TST"), settings_path)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert app.settings.adif_export_folder == ""
    assert not (settings_path.parent.parent / "exports").exists()


async def test_settings_open_with_the_export_folder(settings_path):
    save_settings(Settings("W1TST", adif_export_folder="~/adif"), settings_path)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        await pilot.press("f2")
        assert app.screen.query_one("#folder-input", Input).value == "~/adif"


async def test_non_ascii_export_folder_is_refused_below_it(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2")
        app.screen.query_one("#folder-input", Input).value = "~/T\u00e9l\u00e9chargements"
        await pilot.click("#save")
        assert isinstance(app.screen, SettingsScreen)
        assert app.focused.id == "folder-input"
        assert folder_problem(app) == (
            "ADIF export folder '~/T\u00e9l\u00e9chargements' has non-ASCII characters: '\u00e9'.\n"
            "Use plain ASCII, like ~/Downloads."
        )
        assert load_settings(settings_path).adif_export_folder == exports(settings_path)
        await pilot.press("backspace")
        assert folder_problem(app) == ""


async def test_settings_at_first_start_save_the_call_and_the_folder(
    no_call_app, settings_path, home
):
    app = no_call_app
    async with app.run_test() as pilot:
        await pilot.press("enter", *"w1tst", "tab", "tab", "tab", *"~/adif")
        await pilot.click("#save")
        assert load_settings(settings_path) == Settings("W1TST", adif_export_folder="~/adif")


async def test_first_start_refuses_a_bad_folder_after_a_good_call(no_call_app, settings_path):
    app = no_call_app
    async with app.run_test() as pilot:
        await pilot.press("enter", *"w1tst")
        app.screen.query_one("#folder-input", Input).value = "~/\u00e9"
        await pilot.click("#save")
        assert isinstance(app.screen, SettingsScreen)
        assert app.focused.id == "folder-input"
        assert folder_problem(app).startswith("ADIF export folder '~/\u00e9' has non-ASCII")
        assert not app.screen.query_one("#settings-problem", Static).has_class("-shown")
        assert not settings_path.exists()


async def test_spaces_around_the_export_folder_in_file_are_fixed(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1TST"\nadif_export_folder = " ~/adif "\n')
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert len(app.screen_stack) == 1
    assert 'adif_export_folder = "~/adif"\n' in settings_path.read_text()


async def test_bad_export_folder_in_file_blocks_for_fixing_by_hand(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1TST"\nadif_export_folder = 1\n')
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert app.screen.id == "file-errors"


async def test_settings_open_as_saved(settings_path):
    save_settings(Settings("W1TST", edit_comment_pota_info=True), settings_path)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        await pilot.press("f2")
        assert [box.value for box in app.screen.query(Checkbox)] == [False, True]


async def test_bad_setting_in_file_blocks_for_fixing_by_hand(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "w1tst"\nnew_comment_pota_info = "yes"\n')
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert app.screen.id == "file-errors"
        assert not app.settings.new_comment_pota_info
        errors = (settings_path.parent / "file_errors.txt").read_text()
        assert f"{settings_path}: new_comment_pota_info 'yes' must be true or false" in errors
    # Not saved with the call's case fixed, which would hide the problem.
    assert "w1tst" in settings_path.read_text()


async def test_f2_opens_modal_from_field(app):
    async with app.run_test() as pilot:
        await pilot.press("f2")
        assert isinstance(app.screen, SettingsScreen)


async def test_f2_does_not_stack_modals(app):
    async with app.run_test() as pilot:
        await pilot.press("f2", "f2")
        assert len(app.screen_stack) == 2


async def test_save_uppercases_updates_status_and_file(no_call_app, settings_path):
    app = no_call_app
    async with app.run_test() as pilot:
        await pilot.press("enter", *"w1abc", "enter")
        assert not isinstance(app.screen, SettingsScreen)
        assert station_callsign(app) == "W1ABC"
        expected = Settings("W1ABC", adif_export_folder=exports(settings_path))
        assert load_settings(settings_path) == expected


async def test_save_button_saves(no_call_app, settings_path):
    app = no_call_app
    async with app.run_test() as pilot:
        await pilot.press("enter")
        app.screen.query_one("#station-callsign-input", Input).value = "W1ABC"
        await pilot.click("#save")
        expected = Settings("W1ABC", adif_export_folder=exports(settings_path))
        assert load_settings(settings_path) == expected


async def test_invalid_station_callsign_is_refused(no_call_app, settings_path):
    app = no_call_app
    async with app.run_test() as pilot:
        await pilot.press("enter", *"w1tst/", "enter")
        assert isinstance(app.screen, SettingsScreen)
        assert app.focused.id == "station-callsign-input"
        assert settings_problem(app) == "Station callsign 'w1tst/' has an empty part next to a /"
        assert not app._notifications
        assert not settings_path.exists()
        # Gone once the call is edited.
        await pilot.press("backspace")
        assert settings_problem(app) is None


async def test_settings_open_with_no_problem_shown(no_call_app):
    app = no_call_app
    async with app.run_test() as pilot:
        await pilot.press("enter")
        assert settings_problem(app) is None


async def test_non_ascii_station_callsign_is_refused(app, settings_path):
    async with app.run_test() as pilot:
        app.push_screen(SettingsScreen(Settings()))
        await pilot.pause()
        app.screen.query_one("#station-callsign-input", Input).value = "W1ABÇ"
        await pilot.press("enter")
        assert isinstance(app.screen, SettingsScreen)
        assert settings_problem(app) == (
            "Station callsign 'W1ABÇ' has non-ASCII characters: 'Ç'.\n"
            "Use plain ASCII, like W1ABC."
        )
        expected = Settings("W1TST", adif_export_folder=exports(settings_path))
        assert load_settings(settings_path) == expected


async def test_blank_station_callsign_saves_and_asks_for_one(no_call_app, settings_path):
    app = no_call_app
    async with app.run_test() as pilot:
        await pilot.press("enter")
        app.screen.query_one("#station-callsign-input", Input).value = "  "
        await pilot.press("enter")
        assert app.screen.id == "station-callsign-required"
        assert station_callsign(app) == "NOCALL"
        expected = Settings("", adif_export_folder=exports(settings_path))
        assert load_settings(settings_path) == expected
        await pilot.press("enter")
        assert isinstance(app.screen, SettingsScreen)


async def test_unusual_station_callsign_warns_and_enter_saves(no_call_app, settings_path):
    app = no_call_app
    async with app.run_test() as pilot:
        await open_settings_with(app, pilot, "w111111ab")
        assert isinstance(app.screen, CallsignWarningScreen)
        message = str(app.screen.query_one("#callsign-warning-message", Static).render())
        assert message.startswith("W111111AB is an unusual callsign.")
        await pilot.press("enter")
        assert not isinstance(app.screen, (CallsignWarningScreen, SettingsScreen))
        assert station_callsign(app) == "W111111AB"
        expected = Settings("W111111AB", adif_export_folder=exports(settings_path))
        assert load_settings(settings_path) == expected


async def test_unusual_station_callsign_escape_returns_to_settings(no_call_app, settings_path):
    app = no_call_app
    async with app.run_test() as pilot:
        await open_settings_with(app, pilot, "W11BC")
        await pilot.press("escape")
        assert isinstance(app.screen, SettingsScreen)
        assert app.focused.id == "station-callsign-input"
        assert app.focused.value == "W11BC"
        assert not settings_path.exists()


async def test_unusual_station_callsign_corrected_in_warning(no_call_app, settings_path):
    app = no_call_app
    async with app.run_test() as pilot:
        await open_settings_with(app, pilot, "W11BC")
        app.screen.query_one("#callsign-warning-input", Input).value = "W1ÅBC"
        await pilot.press("enter")
        assert [n.message for n in app._notifications] == [
            "Station callsign 'W1ÅBC' has non-ASCII characters: 'Å'.\n"
            "Use plain ASCII, like W1ABC."
        ]
        app.screen.query_one("#callsign-warning-input", Input).value = "w1abc"
        await pilot.press("enter")
        expected = Settings("W1ABC", adif_export_folder=exports(settings_path))
        assert load_settings(settings_path) == expected


async def test_f2_over_station_callsign_warning_does_not_stack(no_call_app):
    app = no_call_app
    async with app.run_test() as pilot:
        await open_settings_with(app, pilot, "W11BC")
        await pilot.press("f2")
        assert isinstance(app.screen, CallsignWarningScreen)
        assert sum(isinstance(s, SettingsScreen) for s in app.screen_stack) == 1


async def test_escape_cancels_without_saving(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2", "space", "escape")
        assert not isinstance(app.screen, SettingsScreen)
        expected = Settings("W1TST", adif_export_folder=exports(settings_path))
        assert app.settings == expected
        assert load_settings(settings_path) == expected


async def test_cancel_button_cancels(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2", "space")
        await pilot.click("#cancel")
        expected = Settings("W1TST", adif_export_folder=exports(settings_path))
        assert app.settings == expected
        assert load_settings(settings_path) == expected


async def test_closing_modal_keeps_entry_in_progress(app):
    async with app.run_test() as pilot:
        await pilot.press(*"14.074", "f2", "escape")
        assert app.focused.id == "field-freq"
        assert app.query_one("#field-freq", Input).value == "14.074"


async def test_broken_settings_file_is_shown_in_the_required_block(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1TST\n')
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        assert station_callsign(app) == "NOCALL"
        assert app.screen.id == "station-callsign-required"
        assert not app._notifications
        message = required_message(app)
        assert message.startswith(
            "A valid callsign for transmitting\nstation is required.\n\n"
            f"Couldn't read {settings_path}: "
        )
        assert message.endswith("\n\nPress Enter to go to Settings.")
        # Saving Settings rewrites the file, so it's not shown again.
        await pilot.press("enter", "enter")
        assert app.screen.id == "station-callsign-required"
        assert required_message(app) == (
            "A valid callsign for transmitting\nstation is required.\n"
            "Press Enter to go to Settings."
        )


async def test_bad_station_callsign_in_file_is_reported_and_shown_to_fix(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1"\n')
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        assert station_callsign(app) == "NOCALL"
        assert app.screen.id == "station-callsign-required"
        assert not app._notifications
        problem = (
            f"{settings_path}: station_callsign 'W1' doesn't look like a callsign, like W1ABC"
        )
        assert required_message(app) == (
            "A valid callsign for transmitting\nstation is required.\n\n"
            f"{problem}\n\nPress Enter to go to Settings."
        )
        # In Settings to correct, with the problem shown only on Save, and
        # back to the block (still showing it) if cancelled.
        await pilot.press("enter")
        assert app.focused.value == "W1"
        assert settings_problem(app) is None
        await pilot.press("enter")
        assert settings_problem(app) == (
            "Station callsign 'W1' doesn't look like a callsign, like W1ABC"
        )
        await pilot.press("escape")
        assert problem in required_message(app)
        await pilot.press("enter")
        assert app.focused.value == "W1"
        await pilot.press("end", *"TST", "enter")
        # Then the parks list is offered (skipped here).
        assert isinstance(app.screen, ParksOfferScreen)
        await pilot.press("escape")
        assert len(app.screen_stack) == 1
        expected = Settings("W1TST", adif_export_folder=exports(settings_path))
        assert load_settings(settings_path) == expected


@pytest.mark.parametrize("call", ["w1tst", " W1TST "])
async def test_how_the_station_callsign_in_file_is_written_is_fixed(settings_path, call):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(f'station_callsign = "{call}"\n')
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert station_callsign(app) == "W1TST"
        assert len(app.screen_stack) == 1
    assert settings_path.read_text() == (
        'station_callsign = "W1TST"\n'
        "new_comment_pota_info = false\n"
        "edit_comment_pota_info = false\n"
        f'adif_export_folder = "{exports(settings_path)}"\n'
    )
