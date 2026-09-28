from datetime import date

from textual.command import CommandPalette
from textual.widgets import DataTable, Input, Static

from pota_logger_t3 import PotaLoggerApp, dates
from pota_logger_t3.callsign_warning_screen import CallsignWarningScreen
from pota_logger_t3.entry_form import FIELDS
from pota_logger_t3.settings import Settings, load_settings, save_settings
from pota_logger_t3.settings_screen import SettingsScreen
from pota_logger_t3.warning_screen import WarningScreen


def station_callsign(app) -> str:
    return str(app.query_one("#station-callsign", Static).render())


# Layout


async def test_focus_starts_on_freq(app):
    async with app.run_test():
        assert app.focused.id == "field-freq"


async def test_uses_pota_theme(app):
    async with app.run_test():
        assert app.theme == "pota"


async def test_footer_shows_quit_settings_and_screenshot(app):
    async with app.run_test():
        shown = [
            key for key, active in app.screen.active_bindings.items() if active.binding.show
        ]
        assert shown == ["ctrl+q", "f2", "ctrl+s"]


async def test_ctrl_p_opens_no_command_palette(app):
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        assert not isinstance(app.screen, CommandPalette)


async def test_ctrl_s_delivers_a_screenshot(app, monkeypatch):
    delivered = []
    # Stubbed so the test doesn't save into the real Downloads folder.
    monkeypatch.setattr(app, "deliver_screenshot", lambda: delivered.append(True))
    async with app.run_test() as pilot:
        await pilot.press("ctrl+s")
        assert delivered == [True]


async def test_date_defaults_to_todays_local_date(app, monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 9, 3)

    monkeypatch.setattr(dates, "date", FixedDate)
    async with app.run_test():
        assert app.query_one("#field-date", Input).value == "260903"


async def test_entry_fields_have_equal_gaps_above_and_below(app):
    async with app.run_test(size=(100, 24)):
        status_bar = app.query_one("StatusBar").region
        label = app.query_one("EntryForm Label").region
        field = app.query_one("#field-freq", Input).region
        table = app.query_one("#log-table", DataTable).region
        gap_above = label.y - status_bar.bottom
        gap_below = table.y - field.bottom
        assert gap_above == gap_below == 1


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
        "PWR": "1500",
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
    "FREQ": "14.285.5",
    "MODE": "USB",
    "CALL": "W1ABC",
    "PARK": "1234",
    "ST": "NJ",
    "SNT": "59",
    "RCD": "57",
    "PWR": "60",
    "DATE": "260925",
    "TIME": "1953",
}

# ENTRY on CW, so any frequency in a band is fine.
CW_ENTRY = ENTRY | {"MODE": "CW"}

# ENTRY as it appears in the log table.
ENTRY_ROW = list(
    (
        ENTRY
        | {
            "FREQ": "14.285.500",
            "PARK": "US-1234",
            "PWR": "60W",
            "DATE": "2026.09.25",
            "TIME": "19:53",
        }
    ).values()
)


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


async def test_call_any_case_shown_uppercase(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "w1abc"})
        await pilot.press("enter")
        assert table_rows(app)[0][2] == "W1ABC"


async def test_invalid_call_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "W1ABC."})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-call"
        assert [n.message for n in app._notifications] == [
            "CALL 'W1ABC.' can only use letters, digits, and /"
        ]
        assert field_values(app)["FREQ"] == "14.285.5"


async def test_usual_call_skips_warning(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "ve3/w1abc/p"})
        await pilot.press("enter")
        assert not isinstance(app.screen, CallsignWarningScreen)
        assert table_rows(app)[0][2] == "VE3/W1ABC/P"


async def test_unusual_call_opens_warning_instead_of_saving(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "w11bc"})
        await pilot.press("enter")
        assert isinstance(app.screen, CallsignWarningScreen)
        assert table_rows(app) == []
        message = app.screen.query_one("#callsign-warning-message", Static)
        assert str(message.render()) == (
            "W11BC is an unusual callsign.\nCorrect and/or confirm with Enter."
        )
        assert app.focused.id == "callsign-warning-input"
        assert app.focused.value == "W11BC"


