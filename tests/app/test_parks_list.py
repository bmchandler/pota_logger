"""POTA's parks list: the download, and what the app does with it."""

import pytest
from textual.widgets import Button, Input

from pota_logger.app import PotaLoggerApp
from pota_logger.parks_list import download_parks, md5_etag, parks_folder
from pota_logger.screens.parks_offer_screen import ParksOfferScreen
from pota_logger.screens.settings_screen import SettingsScreen
from pota_logger.screens.warning_screen import WarningScreen
from pota_logger.settings import Settings, save_settings

from tests.app.helpers import (
    BROKEN_ROW,
    ENTRY,
    LOG_HEADER,
    exported_files,
    fill,
    first_start,
    last_notification,
    leave_park,
    park_name,
    parks_list_done,
    parks_list_row,
    required_message,
    save_parks_list,
    select_row,
    st_value,
    table_calls,
    table_rows,
)
from tests.conftest import LIST


async def test_first_start_offers_parks_list_and_downloads_with_enter(settings_path, pota):
    app = PotaLoggerApp(settings_path=settings_path)
    app.parks_url = pota.url
    async with app.run_test() as pilot:
        await first_start(app, pilot)
        assert isinstance(app.screen, ParksOfferScreen)
        assert required_message(app) == (
            "Download POTA's parks list (about 9 MB)?\n"
            "It lets the app fill in ST, show park names,\n"
            "and warn on a park not in the list.\n"
            "You can download it later in Settings (f2).\n"
            "Esc to skip, or download with Enter."
        )
        assert [b.label.plain for b in app.screen.query(Button)] == ["Skip", "Download"]
        await pilot.press("enter")
        assert len(app.screen_stack) == 1
        await parks_list_done(app, pilot)
        assert [n.message for n in app._notifications] == [
            "Downloading POTA's parks list...",
            "Parks list downloaded.",
        ]
    assert (settings_path.parent / "pota" / "all_parks_ext.csv").read_bytes() == LIST


async def test_parks_offer_skipped_with_esc(settings_path, pota):
    app = PotaLoggerApp(settings_path=settings_path)
    app.parks_url = pota.url
    async with app.run_test() as pilot:
        await first_start(app, pilot)
        await pilot.press("escape")
        assert len(app.screen_stack) == 1
        assert app.focused.id == "field-freq"
        assert not app._notifications
    assert pota.requests == []


async def test_no_parks_offer_with_a_copy_saved(settings_path, pota):
    download_parks(parks_folder(settings_path.parent), pota.url)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        await first_start(app, pilot)
        assert len(app.screen_stack) == 1


async def test_no_parks_offer_over_file_errors_block(settings_path):
    (settings_path.parent).mkdir(parents=True)
    (settings_path.parent / "20260925.csv").write_text(LOG_HEADER + BROKEN_ROW)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        await first_start(app, pilot)
        assert app.screen.id == "file-errors"
        assert len(app.screen_stack) == 2


async def test_no_parks_offer_once_a_call_is_set(app):
    async with app.run_test():
        assert len(app.screen_stack) == 1


async def test_first_time_settings_have_no_parks_list(no_call_app):
    async with no_call_app.run_test() as pilot:
        await pilot.press("enter")
        assert isinstance(no_call_app.screen, SettingsScreen)
        assert not no_call_app.screen.query("#parks-row")


async def test_settings_check_for_updated_downloads_parks_list(app, pota):
    app.parks_url = pota.url
    async with app.run_test() as pilot:
        await pilot.press("f2")
        assert parks_list_row(app) == "POTA parks list: none"
        button = app.screen.query_one("#check-parks", Button)
        assert button.label.plain == "Check for Updated"
        button.focus()
        await pilot.press("enter")
        await parks_list_done(app, pilot)
        assert last_notification(app) == "Parks list downloaded."
        assert parks_list_row(app) == "POTA parks list: 2026.10.09"
        # Settings stays open, and the date is there when next opened.
        await pilot.press("escape", "f2")
        assert parks_list_row(app) == "POTA parks list: 2026.10.09"


