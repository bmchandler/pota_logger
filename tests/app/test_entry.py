"""Entering a record: the form's fields, checks, warnings, and saving."""

from textual.widgets import DataTable, Input, Static

from pota_logger.entry_form import FIELDS, LOG_FIELDS, ROW_FIELDS
from pota_logger.screens.callsign_warning_screen import CallsignWarningScreen
from pota_logger.screens.warning_screen import WarningScreen

from tests.app.helpers import (
    CW_ENTRY,
    ENTRY,
    ENTRY_ROW,
    FUTURE,
    drawn_table_row,
    field_values,
    fill,
    report_placeholders,
    table_rows,
)


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
        for name, _, _ in FIELDS:
            await pilot.press(*ENTRY[name], "tab")
        await pilot.press("shift+tab", "enter")  # back onto COMMENT, then Enter
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


async def test_non_ascii_correction_stays_in_warning(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "W11BC"})
        await pilot.press("enter")
        app.screen.query_one("#callsign-warning-input", Input).value = "W1ÅBC"
        await pilot.press("enter")
        assert isinstance(app.screen, CallsignWarningScreen)
        assert table_rows(app) == []
        assert [n.message for n in app._notifications] == [
            "CALL 'W1ÅBC' has non-ASCII characters: 'Å'.\nUse plain ASCII, like W1ABC."
        ]


async def test_escape_from_warning_returns_to_call_without_saving(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "W11BC"})
        await pilot.press("enter", "escape")
        assert not isinstance(app.screen, CallsignWarningScreen)
        assert table_rows(app) == []
        assert app.focused.id == "field-call"
        assert field_values(app) == ENTRY | {"CALL": "W11BC"}


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


async def test_warning_opens_with_no_button_focused(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | FUTURE)
        await pilot.press("enter")
        assert app.focused is None


async def test_tab_moves_between_warning_buttons(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | FUTURE)
        await pilot.press("enter", "tab")
        assert app.focused.id == "back"
        await pilot.press("tab")
        assert app.focused.id == "confirm"
        await pilot.press("tab")
        assert app.focused.id == "back"
        await pilot.press("shift+tab")
        assert app.focused.id == "confirm"


async def test_enter_on_tabbed_back_button_goes_back(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | FUTURE)
        await pilot.press("enter", "tab", "enter")
        assert not isinstance(app.screen, WarningScreen)
        assert table_rows(app) == []
        assert app.focused.id == "field-date"


async def test_enter_on_tabbed_confirm_button_saves(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | FUTURE)
        await pilot.press("enter", "tab", "tab", "enter")
        assert not isinstance(app.screen, WarningScreen)
        assert len(table_rows(app)) == 1


async def test_lone_button_not_focusable(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        await pilot.press("enter")
        fill(app, ENTRY)
        await pilot.press("enter")
        # The dupe block: one button, and Enter or Esc closes it.
        assert isinstance(app.screen, WarningScreen)
        assert not app.screen.query_one("#confirm").can_focus
        await pilot.press("tab")
        assert app.focused is None


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


async def test_park_shown_as_full_pota_reference(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"PARK": "1234"})
        await pilot.press("enter")
        fill(app, ENTRY | {"PARK": "JP-1234", "ST": ""})
        await pilot.press("enter")
        fill(app, ENTRY | {"PARK": "jp234", "ST": ""})
        await pilot.press("enter")
        assert [row[3] for row in table_rows(app)] == ["US-1234", "JP-1234", "JP-0234"]


async def test_park_field_takes_adif_longest_reference_at_its_width(app):
    async with app.run_test(size=(130, 30)) as pilot:
        field = app.query_one("#field-park", Input)
        width = field.region.width
        field.focus()
        await pilot.press(*"ABCD-12345", *"XYZ")
        assert field.value == "ABCD-12345"
        assert field.region.width == width
        table = app.query_one("#log-table", DataTable)
        park = next(c for c in table.columns.values() if str(c.label).strip() == "PARK")
        # Plus the padding each log cell carries, a space each side.
        assert park.width == len("ABCD-12345") + 2


async def test_park_with_too_many_digits_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"PARK": "123456"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-park"
        assert [n.message for n in app._notifications] == [
            "PARK '123456' isn't a POTA park; parks must be <= 5 digits"
        ]


async def test_park_with_location_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"PARK": "4566@us-wy"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-park"
        assert [n.message for n in app._notifications] == [
            "PARK '4566@us-wy': @ form not accepted for input; ADIF export only"
        ]


