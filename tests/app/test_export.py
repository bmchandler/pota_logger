"""The ADIF export."""

import re

import pytest
from textual.containers import Vertical
from textual.widgets import Input, Static

from pota_logger.app import PotaLoggerApp
from pota_logger.fields import dates
from pota_logger.screens.export_screen import ExportScreen
from pota_logger.screens.settings_screen import SettingsScreen
from pota_logger.settings import Settings, save_settings

from tests.app.helpers import (
    ENTRY,
    K1AAA_ROW,
    LOG_HEADER,
    THREE_DAYS,
    export_problem,
    export_range,
    exported_files,
    fill,
    write_refused,
    write_saved_log,
)


async def test_f6_opens_export_on_the_latest_date_logged(export_app, settings_path, export_folder):
    # The folder isn't shown: it's set and seen in Settings.
    write_saved_log(settings_path, THREE_DAYS)
    async with export_app.run_test() as pilot:
        await pilot.press("f6")
        assert isinstance(app_screen := export_app.screen, ExportScreen)
        assert export_range(export_app) == ("260926", "260926")
        assert str(export_folder) not in str(export_app.screen.query_one(Vertical).render())
        assert export_app.focused.id == "export-from"
        assert app_screen.query_one("#export-problem", Static).has_class("-shown") is False


async def test_adif_button_opens_export(export_app):
    async with export_app.run_test() as pilot:
        await pilot.click("#adif")
        assert isinstance(export_app.screen, ExportScreen)


async def test_export_range_defaults_to_this_sessions_dates(export_app, settings_path):
    write_saved_log(settings_path, THREE_DAYS)
    async with export_app.run_test() as pilot:
        fill(export_app, ENTRY | {"DATE": "260927"})
        await pilot.press("enter")
        fill(export_app, ENTRY | {"CALL": "W1XYZ", "DATE": "260920"})
        await pilot.press("enter")
        await pilot.press("f6")
        assert export_range(export_app) == ("260920", "260927")


async def test_export_range_with_nothing_logged_is_todays_local_date(export_app):
    async with export_app.run_test() as pilot:
        await pilot.press("f6")
        assert export_range(export_app) == (dates.default_date(), dates.default_date())


async def test_esc_closes_export(export_app, export_folder):
    async with export_app.run_test() as pilot:
        await pilot.press("f6", "escape")
        assert not isinstance(export_app.screen, ExportScreen)
    assert not exported_files(export_folder)


async def test_export_writes_the_range_in_time_order(export_app, settings_path, export_folder):
    write_saved_log(settings_path, THREE_DAYS)
    async with export_app.run_test() as pilot:
        await pilot.press("f6")
        export_app.screen.query_one("#export-from", Input).value = "260925"
        await pilot.press("enter")
        assert not isinstance(export_app.screen, ExportScreen)
        assert [n.message for n in export_app._notifications] == ["ADIF export complete."]
    [exported] = exported_files(export_folder)
    assert re.fullmatch(r"pota_\d{14}_20260925_20260926\.adi", exported.name)
    lines = exported.read_text().splitlines()
    assert lines[0] == "POTA Logger ADIF export"
    assert lines[5] == "<EOH>"
    records = lines[6:]
    assert [record.split("<CALL:")[1].split(">")[1].split(" ")[0] for record in records] == [
        "K1BBB",
        "W1CCC",
        "N1DDD",
    ]
    assert records[0].startswith("<QSO_DATE:8>20260925 <TIME_ON:4>0100 <CALL:5>K1BBB <BAND:3>20m")
    assert all(record.endswith("<EOR>") for record in records)


async def test_export_expands_home(settings_path, home):
    save_settings(Settings("W1TST", adif_export_folder="~/adif"), settings_path)
    write_saved_log(settings_path, THREE_DAYS)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        await pilot.press("f6", "enter")
    assert len(exported_files(home / "adif")) == 1


async def test_export_into_a_folder_gone_since_says_why(settings_path, tmp_path):
    # Saved while it existed, then removed: export doesn't make it again.
    gone = tmp_path / "gone"
    save_settings(Settings("W1TST", adif_export_folder=str(gone)), settings_path)
    write_saved_log(settings_path, THREE_DAYS)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        await pilot.press("f6", "enter")
        assert isinstance(app.screen, ExportScreen)
        first, error = export_problem(app).split("\n", 1)
        assert first == "Export error: Couldn't write the file."
        assert str(gone) in error
    assert not gone.exists()


