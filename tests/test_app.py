from datetime import date

import pytest
from textual.command import CommandPalette
from textual.widgets import Button, DataTable, Input, Static

from pota_logger import PotaLoggerApp, dates
from pota_logger.callsign_warning_screen import CallsignWarningScreen
from pota_logger.entry_form import COMMENT_LENGTH, FIELDS, ROW_FIELDS, EntryForm
from pota_logger.settings import Settings, load_settings, save_settings
from pota_logger.settings_screen import SettingsScreen
from pota_logger.warning_screen import WarningScreen


def station_callsign(app) -> str:
    return str(app.query_one("#station-callsign", Static).render())


# Layout


async def test_focus_starts_on_freq(app):
    async with app.run_test():
        assert app.focused.id == "field-freq"


async def test_uses_pota_theme(app):
    async with app.run_test():
        assert app.theme == "pota"


async def test_footer_shows_quit_settings_edit_and_screenshot(app):
    async with app.run_test():
        shown = [
            key for key, active in app.screen.active_bindings.items() if active.binding.show
        ]
        assert shown == ["ctrl+q", "f2", "f3", "ctrl+s"]


async def test_footer_shows_terminal_size_and_follows_resize(app):
    async with app.run_test(size=(110, 26)) as pilot:
        size = app.query_one("#terminal-size", Static)
        assert str(size.render()) == "110x26"
        await pilot.resize_terminal(100, 24)
        await pilot.pause()
        assert str(size.render()) == "100x24"
        assert size.region.right == 100
        assert size.region.y == 23


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
    async with app.run_test(size=(107, 24)):
        status_bar = app.query_one("StatusBar").region
        label = app.query_one("EntryForm Horizontal Label").region
        comment = app.query_one("#field-comment", Input).region
        table = app.query_one("#log-table", DataTable).region
        gap_above = label.y - status_bar.bottom
        gap_below = table.y - comment.bottom
        assert gap_above == gap_below == 1


async def test_quit_button_matches_warning_confirm_color(app):
    async with app.run_test():
        assert app.query_one("#quit", Button).variant == "warning"


async def test_form_scrolls_sideways_only_when_narrower_than_it(app):
    async with app.run_test(size=(107, 24)) as pilot:
        form = app.query_one(EntryForm)
        assert not form.show_horizontal_scrollbar
        await pilot.resize_terminal(106, 24)
        await pilot.pause()
        assert form.show_horizontal_scrollbar
        await pilot.resize_terminal(107, 24)
        await pilot.pause()
        assert not form.show_horizontal_scrollbar
        assert form.scroll_x == 0


async def test_narrow_form_scrollbar_lines_up_with_comment_and_keeps_gaps(app):
    async with app.run_test(size=(90, 24)) as pilot:
        await pilot.pause()
        form = app.query_one(EntryForm).region
        comment = app.query_one("#field-comment", Input).region
        table = app.query_one("#log-table", DataTable).region
        scrollbar_row = form.bottom - 1
        assert form.x == comment.x
        # COMMENT, a blank row, the scrollbar, a blank row, then the log.
        assert scrollbar_row - comment.bottom == 1
        assert table.y - form.bottom == 1
        assert table.width == 90


async def test_narrow_form_scrolls_to_the_focused_field(app):
    async with app.run_test(size=(90, 24)) as pilot:
        form = app.query_one(EntryForm)
        field = app.query_one("#field-time", Input)
        field.focus()
        # Focus queues a scroll into view, which then animates.
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        assert form.scroll_x > 0
        assert form.region.contains_region(field.region)


async def test_tab_order_follows_paper_log_then_table(app):
    async with app.run_test():
        chain = [w.id for w in app.screen.focus_chain]
        assert chain == [f"field-{name.lower()}" for name, _, _ in FIELDS] + ["log-table"]


async def test_log_table_columns_match_fields(app):
    async with app.run_test():
        table = app.query_one("#log-table", DataTable)
        # The first column, with no header, holds the session marker.
        labels = [str(c.label).strip() for c in table.columns.values()]
        assert labels == [""] + [n for n, _, _ in FIELDS]


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
        "COMMENT": "x" * COMMENT_LENGTH,
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
    "COMMENT": "",
}

# ENTRY on CW, so any frequency in a band is fine.
CW_ENTRY = ENTRY | {"MODE": "CW", "SNT": "599", "RCD": "579"}

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
    """The log's rows, without the marker column or the cells' padding."""
    table = app.query_one("#log-table", DataTable)
    return [
        [str(cell).strip() for cell in table.get_row_at(i)[1:]] for i in range(table.row_count)
    ]