async def test_settings_check_for_updated_with_current_copy(app, settings_path, pota):
    download_parks(parks_folder(settings_path.parent), pota.url)
    app.parks_url = pota.url
    async with app.run_test() as pilot:
        await pilot.press("f2")
        app.screen.query_one("#check-parks", Button).press()
        await parks_list_done(app, pilot)
        assert last_notification(app) == "Parks file is already current."
        assert pota.requests[-1]["If-None-Match"] == md5_etag(LIST)


async def test_settings_check_for_updated_failure_is_notified(app, settings_path, pota):
    download_parks(parks_folder(settings_path.parent), pota.url)
    pota.status = 503
    app.parks_url = pota.url
    async with app.run_test() as pilot:
        await pilot.press("f2")
        app.screen.query_one("#check-parks", Button).press()
        await parks_list_done(app, pilot)
        assert last_notification(app) == (
            "Parks list download failed: the server replied 503."
        )
        assert list(app._notifications)[-1].severity == "error"
        assert parks_list_row(app) == "POTA parks list: 2026.10.09"


async def test_parks_list_check_not_doubled(app, pota):
    app.parks_url = pota.url
    async with app.run_test() as pilot:
        app.check_parks_list()
        app.check_parks_list()
        await parks_list_done(app, pilot)
        assert len(pota.requests) == 1


# The park's name, on COMMENT's label row, from the parks list.