async def test_export_without_a_folder_says_to_set_one(settings_path):
    # None set, as the default can't be made: a file is in its place.
    save_settings(Settings("W1TST"), settings_path)
    (settings_path.parent.parent / "exports").write_text("")
    app = PotaLoggerApp(settings_path=settings_path)
    write_saved_log(settings_path, THREE_DAYS)
    async with app.run_test() as pilot:
        await pilot.press("f6")
        await pilot.press("enter")
        assert isinstance(app.screen, ExportScreen)
        assert export_problem(app) == (
            "Export error: No ADIF export folder set.\nSet one in Settings (F2)."
        )


async def test_folder_set_from_export_with_f2_is_used(app, settings_path, export_folder):
    write_saved_log(settings_path, THREE_DAYS)
    async with app.run_test() as pilot:
        await pilot.press("f6", "f2")
        assert isinstance(app.screen, SettingsScreen)
        app.screen.query_one("#folder-input", Input).value = str(export_folder)
        await pilot.click("#save")
        assert isinstance(app.screen, ExportScreen)
        await pilot.press("enter")
        assert not isinstance(app.screen, ExportScreen)
    assert len(exported_files(export_folder)) == 1


async def test_export_waits_for_a_clean_log(export_app, settings_path, export_folder):
    # Two rows sharing a record ID are marked U.
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    (settings_path.parent / "20260925.csv").write_text(
        LOG_HEADER + K1AAA_ROW + K1AAA_ROW.replace("K1AAA", "K1BBB")
    )
    async with export_app.run_test() as pilot:
        await pilot.press("f6", "enter")
        assert isinstance(export_app.screen, ExportScreen)
        assert export_problem(export_app) == (
            "Export error: Rows are marked !, U, or =.\nResolve and try again."
        )
    assert not exported_files(export_folder)


async def test_export_waits_for_a_clean_log_outside_the_range(export_app, settings_path):
    write_refused(settings_path)
    async with export_app.run_test() as pilot:
        await pilot.press("f6")
        assert export_range(export_app) == ("260926", "260926")
        await pilot.press("enter")
        assert export_problem(export_app).startswith("Export error: Rows are marked")


@pytest.mark.parametrize(
    "start, end, problem, focused",
    [
        ("2610", "260925", "From '2610' should be YYMMDD, like 260923", "export-from"),
        ("260925", "261332", "To '261332' isn't a real date", "export-to"),
        ("260926", "260925", "From 260926 is after To 260925", "export-from"),
        (
            "\uff12\uff16\uff10\uff19\uff12\uff15",
            "260925",
            "From '\uff12\uff16\uff10\uff19\uff12\uff15' has non-ASCII characters: "
            "'\uff12', '\uff16', '\uff10', '\uff19', '\uff15'.\nUse plain ASCII, like 260923.",
            "export-from",
        ),
    ],
)
async def test_bad_export_dates_are_refused(export_app, settings_path, start, end, problem, focused):
    write_saved_log(settings_path, THREE_DAYS)
    async with export_app.run_test() as pilot:
        await pilot.press("f6")
        export_app.screen.query_one("#export-from", Input).value = start
        export_app.screen.query_one("#export-to", Input).value = end
        await pilot.click("#export")
        assert export_problem(export_app) == problem
        assert export_app.focused.id == focused
        await pilot.press("backspace")
        assert export_problem(export_app) == ""


async def test_export_of_an_empty_range_is_refused(export_app, settings_path, export_folder):
    write_saved_log(settings_path, THREE_DAYS)
    async with export_app.run_test() as pilot:
        await pilot.press("f6")
        export_app.screen.query_one("#export-from", Input).value = "261001"
        export_app.screen.query_one("#export-to", Input).value = "261009"
        await pilot.press("enter")
        assert export_problem(export_app) == "Export error: No logs in date range."
    assert not exported_files(export_folder)


async def test_export_that_cant_be_written_says_why(settings_path, tmp_path):
    # The folder's path is now a file.
    export_folder = tmp_path / "adif"
    export_folder.write_text("not a folder")
    save_settings(Settings("W1TST", adif_export_folder=str(export_folder)), settings_path)
    write_saved_log(settings_path, THREE_DAYS)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        await pilot.press("f6", "enter")
        assert isinstance(app.screen, ExportScreen)
        first, error = export_problem(app).split("\n", 1)
        assert first == "Export error: Couldn't write the file."
        assert str(export_folder) in error


async def test_f6_doesnt_open_export_over_another_modal(export_app):
    async with export_app.run_test() as pilot:
        await pilot.press("f2", "f6")
        assert isinstance(export_app.screen, SettingsScreen)
        assert len(export_app.screen_stack) == 2