def table_markers(app) -> list[str]:
    table = app.query_one("#log-table", DataTable)
    return [str(table.get_row_at(i)[0]).strip() for i in range(table.row_count)]


def divider_rows(app) -> list[int]:
    """Rows whose every cell is overlined, as the divider is."""
    table = app.query_one("#log-table", DataTable)
    return [
        i
        for i in range(table.row_count)
        if all("overline" in str(cell.style) for cell in table.get_row_at(i))
    ]


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


async def test_park_shown_as_full_pota_reference(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"PARK": "1234"})
        await pilot.press("enter")
        fill(app, ENTRY | {"PARK": "JP-1234", "ST": ""})
        await pilot.press("enter")
        fill(app, ENTRY | {"PARK": "jp234", "ST": ""})
        await pilot.press("enter")
        fill(app, ENTRY | {"PARK": "us4566@us-wy", "ST": ""})
        await pilot.press("enter")
        assert [row[3] for row in table_rows(app)] == [
            "US-1234", "JP-1234", "JP-0234", "US-4566@US-WY"
        ]


async def test_park_field_takes_adif_longest_reference_at_its_width(app):
    async with app.run_test(size=(130, 30)) as pilot:
        field = app.query_one("#field-park", Input)
        width = field.region.width
        field.focus()
        await pilot.press(*"ABCD-12345@US-ABC", *"XYZ")
        assert field.value == "ABCD-12345@US-ABC"
        assert field.region.width == width
        table = app.query_one("#log-table", DataTable)
        park = next(c for c in table.columns.values() if str(c.label).strip() == "PARK")
        # Plus the padding each log cell carries, a space each side.
        assert park.width == len("ABCD-12345@US-ABC") + 2


async def test_park_with_too_many_digits_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"PARK": "123456"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-park"
        assert [n.message for n in app._notifications] == [
            "PARK '123456' isn't a POTA park; parks must be <= 5 digits"
        ]


async def test_invalid_park_blocks_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"PARK": "US 1234"})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == "field-park"
        assert [n.message for n in app._notifications] == [
            "PARK 'US 1234' isn't a POTA park; use a form like 1234, JP-1234, or US-4566@US-WY"
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
        time_column = [name for name, _, _ in FIELDS].index("TIME")
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
        await pilot.press(*"14.074", "tab", "s", "tab")
        assert app.focused.id == "field-call"
        assert mode.value == "s"


def report_placeholders(app) -> list[str]:
    return [app.query_one(f"#field-{name}", Input).placeholder for name in ("snt", "rcd")]


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


async def test_report_placeholders_reset_after_cw_entry(app):
    async with app.run_test() as pilot:
        app.query_one("#field-mode", Input).focus()
        fill(app, CW_ENTRY)
        await pilot.press("tab")
        assert report_placeholders(app) == ["599", "599"]
        await pilot.press("enter")
        assert len(table_rows(app)) == 1
        assert report_placeholders(app) == ["59", "59"]


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
        names = [name for name, _, _ in FIELDS]
        assert names.index("DATE") == names.index("TIME") - 1


# COMMENT


async def test_comment_spans_the_row_of_fields_above(app):
    async with app.run_test(size=(130, 30)):
        comment = app.query_one("#field-comment", Input).region
        first = app.query_one(f"#field-{ROW_FIELDS[0][0].lower()}", Input).region
        last = app.query_one(f"#field-{ROW_FIELDS[-1][0].lower()}", Input).region
        assert (comment.x, comment.right) == (first.x, last.right)


async def test_comment_takes_only_what_fits_in_view(app):
    async with app.run_test(size=(130, 30)) as pilot:
        field = app.query_one("#field-comment", Input)
        field.focus()
        await pilot.press(*"x" * (COMMENT_LENGTH + 3))
        assert field.value == "x" * COMMENT_LENGTH
        # +1 for the cursor
        assert field.content_region.width >= COMMENT_LENGTH + 1


async def test_comment_column_follows_time_at_the_fields_width(app):
    async with app.run_test():
        table = app.query_one("#log-table", DataTable)
        columns = list(table.columns.values())
        assert [str(c.label).strip() for c in columns[-2:]] == ["TIME", "COMMENT"]
        # Plus the padding each log cell carries, a space each side.
        assert columns[-1].width == COMMENT_LENGTH + 2


async def test_comment_is_saved_as_typed_and_cleared_for_next_entry(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"COMMENT": " RSGB Field Day Serial #042 "})
        await pilot.press("enter")
        assert table_rows(app)[0][-1] == "RSGB Field Day Serial #042"
        assert app.query_one("#field-comment", Input).value == ""