async def test_park_name_shows_on_leaving_park(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        assert park_name(app) == ""
        await leave_park(app, pilot, "1")
        assert park_name(app) == "Acadia National Park"
        await leave_park(app, pilot, "us-2")
        assert park_name(app) == "Alagnak Wild River National Park"


@pytest.mark.parametrize("text", ["9999", "12x", "", "JP-0001"])
async def test_no_park_name_for_a_park_not_read_or_listed(parks_app, text):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        await leave_park(app, pilot, "1")
        await leave_park(app, pilot, text)
        assert park_name(app) == ""


async def test_park_name_on_enter_in_park(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        app.query_one("#field-park", Input).value = "1"
        app.query_one("#field-park", Input).focus()
        # Stopped by the missing fields, still in PARK.
        await pilot.press("enter")
        assert park_name(app) == "Acadia National Park"


async def test_park_name_cleared_after_save(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        fill(app, ENTRY | {"PARK": "1", "ST": "ME"})
        await pilot.press("enter")
        assert table_calls(app) == ["W1ABC"]
        assert park_name(app) == ""


async def test_park_name_for_a_selected_row_then_back_to_the_form(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        fill(app, ENTRY | {"PARK": "1", "ST": "ME"})
        await pilot.press("enter")
        await leave_park(app, pilot, "2")
        assert park_name(app) == "Alagnak Wild River National Park"
        await select_row(app, pilot, 0)
        assert park_name(app) == "Acadia National Park"
        await pilot.press("escape")
        assert park_name(app) == "Alagnak Wild River National Park"


async def test_park_name_once_the_list_is_downloaded(app, pota):
    app.parks_url = pota.url
    async with app.run_test() as pilot:
        await leave_park(app, pilot, "1")
        assert park_name(app) == ""
        app.check_parks_list()
        await parks_list_done(app, pilot)
        # The names load in a thread of their own, once it's saved.
        await parks_list_done(app, pilot)
        assert park_name(app) == "Acadia National Park"


# ST filled from the park, and the parks list's warnings.


async def test_st_filled_on_leaving_park_and_typing_replaces_it(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        await leave_park(app, pilot, "1")
        assert st_value(app) == "ME"
        assert app.focused.id == "field-st"
        await pilot.press("n", "h")
        assert st_value(app) == "nh"


async def test_filled_st_follows_park(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        await leave_park(app, pilot, "1")
        assert st_value(app) == "ME"
        await leave_park(app, pilot, "2")
        assert st_value(app) == "AK"
        # A park in two states, or one not read or listed, clears it.
        await leave_park(app, pilot, "3")
        assert st_value(app) == ""
        await leave_park(app, pilot, "1")
        await leave_park(app, pilot, "9999")
        assert st_value(app) == ""


async def test_typed_st_isnt_changed(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        app.query_one("#field-st", Input).value = "NH"
        await leave_park(app, pilot, "1")
        assert st_value(app) == "NH"


async def test_st_typed_over_the_filled_one_isnt_changed(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        await leave_park(app, pilot, "1")
        await pilot.press("n", "h")
        await leave_park(app, pilot, "2")
        assert st_value(app) == "nh"


async def test_st_filled_on_enter_in_park(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        app.query_one("#field-park", Input).value = "1"
        app.query_one("#field-park", Input).focus()
        await pilot.press("enter")
        assert st_value(app) == "ME"


async def test_no_st_filled_without_a_list(app):
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        await leave_park(app, pilot, "1")
        assert st_value(app) == ""


async def test_filled_st_in_comments_pota_info(settings_path, pota):
    save_settings(Settings("W1TST", new_comment_pota_info=True), settings_path)
    save_parks_list(settings_path, pota)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        await leave_park(app, pilot, "1")
        assert app.query_one("#field-comment", Input).value == "POTA US-0001 ME"


async def test_st_filled_for_a_blank_st_when_editing(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        fill(app, ENTRY | {"PARK": "3", "ST": ""})
        await pilot.press("enter")
        await select_row(app, pilot, 0)
        await pilot.press("f3")
        await leave_park(app, pilot, "2")
        assert st_value(app) == "AK"


async def test_selected_row_and_back_keep_the_fill(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        fill(app, ENTRY | {"PARK": "3", "ST": ""})
        await pilot.press("enter")
        await leave_park(app, pilot, "1")
        await select_row(app, pilot, 0)
        assert st_value(app) == ""
        await pilot.press("escape")
        # Back to the form's own, still the app's to change.
        assert st_value(app) == "ME"
        await leave_park(app, pilot, "2")
        assert st_value(app) == "AK"


async def test_park_not_listed_warns_and_esc_goes_to_park(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        fill(app, ENTRY | {"PARK": "9999", "ST": ""})
        await pilot.press("enter")
        assert isinstance(app.screen, WarningScreen)
        assert required_message(app).startswith("US-9999 isn't in POTA's parks list.\n")
        await pilot.press("escape")
        assert app.focused.id == "field-park"
        assert table_rows(app) == []


async def test_inactive_park_warns_and_enter_saves(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        fill(app, ENTRY | {"PARK": "4", "ST": "ME"})
        await pilot.press("enter")
        assert required_message(app).startswith("US-0004 is inactive in POTA's parks list.\n")
        await pilot.press("enter")
        assert table_calls(app) == ["W1ABC"]


async def test_state_not_the_parks_warns_and_esc_goes_to_st(parks_app):
    app = parks_app
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        fill(app, ENTRY | {"PARK": "3", "ST": "NJ"})
        await pilot.press("enter")
        assert required_message(app) == (
            "US-0003 is in DC or MD, not NJ.\nEsc to correct, or confirm with Enter."
        )
        await pilot.press("escape")
        assert app.focused.id == "field-st"


async def test_no_park_warnings_without_a_list(app):
    async with app.run_test() as pilot:
        await parks_list_done(app, pilot)
        fill(app, ENTRY | {"PARK": "9999"})
        await pilot.press("enter")
        assert table_calls(app) == ["W1ABC"]


async def test_export_takes_dxcc_and_location_from_the_parks_list(
    export_app, settings_path, export_folder, pota
):
    save_parks_list(settings_path, pota)
    async with export_app.run_test() as pilot:
        await parks_list_done(export_app, pilot)
        fill(export_app, ENTRY | {"PARK": "2", "ST": "AK", "DATE": "260925"})
        await pilot.press("enter")
        fill(export_app, ENTRY | {"CALL": "W1XYZ", "PARK": "1", "ST": "ME", "DATE": "260925"})
        await pilot.press("enter")
        fill(export_app, ENTRY | {"CALL": "K1ABC", "PARK": "3", "ST": "MD", "DATE": "260925"})
        await pilot.press("enter")
        await pilot.press("f6")
        await pilot.press("enter")
    [exported] = exported_files(export_folder)
    records = exported.read_text().splitlines()[6:]
    assert ["<DXCC:1>6" in records[0], "<DXCC:3>291" in records[1]] == [True, True]
    # A park in several states takes ST as its location in POTA_REF.
    assert "<POTA_REF:7>US-0001 " in records[1]
    assert "<POTA_REF:13>US-0003@US-MD " in records[2]
    assert "<SIG_INFO:7>US-0003 " in records[2]