async def test_invalid_park_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"PARK": "US 1234"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-park"
        assert [n.message for n in app._notifications] == [
            "PARK 'US 1234' isn't a POTA park; use a form like 1234 or JP-1234"
        ]


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


async def test_two_digit_report_blocked_on_cw(app):
    async with app.run_test() as pilot:
        fill(app, CW_ENTRY | {"RCD": "57"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-rcd"
        assert [n.message for n in app._notifications] == [
            "RCD '57' needs 3 digits on CW, like 599"
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


async def test_after_entry_fields_reset_except_power_date_and_mode(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        app.query_one("#field-time", Input).focus()
        await pilot.press("enter")
        expected = {name: "" for name in ENTRY} | {"MODE": "USB", "PWR": "60", "DATE": "260925"}
        assert field_values(app) == expected
        assert app.focused.id == "field-freq"


async def test_entries_append_in_entered_order(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "W1AAA", "TIME": "2000"})
        await pilot.press("enter")
        fill(app, ENTRY | {"CALL": "W1AAB", "TIME": "1900"})
        await pilot.press("enter")
        time_column = [name for name, _, _ in LOG_FIELDS].index("TIME")
        assert [row[time_column] for row in table_rows(app)] == ["20:00", "19:00"]


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


async def test_state_uppercased(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"ST": "nj"})
        await pilot.press("enter")
        assert [row[4] for row in table_rows(app)] == ["NJ"]


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
            reports = {"SNT": "599", "RCD": "599"} if mode == "cw" else {}
            fill(app, ENTRY | {"CALL": call, "MODE": mode} | reports)
            await pilot.press("enter")
        assert [row[1] for row in table_rows(app)] == ["SSB", "USB", "LSB", "CW"]


async def test_mode_has_placeholder_and_no_autofill(app):
    async with app.run_test() as pilot:
        mode = app.query_one("#field-mode", Input)
        assert mode.placeholder == "SSB"
        assert mode.suggester is None
        # Tab moves on and leaves exactly what was typed.
        app.query_one("#field-date", Input).focus()
        await pilot.press("tab", "s", "tab")
        assert app.focused.id == "field-comment"
        assert mode.value == "s"


async def test_report_placeholders_follow_mode_on_leaving_it(app):
    async with app.run_test() as pilot:
        mode = app.query_one("#field-mode", Input)
        assert report_placeholders(app) == ["59", "59"]
        mode.focus()
        mode.value = "cw"
        await pilot.pause()
        # Not while MODE is still being typed.
        assert report_placeholders(app) == ["59", "59"]
        await pilot.press("tab")
        assert report_placeholders(app) == ["599", "599"]
        mode.focus()
        mode.value = "x"
        await pilot.press("shift+tab")
        assert report_placeholders(app) == ["59", "59"]


async def test_report_placeholders_leave_typed_reports_alone(app):
    async with app.run_test() as pilot:
        fill(app, {"SNT": "57"})
        mode = app.query_one("#field-mode", Input)
        mode.focus()
        mode.value = "CW"
        await pilot.press("tab")
        assert field_values(app)["SNT"] == "57"
        assert report_placeholders(app) == ["599", "599"]


async def test_report_placeholders_stay_cw_after_cw_entry(app):
    # MODE carries forward, so the next entry is on CW too.
    async with app.run_test() as pilot:
        app.query_one("#field-mode", Input).focus()
        fill(app, CW_ENTRY)
        await pilot.press("tab")
        assert report_placeholders(app) == ["599", "599"]
        await pilot.press("enter")
        assert len(table_rows(app)) == 1
        assert field_values(app)["MODE"] == "CW"
        assert report_placeholders(app) == ["599", "599"]


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
        for name, _, _ in ROW_FIELDS:
            await pilot.press(*typed[name], "tab")
        await pilot.press("shift+tab", "enter")
        await pilot.pause()
        assert drawn_table_row(app, 0).split() == [
            "•", "14.250.000", "SSB", "W1AAA", "US-0464", "NJ", "58", "58", "30W", "2026.09.23", "11:11"
        ]
        # A later, longer value is drawn in full too.
        fill(app, typed | {"CALL": ""})
        app.query_one("#field-call", Input).focus()
        await pilot.press(*"VE3/W1ABC/P", "enter")
        await pilot.pause()
        assert drawn_table_row(app, 1).split()[3] == "VE3/W1ABC/P"


async def test_date_column_before_time(app):
    async with app.run_test():
        names = [name for name, _, _ in LOG_FIELDS]
        assert names.index("DATE") == names.index("TIME") - 1