@pytest.mark.parametrize(
    "name, value, message",
    [
        ("COMMENT", "Café", "COMMENT 'Café' has non-ASCII characters: 'é'."),
        (
            "SNT",
            "５９",
            "SNT '５９' has non-ASCII characters: '５', '９'.\n"
            "Use plain ASCII, like 59, or 599 on CW.",
        ),
        (
            "FREQ",
            "１４.２８５",
            "FREQ '１４.２８５' has non-ASCII characters: '１', '４', '２', '８', '５'.\n"
            "Use plain ASCII, like 14.074.5.",
        ),
    ],
)
async def test_non_ascii_blocks_entry_naming_the_characters(app, name, value, message):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {name: value})
        await pilot.press("enter")
        assert table_rows(app) == []
        assert app.focused.id == f"field-{name.lower()}"
        assert [n.message for n in app._notifications] == [message]
        assert field_values(app)[name] == value


# Storage


async def test_entry_is_saved_to_its_dates_file(app, settings_path):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"COMMENT": "Nice, loud"})
        await pilot.press("enter")
    assert (settings_path.parent / "20260925.csv").read_text().splitlines() == [
        "FREQ,MODE,CALL,PARK,ST,SNT,RCD,PWR,DATE,TIME,COMMENT,STATION_CALLSIGN",
        '14285500,USB,W1ABC,US-1234,NJ,59,57,60,20260925,1953,"Nice, loud",W1TST',
    ]


async def test_saved_entries_are_shown_at_start(app, settings_path):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        await pilot.press("enter")
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert table_rows(app) == [ENTRY_ROW]


def write_saved_log(settings_path, rows: dict[str, list[tuple[str, str, str]]]) -> None:
    """Write log files: {file date: [(CALL, DATE, TIME), ...]} in file order."""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    for day, entries in rows.items():
        (settings_path.parent / f"{day}.csv").write_text(
            "FREQ,MODE,CALL,PARK,ST,SNT,RCD,PWR,DATE,TIME,COMMENT,STATION_CALLSIGN\n"
            + "".join(
                f"14285500,USB,{call},US-1234,NJ,59,57,60,{date},{time},,W1TST\n"
                for call, date, time in entries
            )
        )


def table_calls(app) -> list[str]:
    return [row[2] for row in table_rows(app)]


async def test_saved_entries_shown_newest_first(app, settings_path):
    write_saved_log(
        settings_path,
        {
            "20260924": [("K1AAA", "20260924", "2300")],
            "20260925": [
                ("K1BBB", "20260925", "1900"),
                ("K1CCC", "20260925", "0100"),
                ("K1DDD", "20260925", "2100"),
            ],
        },
    )
    async with app.run_test():
        assert table_calls(app) == ["K1DDD", "K1BBB", "K1CCC", "K1AAA"]


async def test_session_entries_go_above_saved_ones_in_typed_order(app, settings_path):
    write_saved_log(settings_path, {"20260924": [("K1AAA", "20260924", "2300")]})
    async with app.run_test() as pilot:
        # Out of time order on purpose, as copied from the paper log.
        for call, time in [("W1ABC", "1953"), ("K2DEF", "1948"), ("N3GHI", "2010")]:
            fill(app, ENTRY | {"CALL": call, "TIME": time})
            await pilot.press("enter")
        assert table_calls(app) == ["W1ABC", "K2DEF", "N3GHI", "K1AAA"]
    # Next start, they're sorted in with the rest.
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert table_calls(app) == ["N3GHI", "W1ABC", "K2DEF", "K1AAA"]


async def test_session_entries_are_marked(app, settings_path):
    write_saved_log(settings_path, {"20260924": [("K1AAA", "20260924", "2300")]})
    async with app.run_test(size=(107, 24)) as pilot:
        assert table_markers(app) == [""]
        fill(app, ENTRY)
        await pilot.press("enter")
        await pilot.pause()
        assert table_markers(app) == ["•", ""]
        # Drawn in the first column, before FREQ.
        assert drawn_table_row(app, 0).split()[:2] == ["•", "14.285.500"]
        assert drawn_table_row(app, 1).split()[0] == "14.285.500"
    # Gone on the next start.
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert table_markers(app) == ["", ""]


