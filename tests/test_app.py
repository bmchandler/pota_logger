from textual.widgets import DataTable, Input, Static

from pota_logger_t3 import PotaLoggerApp
from pota_logger_t3.entry_form import FIELDS
from pota_logger_t3.settings import Settings, load_settings, save_settings
from pota_logger_t3.settings_screen import SettingsScreen


def station_callsign(app) -> str:
    return str(app.query_one("#station-callsign", Static).render())


# Layout


async def test_focus_starts_on_freq(app):
    async with app.run_test():
        assert app.focused.id == "field-freq"


async def test_tab_order_follows_paper_log_then_table(app):
    async with app.run_test():
        chain = [w.id for w in app.screen.focus_chain]
        assert chain == [f"field-{name.lower()}" for name, _, _ in FIELDS] + ["log-table"]


async def test_log_table_columns_match_fields(app):
    async with app.run_test():
        table = app.query_one("#log-table", DataTable)
        assert [str(c.label) for c in table.columns.values()] == [n for n, _, _ in FIELDS]


async def test_fields_fit_longest_expected_values(app):
    longest = {
        "FREQ": "14.074.55",
        "MODE": "SSB",
        "CALL": "VE3/W1ABC/P",
        "PARK": "US-10123",
        "ST": "NJ",
        "SNT": "599",
        "RCD": "599",
        "PWR": "100W",
        "TIME": "1953",
    }
    async with app.run_test(size=(100, 24)):
        for name, value in longest.items():
            field = app.query_one(f"#field-{name.lower()}", Input)
            # +1 for the cursor
            assert field.content_region.width >= len(value) + 1, name


# Quitting


async def test_q_types_into_field_instead_of_quitting(app):
    async with app.run_test() as pilot:
        await pilot.press("q")
        assert app.query_one("#field-freq", Input).value == "q"
        assert app.return_code is None


async def test_ctrl_q_quits_from_field(app):
    async with app.run_test() as pilot:
        await pilot.press("ctrl+q")
        assert app.return_code == 0


async def test_quit_button_quits(app):
    async with app.run_test() as pilot:
        await pilot.click("#quit")
        assert app.return_code == 0


async def test_buttons_not_focusable(app):
    async with app.run_test():
        assert not app.query_one("#quit").can_focus
        assert not app.query_one("#settings").can_focus


# Settings


async def test_no_settings_file_shows_placeholder(app):
    async with app.run_test():
        assert station_callsign(app) == "NOCALL"


async def test_loads_saved_callsign(settings_path):
    save_settings(Settings(station_callsign="W1TST"), settings_path)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert station_callsign(app) == "W1TST"


async def test_settings_button_opens_modal(app):
    async with app.run_test() as pilot:
        await pilot.click("#settings")
        assert isinstance(app.screen, SettingsScreen)
        assert app.focused.id == "station-callsign-input"


async def test_f2_opens_modal_from_field(app):
    async with app.run_test() as pilot:
        await pilot.press("f2")
        assert isinstance(app.screen, SettingsScreen)


async def test_f2_does_not_stack_modals(app):
    async with app.run_test() as pilot:
        await pilot.press("f2", "f2")
        assert len(app.screen_stack) == 2


async def test_save_uppercases_updates_status_and_file(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2", *"w1tst", "enter")
        assert not isinstance(app.screen, SettingsScreen)
        assert station_callsign(app) == "W1TST"
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


async def test_save_button_saves(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2", *"w1tst")
        await pilot.click("#save")
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


async def test_escape_cancels_without_saving(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2", *"w1tst", "escape")
        assert not isinstance(app.screen, SettingsScreen)
        assert station_callsign(app) == "NOCALL"
        assert not settings_path.exists()


async def test_cancel_button_cancels(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2", *"w1tst")
        await pilot.click("#cancel")
        assert station_callsign(app) == "NOCALL"
        assert not settings_path.exists()


async def test_closing_modal_keeps_entry_in_progress(app):
    async with app.run_test() as pilot:
        await pilot.press(*"14.074", "f2", "escape")
        assert app.focused.id == "field-freq"
        assert app.query_one("#field-freq", Input).value == "14.074"


async def test_broken_settings_file_notifies_and_keeps_running(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1TST\n')
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert station_callsign(app) == "NOCALL"
        messages = [n.message for n in app._notifications]
        assert len(messages) == 1
        assert str(settings_path) in messages[0]
