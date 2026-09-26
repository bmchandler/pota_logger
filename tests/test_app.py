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
        "DATE": "260925",
        "TIME": "1953",
    }
    async with app.run_test(size=(120, 24)):
        for name, value in longest.items():
            field = app.query_one(f"#field-{name.lower()}", Input)
            # +1 for the cursor
            assert field.content_region.width >= len(value) + 1, name


# Entering a record

ENTRY = {
    "FREQ": "14.074.5",
    "MODE": "USB",
    "CALL": "W1ABC",
    "PARK": "1234",
    "ST": "NJ",
    "SNT": "59",
    "RCD": "57",
    "PWR": "60W",
    "DATE": "260925",
    "TIME": "1953",
}

# ENTRY as it appears in the log table.
ENTRY_ROW = list((ENTRY | {"FREQ": "14.074.500", "DATE": "2026.09.25"}).values())


def fill(app, values: dict[str, str]) -> None:
    for name, value in values.items():
        app.query_one(f"#field-{name.lower()}", Input).value = value


def field_values(app) -> dict[str, str]:
    return {name: app.query_one(f"#field-{name.lower()}", Input).value for name, _, _ in FIELDS}


def table_rows(app) -> list[list[str]]:
    table = app.query_one("#log-table", DataTable)
    return [[str(cell) for cell in table.get_row_at(i)] for i in range(table.row_count)]


async def test_mode_starts_as_ssb(app):
    async with app.run_test():
        assert app.query_one("#field-mode", Input).value == "SSB"


async def test_enter_adds_row_in_field_order(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        await pilot.press("enter")
        assert table_rows(app) == [ENTRY_ROW]


async def test_typed_entry_with_tab_between_fields(app):
    async with app.run_test() as pilot:
        # Tabbing into MODE selects the SSB default, so typing replaces it.
        for value in ENTRY.values():
            await pilot.press(*value, "tab")
        await pilot.press("shift+tab", "enter")  # back onto TIME, then Enter
        assert table_rows(app) == [ENTRY_ROW]


async def test_enter_works_from_any_field(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        app.query_one("#field-call", Input).focus()
        await pilot.press("enter")
        assert len(table_rows(app)) == 1


async def test_entry_values_are_trimmed(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "  W1ABC "})
        await pilot.press("enter")
        assert table_rows(app)[0][2] == "W1ABC"


async def test_after_entry_fields_reset_except_power_and_date(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        app.query_one("#field-time", Input).focus()
        await pilot.press("enter")
        expected = {name: "" for name in ENTRY} | {"MODE": "SSB", "PWR": "60W", "DATE": "260925"}
        assert field_values(app) == expected
        assert app.focused.id == "field-freq"


async def test_entries_append_in_entered_order(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"TIME": "2000"})
        await pilot.press("enter")
        fill(app, ENTRY | {"TIME": "1900"})
        await pilot.press("enter")
        assert [row[-1] for row in table_rows(app)] == ["2000", "1900"]


async def test_missing_fields_block_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "", "TIME": " "})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-call"
        assert [n.message for n in app._notifications] == ["Missing: CALL, TIME"]
        # Nothing was cleared.
        assert field_values(app)["FREQ"] == "14.074.5"


async def test_freq_shown_in_full_in_table(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"FREQ": "14"})
        await pilot.press("enter")
        fill(app, ENTRY | {"FREQ": "14074"})
        await pilot.press("enter")
        fill(app, ENTRY | {"FREQ": "14.0745"})
        await pilot.press("enter")
        fill(app, ENTRY | {"FREQ": "28312456"})
        await pilot.press("enter")
        assert [row[0] for row in table_rows(app)] == [
            "14.000.000",
            "14.074.000",
            "14.074.500",
            "28.312.456",
        ]


async def test_invalid_freq_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"FREQ": "14.07.45"})
        app.query_one("#field-time", Input).focus()
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-freq"
        assert len(app._notifications) == 1
        assert "14.07.45" in next(iter(app._notifications)).message
        # Nothing was cleared.
        assert field_values(app)["CALL"] == "W1ABC"


async def test_invalid_date_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"DATE": "260230"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-date"
        assert [n.message for n in app._notifications] == ["DATE '260230' isn't a real date"]
        assert field_values(app)["CALL"] == "W1ABC"


def drawn_table_row(app, row_index: int) -> str:
    """Text the log table actually draws for a data row (line 0 is the header)."""
    return app.query_one("#log-table", DataTable).render_line(row_index + 1).text


async def test_rows_drawn_in_full_without_redraw(app):
    # Regression: the first row was drawn at header widths ("14.1", "2026")
    # until something like a mouse hover forced a redraw.
    typed = {
        "FREQ": "1415",
        "MODE": "SSB",
        "CALL": "W1AAA",
        "PARK": "464",
        "ST": "NN",
        "SNT": "58",
        "RCD": "58",
        "PWR": "30",
        "DATE": "260923",
        "TIME": "1111",
    }
    async with app.run_test(size=(120, 24)) as pilot:
        # Typed key by key: the bug needed the redraws that typing causes.
        for value in typed.values():
            await pilot.press(*value, "tab")
        await pilot.press("shift+tab", "enter")
        await pilot.pause()
        assert drawn_table_row(app, 0).split() == [
            "14.150.000", "SSB", "W1AAA", "464", "NN", "58", "58", "30", "2026.09.23", "1111"
        ]
        # A later, longer value is drawn in full too.
        fill(app, typed | {"CALL": ""})
        app.query_one("#field-call", Input).focus()
        await pilot.press(*"VE3/W1ABC/P", "enter")
        await pilot.pause()
        assert drawn_table_row(app, 1).split()[2] == "VE3/W1ABC/P"


async def test_date_column_before_time(app):
    async with app.run_test():
        names = [name for name, _, _ in FIELDS]
        assert names.index("DATE") == names.index("TIME") - 1


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