async def test_divider_over_the_first_saved_entry(app, settings_path):
    write_saved_log(settings_path, {"20260924": [("K1AAA", "20260924", "2300")]})
    async with app.run_test(size=(107, 24)) as pilot:
        # No entries typed yet, so nothing to divide.
        assert divider_rows(app) == []
        for call in ["W1ABC", "K2DEF"]:
            fill(app, ENTRY | {"CALL": call})
            await pilot.press("enter")
            await pilot.pause()
        assert divider_rows(app) == [2]
        # Unbroken: the cells carry their own padding, so the line covers
        # every cell of the row, gaps between columns included.
        table = app.query_one("#log-table", DataTable)
        cells = table.get_row_at(2)
        assert [cell.cell_len for cell in cells] == [c.width for c in table.columns.values()]
        assert all(len(cell.spans) == 0 and cell.style == "overline" for cell in cells)
        # And drawn with the overline, across the table's width.
        drawn = table.render_line(3)
        assert all(segment.style.overline for segment in drawn if segment.text)


async def test_no_divider_without_saved_entries(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        await pilot.press("enter")
        await pilot.pause()
        assert divider_rows(app) == []


async def test_comment_brackets_shown_as_typed(app, settings_path):
    # DataTable reads plain-string cells as markup, which hid these brackets
    # and crashed on "[/]".
    comments = ["RSGB [bold]Field[/bold] Day", "Oops [/] typo"]
    async with app.run_test() as pilot:
        for call, comment in zip(["W1ABC", "K2DEF"], comments):
            fill(app, ENTRY | {"CALL": call, "COMMENT": comment})
            await pilot.press("enter")
            await pilot.pause()
        assert [row[-1] for row in table_rows(app)] == comments
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test():
        assert sorted(row[-1] for row in table_rows(app)) == sorted(comments)


async def test_log_scrolls_to_show_the_latest_session_entry(app, settings_path):
    write_saved_log(settings_path, {"20260924": [("K1AAA", "20260924", "2300")]})
    async with app.run_test(size=(107, 24)) as pilot:
        table = app.query_one("#log-table", DataTable)
        calls = [f"W1A{letter}" for letter in "BCDEFGHIJKLM"]
        for call in calls:
            fill(app, ENTRY | {"CALL": call})
            await pilot.press("enter")
        await pilot.pause()
        rows_in_view = table.scrollable_content_region.height - table.header_height
        assert rows_in_view < len(calls)
        # The latest session entry is the bottom row in view.
        assert table.scroll_y == len(calls) - rows_in_view


async def test_possible_dupe_sees_entries_saved_before(app, settings_path):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        await pilot.press("enter")
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"TIME": "2005"})
        await pilot.press("enter")
        assert isinstance(app.screen, WarningScreen)


async def test_unreadable_row_is_skipped_with_notification(app, settings_path):
    path = settings_path.parent / "20260925.csv"
    path.write_text(
        "FREQ,MODE,CALL,PARK,ST,SNT,RCD,PWR,DATE,TIME,COMMENT,STATION_CALLSIGN\n"
        "14285500,USB,W1ABC,US-1234,NJ,59,57,60,20260925,53,,W1TST\n"
    )
    async with app.run_test():
        assert table_rows(app) == []
        assert [n.message for n in app._notifications] == [
            f"Skipped {path} row 2: TIME '53' should be HHMM, like 2123"
        ]



# Editing

LOG_HEADER = "FREQ,MODE,CALL,PARK,ST,SNT,RCD,PWR,DATE,TIME,COMMENT,STATION_CALLSIGN\n"
K1AAA_ROW = "14285500,USB,K1AAA,US-1234,NJ,59,57,60,20260925,2100,,W1TST\n"
K1BBB_ROW = "7030000,CW,K1BBB,US-5678,,599,579,0.5,20260925,1900,Loud,W1TST\n"


def write_two_saved(settings_path):
    """K1AAA then K1BBB in the log, newest first; K1BBB is the second row."""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    path = settings_path.parent / "20260925.csv"
    path.write_text(LOG_HEADER + K1AAA_ROW + K1BBB_ROW)
    return path


async def select_row(app, pilot, row: int) -> None:
    """Tab into the log, move to a row, and select it with Enter."""
    table = app.query_one("#log-table", DataTable)
    table.focus()
    table.move_cursor(row=row)
    await pilot.press("enter")


async def edit_row(app, pilot, row: int) -> None:
    await select_row(app, pilot, row)
    await pilot.press("f3")


K1BBB_VALUES = {
    "FREQ": "7.030.000",
    "MODE": "CW",
    "CALL": "K1BBB",
    "PARK": "US-5678",
    "ST": "",
    "SNT": "599",
    "RCD": "579",
    "PWR": "0.5",
    "DATE": "260925",
    "TIME": "1900",
    "COMMENT": "Loud",
}