async def test_enter_in_warning_logs_call_as_is(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "W11BC"})
        await pilot.press("enter", "enter")
        assert not isinstance(app.screen, CallsignWarningScreen)
        assert table_rows(app)[0][2] == "W11BC"
        assert field_values(app)["CALL"] == ""
        assert app.focused.id == "field-freq"


async def test_call_corrected_in_warning_is_logged(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "W11BC"})
        # The call starts selected, so typing replaces it.
        await pilot.press("enter", *"w1abc", "enter")
        assert not isinstance(app.screen, CallsignWarningScreen)
        assert table_rows(app)[0][2] == "W1ABC"


async def test_invalid_correction_stays_in_warning(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "W11BC"})
        await pilot.press("enter")
        await pilot.press("end", ".", "enter")
        assert isinstance(app.screen, CallsignWarningScreen)
        assert table_rows(app) == []
        assert [n.message for n in app._notifications] == [
            "CALL 'W11BC.' can only use letters, digits, and /"
        ]


async def test_escape_from_warning_returns_to_call_without_saving(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "W11BC"})
        await pilot.press("enter", "escape")
        assert not isinstance(app.screen, CallsignWarningScreen)
        assert table_rows(app) == []
        assert app.focused.id == "field-call"
        assert field_values(app) == ENTRY | {"CALL": "W11BC"}


FUTURE = {"DATE": "991231"}


async def test_future_time_opens_warning_instead_of_saving(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | FUTURE)
        await pilot.press("enter")
        assert isinstance(app.screen, WarningScreen)
        assert table_rows(app) == []
        message = app.screen.query_one("#warning-message", Static)
        assert str(message.render()).startswith("2099.12.31 19:53 UTC is in the future.")


async def test_enter_in_warning_saves(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | FUTURE)
        await pilot.press("enter", "enter")
        assert not isinstance(app.screen, WarningScreen)
        assert table_rows(app)[0][8] == "2099.12.31"
        assert app.focused.id == "field-freq"


async def test_confirm_button_saves(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | FUTURE)
        await pilot.press("enter")
        await pilot.click("#confirm")
        assert len(table_rows(app)) == 1


async def test_escape_from_future_warning_returns_to_date(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | FUTURE)
        await pilot.press("enter", "escape")
        assert not isinstance(app.screen, WarningScreen)
        assert table_rows(app) == []
        assert app.focused.id == "field-date"
        assert field_values(app) == ENTRY | FUTURE


async def test_voice_outside_range_opens_warning(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"FREQ": "14.074"})
        await pilot.press("enter")
        assert isinstance(app.screen, WarningScreen)
        assert table_rows(app) == []
        message = app.screen.query_one("#warning-message", Static)
        assert str(message.render()).startswith(
            "USB on 14.074.000 runs outside\n20m's voice range."
        )


async def test_ssb_near_voice_edge_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"FREQ": "21.450", "MODE": "SSB"})
        await pilot.press("enter")
        assert not isinstance(app.screen, WarningScreen)
        assert table_rows(app) == []
        assert app.focused.id == "field-mode"
        assert [n.message for n in app._notifications] == [
            "SSB on 21.450.000 is within 3 kHz of 15m's voice edge; log USB or LSB"
        ]


async def test_sideband_inside_edge_is_saved(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"FREQ": "21.450", "MODE": "LSB"})
        await pilot.press("enter")
        assert not isinstance(app.screen, WarningScreen)
        assert len(table_rows(app)) == 1


async def test_sideband_past_edge_opens_warning(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"FREQ": "21.450", "MODE": "USB"})
        await pilot.press("enter")
        assert isinstance(app.screen, WarningScreen)
        assert table_rows(app) == []


async def test_escape_from_voice_warning_returns_to_freq(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"FREQ": "14.074"})
        await pilot.press("enter", "escape")
        assert table_rows(app) == []
        assert app.focused.id == "field-freq"