def form_disabled(app) -> bool:
    """Whether every field is read-only (disabled); False if all are not."""
    states = {field.disabled for field in app.query_one(EntryForm).query(Input)}
    assert len(states) == 1
    return states.pop()


async def test_enter_on_a_log_row_shows_its_entry_read_only(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await select_row(app, pilot, 1)
        assert field_values(app) == K1BBB_VALUES
        assert form_disabled(app)
        table = app.query_one("#log-table", DataTable)
        assert table.cursor_type == "row"
        assert table.has_class("-selected")
        assert app.focused is table
        assert app.query_one(EntryForm).border_title is None


async def test_shown_entry_has_no_placeholders_until_edited(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await select_row(app, pilot, 1)
        # ST is blank: its NJ hint would read like a value.
        assert app.query_one("#field-st", Input).placeholder == ""
        await pilot.press("f3")
        assert app.query_one("#field-st", Input).placeholder == "NJ"
        assert report_placeholders(app) == ["599", "599"]


async def test_double_click_selects_a_row(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        # Below the header, on the second row.
        await pilot.click("#log-table", offset=(10, 2))
        await pilot.click("#log-table", offset=(10, 2))
        assert field_values(app)["CALL"] == "K1BBB"
        assert app.query_one("#log-table", DataTable).cursor_type == "row"


async def test_single_click_only_highlights(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await pilot.click("#log-table", offset=(10, 2))
        assert app.selected is None
        assert not form_disabled(app)


async def test_up_and_down_move_the_selection_and_the_form_follows(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await select_row(app, pilot, 0)
        assert field_values(app)["CALL"] == "K1AAA"
        await pilot.press("down")
        assert field_values(app)["CALL"] == "K1BBB"
        await pilot.press("up")
        assert field_values(app)["CALL"] == "K1AAA"
        assert form_disabled(app)


async def test_f3_edits_the_selected_entry(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 1)
        assert field_values(app) == K1BBB_VALUES
        assert not form_disabled(app)
        form = app.query_one(EntryForm)
        assert form.border_title == "Editing record - Esc to cancel"
        assert app.focused.id == "field-freq"
        # Still shown selected, with the darker highlight.
        assert app.query_one("#log-table", DataTable).has_class("-selected")


async def test_f3_with_no_row_selected_says_how_to_select(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await pilot.press("f3")
        assert list(app._notifications)[-1].message == (
            "Double-click a record or press Enter when log area has focus first."
        )
        assert app.query_one(EntryForm).editing is None


async def test_editing_title_takes_the_top_margins_place(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test(size=(107, 24)) as pilot:
        comment = app.query_one("#field-comment", Input).region
        await edit_row(app, pilot, 0)
        assert app.query_one("#field-comment", Input).region == comment
        strips = app.screen._compositor.render_strips()
        # The row below the status bar, where the top margin was.
        assert "Editing record - Esc to cancel" in "".join(seg.text for seg in strips[1])


async def test_escape_steps_back_from_editing_to_selected_to_entry_in_progress(
    app, settings_path
):
    path = write_two_saved(settings_path)
    async with app.run_test() as pilot:
        fill(app, {"FREQ": "14.074", "CALL": "W1ABC"})
        typed = field_values(app)
        app.query_one("#field-call", Input).focus()
        await edit_row(app, pilot, 1)
        fill(app, {"COMMENT": "Changed"})
        # Editing to selected: the change is dropped, no prompt.
        await pilot.press("escape")
        assert field_values(app) == K1BBB_VALUES
        assert form_disabled(app)
        assert app.query_one(EntryForm).border_title is None
        table = app.query_one("#log-table", DataTable)
        assert app.focused is table
        # Selected to none: the entry in progress comes back.
        await pilot.press("escape")
        assert app.selected is None
        assert field_values(app) == typed
        assert not form_disabled(app)
        assert table.cursor_type == "cell"
        assert not table.has_class("-selected")
        assert app.focused.id == "field-call"
    assert path.read_text() == LOG_HEADER + K1AAA_ROW + K1BBB_ROW


async def test_selecting_another_row_keeps_the_entry_in_progress(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        fill(app, {"CALL": "W1ABC"})
        await select_row(app, pilot, 0)
        await pilot.press("down", "escape")
        assert field_values(app)["CALL"] == "W1ABC"


async def test_log_cursor_stays_on_the_entry_being_edited(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 0)
        table = app.query_one("#log-table", DataTable)
        # The form keeps focus, and a click on another row doesn't move off
        # the entry being edited.
        assert not table.can_focus
        await pilot.click("#log-table", offset=(10, 2))
        await pilot.pause()
        assert table.cursor_row == 0
        assert app.focused.id == "field-freq"
        assert field_values(app)["CALL"] == "K1AAA"


async def test_enter_saves_the_edit_in_place_and_stays_selected(app, settings_path):
    path = write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 1)
        # Not checked against itself: an unchanged CALL is no possible dupe.
        fill(app, {"COMMENT": "Loud, QSB"})
        await pilot.press("enter")
        assert not isinstance(app.screen, WarningScreen)
        assert table_calls(app) == ["K1AAA", "K1BBB"]
        assert table_rows(app)[1][-1] == "Loud, QSB"
        table = app.query_one("#log-table", DataTable)
        assert table.cursor_row == 1
        assert app.focused is table
        assert app.query_one(EntryForm).border_title is None
        assert field_values(app) == K1BBB_VALUES | {"COMMENT": "Loud, QSB"}
        assert form_disabled(app)
        assert app.selected is app.saved_entries[1]
    assert path.read_text() == LOG_HEADER + K1AAA_ROW + K1BBB_ROW.replace(
        "Loud", '"Loud, QSB"'
    )


async def test_edited_saved_entry_is_marked(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 1)
        fill(app, {"COMMENT": "Loud, QSB"})
        await pilot.press("enter")
        assert table_markers(app) == ["", "✎"]
        # Edited again, it stays marked once.
        await pilot.press("f3")
        fill(app, {"COMMENT": "Loud"})
        await pilot.press("enter")
        assert table_markers(app) == ["", "✎"]
        assert len(app.edited_entries) == 1


async def test_edit_mark_and_divider_share_the_first_saved_row(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        await pilot.press("enter")
        await edit_row(app, pilot, 1)
        fill(app, {"COMMENT": "QSB"})
        await pilot.press("enter")
        assert table_markers(app) == ["•", "✎", ""]
        assert divider_rows(app) == [1]


async def test_cancelled_edit_leaves_no_mark(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 0)
        await pilot.press("escape")
        assert table_markers(app) == ["", ""]


async def test_edit_keeps_a_comment_longer_than_the_field_takes(app, settings_path):
    comment = "x" * (COMMENT_LENGTH + 20)
    path = write_two_saved(settings_path)
    path.write_text(LOG_HEADER + K1AAA_ROW.replace(",,", f",{comment},"))
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 0)
        fill(app, {"TIME": "2105"})
        await pilot.press("enter")
    assert path.read_text() == LOG_HEADER + K1AAA_ROW.replace(",,", f",{comment},").replace(
        "2100", "2105"
    )


async def test_edited_session_entry_stays_marked_in_typed_place(app, settings_path):
    async with app.run_test() as pilot:
        for call in ["W1ABC", "K2DEF"]:
            fill(app, ENTRY | {"CALL": call})
            await pilot.press("enter")
        await edit_row(app, pilot, 0)
        fill(app, {"CALL": "N3GHI", "DATE": "260924"})
        await pilot.press("enter")
        assert table_calls(app) == ["N3GHI", "K2DEF"]
        assert table_markers(app) == ["•", "•"]
        # Esc leaves the selection: a fresh entry, PWR and DATE carried
        # forward.
        await pilot.press("escape")
        assert field_values(app)["CALL"] == ""
        assert field_values(app)["DATE"] == "260925"
    # A new DATE moves it to that date's file.
    assert "N3GHI" in (settings_path.parent / "20260924.csv").read_text()
    assert "N3GHI" not in (settings_path.parent / "20260925.csv").read_text()


async def test_edit_goes_through_entry_checks(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 0)
        fill(app, {"TIME": "2460"})
        await pilot.press("enter")
        assert app.focused.id == "field-time"
        assert app.query_one(EntryForm).editing is not None


async def test_hand_edit_while_open_is_overwritten_by_the_next_save(app, settings_path):
    path = write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 0)
        # Edited by hand while the app was open: rows swapped, one changed.
        path.write_text(LOG_HEADER + K1BBB_ROW.replace("Loud", "Hand") + K1AAA_ROW)
        fill(app, {"TIME": "2105"})
        await pilot.press("enter")
        assert app.query_one(EntryForm).editing is None
    assert path.read_text() == LOG_HEADER + K1AAA_ROW.replace("2100", "2105") + K1BBB_ROW


def fail_to_write(monkeypatch, error=PermissionError(13, "Permission denied")):
    """Make every log file write fail, by default for permissions."""

    def replace(source, target):
        raise error

    monkeypatch.setattr("pota_logger.logbook.os.replace", replace)


WRITE_FAILED_MESSAGE = (
    "Couldn't save to 20260925.csv:\n"
    "Permission Denied - Check file system\n"
    "permissions on file.\n"
    "Enter to try again, or Esc to go back."
)


async def test_write_failed_for_another_reason_says_to_close_other_programs(
    app, monkeypatch
):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        fail_to_write(monkeypatch, OSError(16, "Device or resource busy"))
        await pilot.press("enter")
        assert app.screen.message == (
            "Couldn't save to 20260925.csv:\n"
            "Close all programs that have the file\n"
            "open. Changes made there will be lost, so\n"
            "copy them somewhere first if desired.\n"
            "Never edit a raw log during app use.\n"
            "Enter to try again, or Esc to go back."
        )


async def test_failed_write_opens_modal_and_esc_keeps_the_entry_typed(
    app, settings_path, monkeypatch
):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        typed = field_values(app)
        fail_to_write(monkeypatch)
        await pilot.press("enter")
        assert app.screen.message == WRITE_FAILED_MESSAGE
        await pilot.press("escape")
        assert field_values(app) == typed
        assert table_rows(app) == []
        assert app.query_one(EntryForm).logged == []
    assert not (settings_path.parent / "20260925.csv").exists()


async def test_enter_in_write_failed_modal_tries_again(app, settings_path, monkeypatch):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        fail_to_write(monkeypatch)
        await pilot.press("enter")
        # Still failing: the modal comes back.
        await pilot.press("enter")
        assert app.screen.message == WRITE_FAILED_MESSAGE
        monkeypatch.undo()
        await pilot.press("enter")
        assert not isinstance(app.screen, WarningScreen)
        assert table_rows(app) == [ENTRY_ROW]
        assert field_values(app)["CALL"] == ""
    assert "W1ABC" in (settings_path.parent / "20260925.csv").read_text()


async def test_failed_edit_write_stays_in_edit_mode(app, settings_path, monkeypatch):
    path = write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 0)
        fill(app, {"TIME": "2105"})
        fail_to_write(monkeypatch)
        await pilot.press("enter")
        assert app.screen.message == WRITE_FAILED_MESSAGE
        await pilot.press("escape")
        form = app.query_one(EntryForm)
        assert form.editing is not None
        assert field_values(app)["TIME"] == "2105"
        assert table_markers(app) == ["", ""]
    assert path.read_text() == LOG_HEADER + K1AAA_ROW + K1BBB_ROW


async def test_new_entry_is_highlighted_but_not_selected(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        for call in ["W1ABC", "K2DEF"]:
            fill(app, ENTRY | {"CALL": call})
            await pilot.press("enter")
        table = app.query_one("#log-table", DataTable)
        assert table.cursor_row == 1
        assert app.selected is None
        assert app.focused.id == "field-freq"
        # Tab into the log and Enter selects it.
        table.focus()
        await pilot.press("enter", "f3")
        assert field_values(app)["CALL"] == "K2DEF"


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


def required_message(app) -> str:
    return str(app.screen.query_one("#warning-message", Static).render())


async def test_no_station_callsign_opens_on_required_block(settings_path):
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        assert app.screen.id == "station-callsign-required"
        assert required_message(app) == (
            "A transmitting station callsign\nis required.\nPress Enter to go to Settings."
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
        assert len(app.screen_stack) == 1
        assert app.focused.id == "field-freq"
        assert station_callsign(app) == "W1TST"
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


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
    assert (settings_path.parent / "20260925.csv").read_text().splitlines()[1].endswith(",W1ABC")


async def test_loads_saved_callsign(app):
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


async def test_settings_shows_the_current_call(app):
    async with app.run_test() as pilot:
        await pilot.press("f2")
        assert app.focused.value == "W1TST"


async def test_save_uppercases_updates_status_and_file(app, settings_path):
    async with app.run_test() as pilot:
        # Typing replaces the call, selected on opening.
        await pilot.press("f2", *"w1abc", "enter")
        assert not isinstance(app.screen, SettingsScreen)
        assert station_callsign(app) == "W1ABC"
        assert load_settings(settings_path) == Settings(station_callsign="W1ABC")


async def test_save_button_saves(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2")
        app.screen.query_one("#station-callsign-input", Input).value = "W1ABC"
        await pilot.click("#save")
        assert load_settings(settings_path) == Settings(station_callsign="W1ABC")


async def test_invalid_station_callsign_is_refused(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2", *"w1tst/", "enter")
        assert isinstance(app.screen, SettingsScreen)
        assert app.focused.id == "station-callsign-input"
        assert [n.message for n in app._notifications] == [
            "Station callsign 'w1tst/' has an empty part next to a /"
        ]
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


async def test_non_ascii_station_callsign_is_refused(app, settings_path):
    async with app.run_test() as pilot:
        app.push_screen(SettingsScreen(Settings()))
        await pilot.pause()
        app.screen.query_one("#station-callsign-input", Input).value = "W1ABÇ"
        await pilot.press("enter")
        assert isinstance(app.screen, SettingsScreen)
        assert [n.message for n in app._notifications] == [
            "Station callsign 'W1ABÇ' has non-ASCII characters: 'Ç'.\n"
            "Use plain ASCII, like W1ABC."
        ]
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


async def test_cleared_station_callsign_saves_and_asks_for_one(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2")
        app.screen.query_one("#station-callsign-input", Input).value = "  "
        await pilot.press("enter")
        assert app.screen.id == "station-callsign-required"
        assert station_callsign(app) == "NOCALL"
        assert load_settings(settings_path) == Settings(station_callsign="")
        await pilot.press("enter")
        assert isinstance(app.screen, SettingsScreen)


async def open_settings_with(app, pilot, call: str) -> None:
    await pilot.press("f2")
    app.screen.query_one("#station-callsign-input", Input).value = call
    await pilot.press("enter")


async def test_unusual_station_callsign_warns_and_enter_saves(app, settings_path):
    async with app.run_test() as pilot:
        await open_settings_with(app, pilot, "w111111ab")
        assert isinstance(app.screen, CallsignWarningScreen)
        message = str(app.screen.query_one("#callsign-warning-message", Static).render())
        assert message.startswith("W111111AB is an unusual callsign.")
        await pilot.press("enter")
        assert not isinstance(app.screen, (CallsignWarningScreen, SettingsScreen))
        assert station_callsign(app) == "W111111AB"
        assert load_settings(settings_path) == Settings(station_callsign="W111111AB")


async def test_unusual_station_callsign_escape_returns_to_settings(app, settings_path):
    async with app.run_test() as pilot:
        await open_settings_with(app, pilot, "W11BC")
        await pilot.press("escape")
        assert isinstance(app.screen, SettingsScreen)
        assert app.focused.id == "station-callsign-input"
        assert app.focused.value == "W11BC"
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


async def test_unusual_station_callsign_corrected_in_warning(app, settings_path):
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
        assert load_settings(settings_path) == Settings(station_callsign="W1ABC")


async def test_f2_over_station_callsign_warning_does_not_stack(app):
    async with app.run_test() as pilot:
        await open_settings_with(app, pilot, "W11BC")
        await pilot.press("f2")
        assert isinstance(app.screen, CallsignWarningScreen)
        assert sum(isinstance(s, SettingsScreen) for s in app.screen_stack) == 1


async def test_escape_cancels_without_saving(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2", "backspace", "escape")
        assert not isinstance(app.screen, SettingsScreen)
        assert station_callsign(app) == "W1TST"
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


async def test_cancel_button_cancels(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2", "backspace")
        await pilot.click("#cancel")
        assert station_callsign(app) == "W1TST"
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


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
        assert app.screen.id == "station-callsign-required"
        messages = [n.message for n in app._notifications]
        assert len(messages) == 1
        assert str(settings_path) in messages[0]


async def test_bad_station_callsign_in_file_is_reported_and_shown_to_fix(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('station_callsign = "W1"\n')
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        assert station_callsign(app) == "NOCALL"
        assert app.screen.id == "station-callsign-required"
        assert [n.message for n in app._notifications] == [
            f"{settings_path}: station_callsign 'W1' doesn't look like a callsign, like W1ABC"
        ]
        # In Settings to correct, and back there if cancelled.
        await pilot.press("enter")
        assert app.focused.value == "W1"
        await pilot.press("escape", "enter")
        assert app.focused.value == "W1"
        await pilot.press("end", *"TST", "enter")
        assert len(app.screen_stack) == 1
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


@pytest.mark.parametrize(
    "call, problem",
    [("w1tst", "should be uppercase, like W1TST"), (" W1TST ", "should have no spaces around it, like W1TST")],
)
async def test_station_callsign_in_file_must_be_as_saved(settings_path, call, problem):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(f'station_callsign = "{call}"\n')
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        assert station_callsign(app) == "NOCALL"
        assert [n.message for n in app._notifications] == [
            f"{settings_path}: station_callsign {call!r} {problem}"
        ]
        await pilot.press("enter")
        assert app.focused.value == call
        # Saved as the settings modal saves it.
        await pilot.press("enter")
        assert station_callsign(app) == "W1TST"
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")