async def test_cw_in_cw_range_has_no_warning(app):
    async with app.run_test() as pilot:
        fill(app, CW_ENTRY | {"FREQ": "14.074"})
        await pilot.press("enter")
        assert not isinstance(app.screen, WarningScreen)
        assert len(table_rows(app)) == 1


async def test_state_on_non_us_park_opens_warning(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"PARK": "JP-1234", "ST": "NJ"})
        await pilot.press("enter")
        assert isinstance(app.screen, WarningScreen)
        message = app.screen.query_one("#warning-message", Static)
        assert str(message.render()).startswith("JP-1234 is a non-US park, so ST is likely blank.")
        await pilot.press("escape")
        assert table_rows(app) == []
        assert app.focused.id == "field-st"


async def test_non_us_park_with_blank_state_has_no_warning(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"PARK": "JP-1234", "ST": ""})
        await pilot.press("enter")
        assert table_rows(app)[0][3:5] == ["JP-1234", ""]


async def test_possible_dupe_opens_warning(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        await pilot.press("enter")
        fill(app, ENTRY | {"FREQ": "14.300", "MODE": "SSB", "TIME": "2005"})
        await pilot.press("enter")
        assert isinstance(app.screen, WarningScreen)
        assert len(table_rows(app)) == 1
        message = str(app.screen.query_one("#warning-message", Static).render())
        assert message.startswith("Possible dupe: W1ABC at US-1234,\n20m voice, already logged at 19:53.")
        await pilot.press("escape")
        assert app.focused.id == "field-call"
        await pilot.press("enter", "enter")
        assert len(table_rows(app)) == 2


async def test_same_call_on_another_band_is_not_a_dupe(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        await pilot.press("enter")
        fill(app, ENTRY | {"FREQ": "7.200"})
        await pilot.press("enter")
        assert not isinstance(app.screen, WarningScreen)
        assert len(table_rows(app)) == 2


async def test_warnings_come_one_after_another(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | FUTURE | {"CALL": "W11BC"})
        await pilot.press("enter")
        assert isinstance(app.screen, CallsignWarningScreen)
        await pilot.press("enter")
        assert isinstance(app.screen, WarningScreen)
        assert table_rows(app) == []
        await pilot.press("enter")
        assert table_rows(app)[0][2] == "W11BC"


async def test_park_bare_number_shown_as_us(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"PARK": "1234"})
        await pilot.press("enter")
        fill(app, ENTRY | {"PARK": "JP-1234", "ST": ""})
        await pilot.press("enter")
        fill(app, ENTRY | {"PARK": "jp234", "ST": ""})
        await pilot.press("enter")
        assert [row[3] for row in table_rows(app)] == ["US-1234", "JP-1234", "JP-234"]


async def test_three_digit_report_requires_cw(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"MODE": "USB", "SNT": "599"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-snt"
        assert [n.message for n in app._notifications] == [
            "SNT '599' needs MODE CW for a 3-digit report"
        ]
        assert field_values(app)["CALL"] == "W1ABC"


async def test_impossible_report_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"RCD": "69"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-rcd"
        assert [n.message for n in app._notifications] == [
            "RCD '69' isn't a real report: readability is 1-5"
        ]
        assert field_values(app)["CALL"] == "W1ABC"


async def test_three_digit_report_allowed_on_cw(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"MODE": "CW", "SNT": "599", "RCD": "579"})
        await pilot.press("enter")
        assert [row[5] for row in table_rows(app)] == ["599"]
        assert [row[6] for row in table_rows(app)] == ["579"]


async def test_after_entry_fields_reset_except_power_and_date(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        app.query_one("#field-time", Input).focus()
        await pilot.press("enter")
        expected = {name: "" for name in ENTRY} | {"MODE": "SSB", "PWR": "60", "DATE": "260925"}
        assert field_values(app) == expected
        assert app.focused.id == "field-freq"


async def test_entries_append_in_entered_order(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "W1AAA", "TIME": "2000"})
        await pilot.press("enter")
        fill(app, ENTRY | {"CALL": "W1AAB", "TIME": "1900"})
        await pilot.press("enter")
        assert [row[-1] for row in table_rows(app)] == ["20:00", "19:00"]


async def test_missing_fields_block_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "", "TIME": " "})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-call"
        assert [n.message for n in app._notifications] == ["Missing: CALL, TIME"]
        # Nothing was cleared.
        assert field_values(app)["FREQ"] == "14.285.5"


async def test_freq_shown_in_full_in_table(app):
    async with app.run_test() as pilot:
        fill(app, CW_ENTRY | {"CALL": "W1AAA", "FREQ": "14"})
        await pilot.press("enter")
        fill(app, CW_ENTRY | {"CALL": "W1AAB", "FREQ": "14074"})
        await pilot.press("enter")
        fill(app, CW_ENTRY | {"CALL": "W1AAC", "FREQ": "14.0745"})
        await pilot.press("enter")
        fill(app, CW_ENTRY | {"CALL": "W1AAD", "FREQ": "28312456"})
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


async def test_invalid_time_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"TIME": "2360"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-time"
        assert [n.message for n in app._notifications] == [
            "TIME '2360' isn't a real time (0000 to 2359)"
        ]
        assert field_values(app)["CALL"] == "W1ABC"


async def test_state_is_optional(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"ST": ""})
        await pilot.press("enter")
        assert table_rows(app)[0][4] == ""
        assert not app._notifications


async def test_state_uppercased_and_na_allowed(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "W1AAA", "ST": "nj"})
        await pilot.press("enter")
        fill(app, ENTRY | {"CALL": "W1AAB", "ST": "na"})
        await pilot.press("enter")
        assert [row[4] for row in table_rows(app)] == ["NJ", "NA"]


async def test_invalid_state_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"ST": "ZZ"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-st"
        assert len(app._notifications) == 1
        assert field_values(app)["CALL"] == "W1ABC"


async def test_mode_any_case_shown_uppercase(app):
    async with app.run_test() as pilot:
        for call, mode in zip(("W1AAA", "W1AAB", "W1AAC", "W1AAD"), ("ssb", "usb", "Lsb", "cw")):
            fill(app, ENTRY | {"CALL": call, "MODE": mode})
            await pilot.press("enter")
        assert [row[1] for row in table_rows(app)] == ["SSB", "USB", "LSB", "CW"]


async def test_mode_has_placeholder_and_no_autofill(app):
    async with app.run_test() as pilot:
        mode = app.query_one("#field-mode", Input)
        assert mode.placeholder == "SSB"
        assert mode.suggester is None
        # Tab moves on and leaves exactly what was typed.
        await pilot.press(*"14.074", "tab", "s", "tab")
        assert app.focused.id == "field-call"
        assert mode.value == "s"


async def test_single_letter_mode_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"MODE": "u"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-mode"


async def test_invalid_mode_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"MODE": "FM"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-mode"
        assert len(app._notifications) == 1
        assert field_values(app)["CALL"] == "W1ABC"


async def test_power_shown_with_watts(app):
    async with app.run_test() as pilot:
        for call, watts in zip(("W1AAA", "W1AAB", "W1AAC", "W1AAD"), ("60", ".5", "2.5", "1500")):
            fill(app, ENTRY | {"CALL": call, "PWR": watts})
            await pilot.press("enter")
        assert [row[7] for row in table_rows(app)] == ["60W", ".5W", "2.5W", "1500W"]


async def test_invalid_power_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"PWR": "60W"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-pwr"
        assert len(app._notifications) == 1
        assert field_values(app)["CALL"] == "W1ABC"


def drawn_table_row(app, row_index: int) -> str:
    """Text the log table actually draws for a data row (line 0 is the header)."""
    return app.query_one("#log-table", DataTable).render_line(row_index + 1).text


async def test_rows_drawn_in_full_without_redraw(app):
    # Regression: the first row was drawn at header widths ("14.1", "2026")
    # until something like a mouse hover forced a redraw.
    typed = {
        "FREQ": "1425",
        "MODE": "SSB",
        "CALL": "W1AAA",
        "PARK": "464",
        "ST": "NJ",
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
            "14.250.000", "SSB", "W1AAA", "US-464", "NJ", "58", "58", "30W", "2026.09.23", "11:11"
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
