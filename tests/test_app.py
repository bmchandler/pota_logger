import re
from collections import Counter
from datetime import date, time

import pytest
from conftest import LIST, NEWER_LIST
from textual.command import CommandPalette
from textual.containers import Vertical
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Static

from pota_logger.app import PotaLoggerApp, header_cell, mark_count_lines, sort_key
from pota_logger.fields import dates
from pota_logger.screens.callsign_warning_screen import CallsignWarningScreen
from pota_logger.screens.delete_screen import DeleteScreen
from pota_logger.screens.export_screen import ExportScreen
from pota_logger.entry_form import (
    COMMENT_LENGTH,
    FIELDS,
    LOG_FIELDS,
    ROW_FIELDS,
    EntryForm,
    pota_info,
)
from pota_logger.parks_list import download_parks, md5_etag, parks_folder
from pota_logger.screens.parks_offer_screen import ParksOfferScreen
from pota_logger.record_ids import new_id, parse_id
from pota_logger.settings import Settings, load_settings, save_settings
from pota_logger.screens.settings_screen import SettingsScreen
from pota_logger.screens.warning_screen import WarningScreen


def station_callsign(app) -> str:
    return str(app.query_one("#station-callsign", Static).render())


# Layout


async def test_focus_starts_on_freq(app):
    async with app.run_test():
        assert app.focused.id == "field-freq"


async def test_uses_pota_theme(app):
    async with app.run_test():
        assert app.theme == "pota"


def footer_keys(app) -> list[str]:
    return [key for key, active in app.screen.active_bindings.items() if active.binding.show]


async def test_footer_shows_quit_settings_edit_delete_sort_export_and_screenshot(app):
    async with app.run_test():
        assert footer_keys(app) == ["ctrl+q", "f2", "f3", "f4", "f5", "f6", "ctrl+s"]


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


async def test_notifications_sit_a_row_above_the_buttons_and_log_scrollbar(app):
    async with app.run_test(size=(90, 34), notifications=True) as pilot:
        app.notify("First")
        app.notify("Second")
        await pilot.pause(0.5)
        toast = app.screen.query("Toast").last()
        table = app.query_one("#log-table", DataTable)
        buttons = app.query_one("#button-bar")
        # The log scrolls sideways at this width: its scrollbar, then a gap.
        assert table.show_horizontal_scrollbar
        assert toast.region.bottom == buttons.region.y - 2
        # Wide enough for the whole log, so just the gap.
        await pilot.resize_terminal(233, 34)
        await pilot.pause(0.5)
        assert not table.show_horizontal_scrollbar
        assert toast.region.bottom == buttons.region.y - 1


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
        field = app.query_one(f"#field-{ROW_FIELDS[-1][0].lower()}", Input)
        field.focus()
        # Focus queues a scroll into view, which then animates.
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        assert form.scroll_x > 0
        assert form.region.contains_region(field.region)


async def test_tab_order_follows_entry_order_then_table(app):
    # Fields typed on every entry first; PWR, DATE, and MODE carry
    # forward, so they come last.
    entry_order = ["FREQ", "CALL", "PARK", "ST", "SNT", "RCD", "TIME", "PWR", "DATE", "MODE"]
    async with app.run_test():
        chain = [w.id for w in app.screen.focus_chain]
        assert chain == [f"field-{name.lower()}" for name in entry_order + ["COMMENT"]] + [
            "log-table"
        ]


async def test_log_table_columns_keep_paper_log_order(app):
    paper_log = ["FREQ", "MODE", "CALL", "PARK", "ST", "SNT", "RCD", "PWR", "DATE", "TIME"]
    async with app.run_test():
        table = app.query_one("#log-table", DataTable)
        # The first column, with no header, holds the session marker.
        labels = [str(c.label).strip() for c in table.columns.values()]
        assert labels == [""] + paper_log + ["COMMENT"]


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


def mark_counts(app) -> list[str]:
    """The lines counting marked rows, beside the Quit button."""
    text = str(app.query_one("#mark-counts", Static).render())
    return text.splitlines()


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
        # Filled to near the limit, then typed past it.
        field.value = "x" * (COMMENT_LENGTH - 2)
        await pilot.press("end", *"yyyyy")
        assert field.value == "x" * (COMMENT_LENGTH - 2) + "yy"
        # +1 for the cursor
        assert field.content_region.width >= COMMENT_LENGTH + 1


def comment_column_width(app) -> int:
    """COMMENT's log column width, less the padding each cell carries."""
    columns = list(app.query_one("#log-table", DataTable).columns.values())
    assert [str(c.label).strip() for c in columns[-2:]] == ["TIME", "COMMENT"]
    return columns[-1].width - 2


def log_fills_its_width(app) -> bool:
    """The log's columns end at its right edge (beside any vertical
    scrollbar), with no sideways scrollbar.
    """
    table = app.query_one("#log-table", DataTable)
    columns = sum(column.width for column in table.columns.values())
    return columns == table.scrollable_content_region.width and not table.show_horizontal_scrollbar


async def test_comment_column_follows_time_at_least_its_headers_width(app):
    # Narrower than the log, so COMMENT gets no more than its header.
    async with app.run_test(size=(80, 24)):
        assert comment_column_width(app) == len("COMMENT")
        assert app.query_one("#log-table", DataTable).show_horizontal_scrollbar


async def test_comment_column_fills_the_logs_width_as_the_window_changes(app):
    async with app.run_test(size=(107, 24)) as pilot:
        assert log_fills_its_width(app)
        await pilot.resize_terminal(150, 24)
        await pilot.pause()
        assert log_fills_its_width(app)
        await pilot.resize_terminal(107, 24)
        await pilot.pause()
        assert log_fills_its_width(app)


async def test_comment_column_widens_to_the_longest_comment_typed(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"COMMENT": "QSB"})
        await pilot.press("enter")
        assert comment_column_width(app) == len("COMMENT")
        fill(app, ENTRY | {"CALL": "K2DEF", "COMMENT": "RSGB Field Day Serial #042"})
        await pilot.press("enter")
        assert comment_column_width(app) == len("RSGB Field Day Serial #042")


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


# COMMENT's POTA info (Settings)


@pytest.mark.parametrize(
    "park, state, info",
    [
        ("1234", "NJ", "POTA US-1234 NJ"),
        ("1234", "nj", "POTA US-1234 NJ"),
        ("1234", "", "POTA US-1234"),
        ("bb10", "", "POTA BB-0010"),
        ("US-4566@US-WY", "WY", "POTA"),
        # An ST that isn't a state is left out; an ST alone waits for PARK.
        ("1234", "XX", "POTA US-1234"),
        ("", "NJ", "POTA"),
        ("12345678", "NJ", "POTA"),
        ("１２３４", "", "POTA"),
        ("1234", "ＮＪ", "POTA US-1234"),
    ],
)
def test_pota_info(park, state, info):
    assert pota_info(park, state) == info


@pytest.fixture
def pota_app(settings_path):
    """The app with both POTA info settings on."""
    save_settings(
        Settings("W1TST", new_comment_pota_info=True, edit_comment_pota_info=True), settings_path
    )
    return PotaLoggerApp(settings_path=settings_path)


def comment(app) -> str:
    return app.query_one("#field-comment", Input).value


async def type_and_leave(app, pilot, name: str, value: str) -> None:
    """Set a field's value from inside it, then Tab out."""
    field = app.query_one(f"#field-{name.lower()}", Input)
    field.focus()
    field.value = value
    await pilot.press("tab")


async def test_comment_starts_blank_with_the_setting_off(app):
    async with app.run_test() as pilot:
        await type_and_leave(app, pilot, "PARK", "1234")
        assert comment(app) == ""


async def test_new_comment_starts_with_pota_then_park_then_state(pota_app):
    app = pota_app
    async with app.run_test() as pilot:
        assert comment(app) == "POTA "
        await type_and_leave(app, pilot, "PARK", "1234")
        assert comment(app) == "POTA US-1234"
        await type_and_leave(app, pilot, "ST", "nj")
        assert comment(app) == "POTA US-1234 NJ"
        await type_and_leave(app, pilot, "ST", "")
        assert comment(app) == "POTA US-1234"


async def test_state_before_park_waits_for_it(pota_app):
    app = pota_app
    async with app.run_test() as pilot:
        await type_and_leave(app, pilot, "ST", "NJ")
        assert comment(app) == "POTA "
        await type_and_leave(app, pilot, "PARK", "1234")
        assert comment(app) == "POTA US-1234 NJ"
        # A park that doesn't read goes back to waiting.
        await type_and_leave(app, pilot, "PARK", "12345678")
        assert comment(app) == "POTA "


async def test_pota_info_rewritten_keeping_what_follows(pota_app):
    app = pota_app
    async with app.run_test() as pilot:
        await type_and_leave(app, pilot, "PARK", "1234")
        await type_and_leave(app, pilot, "ST", "NJ")
        app.query_one("#field-comment", Input).value += " Great signal"
        await type_and_leave(app, pilot, "PARK", "5678")
        assert comment(app) == "POTA US-5678 NJ Great signal"
        await type_and_leave(app, pilot, "ST", "")
        assert comment(app) == "POTA US-5678 Great signal"


async def test_text_typed_after_a_bare_pota_is_left_alone(pota_app):
    # Most likely POTA info typed by hand.
    app = pota_app
    async with app.run_test() as pilot:
        app.query_one("#field-comment", Input).value = "POTA US-9999"
        await type_and_leave(app, pilot, "PARK", "1234")
        assert comment(app) == "POTA US-9999"


async def test_pota_info_typed_by_hand_is_not_repeated(pota_app):
    app = pota_app
    async with app.run_test() as pilot:
        app.query_one("#field-comment", Input).value = "POTA US-1234 NJ Great signal"
        await type_and_leave(app, pilot, "PARK", "1234")
        await type_and_leave(app, pilot, "ST", "NJ")
        assert comment(app) == "POTA US-1234 NJ Great signal"
        # Then it's the app's to rewrite.
        await type_and_leave(app, pilot, "ST", "")
        assert comment(app) == "POTA US-1234 Great signal"


async def test_pota_info_changed_by_hand_is_left_alone(pota_app):
    app = pota_app
    async with app.run_test() as pilot:
        await type_and_leave(app, pilot, "PARK", "1234")
        app.query_one("#field-comment", Input).value = "POTA US-1243"
        await type_and_leave(app, pilot, "PARK", "5678")
        assert comment(app) == "POTA US-1243"
        app.query_one("#field-comment", Input).value = "Field Day"
        await type_and_leave(app, pilot, "PARK", "1234")
        assert comment(app) == "Field Day"


async def test_pota_info_left_as_is_if_it_would_not_fit(pota_app):
    app = pota_app
    async with app.run_test() as pilot:
        await type_and_leave(app, pilot, "PARK", "1234")
        full = "POTA US-1234 " + "x" * (COMMENT_LENGTH - len("POTA US-1234 "))
        app.query_one("#field-comment", Input).value = full
        await type_and_leave(app, pilot, "ST", "NJ")
        assert comment(app) == full


async def test_enter_in_park_saves_its_pota_info_then_starts_over(pota_app):
    app = pota_app
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"PARK": "", "ST": "NJ", "COMMENT": "POTA "})
        app.query_one("#field-park", Input).focus()
        await pilot.press(*"1234", "enter")
        assert table_rows(app)[0][-1] == "POTA US-1234 NJ"
        assert comment(app) == "POTA "
        assert app.focused.id == "field-freq"


async def test_pota_info_kept_while_an_entry_is_shown(pota_app):
    app = pota_app
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"COMMENT": "Saved"})
        await pilot.press("enter")
        await type_and_leave(app, pilot, "PARK", "1234")
        await select_row(app, pilot, 0)
        assert comment(app) == "Saved"
        await pilot.press("escape")
        assert comment(app) == "POTA US-1234"
        await type_and_leave(app, pilot, "ST", "NJ")
        assert comment(app) == "POTA US-1234 NJ"


async def test_edited_comment_updated_from_its_park_and_state(pota_app):
    app = pota_app
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"COMMENT": "POTA US-1234 NJ Great signal"})
        await pilot.press("enter")
        await edit_row(app, pilot, 0)
        await type_and_leave(app, pilot, "PARK", "5678")
        assert comment(app) == "POTA US-5678 NJ Great signal"
        await pilot.press("enter")
        assert table_rows(app)[0][-1] == "POTA US-5678 NJ Great signal"


async def test_edited_comment_without_its_pota_info_left_alone(pota_app):
    app = pota_app
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"CALL": "W1AAA", "COMMENT": ""})
        await pilot.press("enter")
        fill(app, ENTRY | {"CALL": "W1AAB", "COMMENT": "POTA US-9999"})
        await pilot.press("enter")
        for row in (0, 1):
            await edit_row(app, pilot, row)
            await type_and_leave(app, pilot, "PARK", "5678")
            assert comment(app) == field_values(app)["COMMENT"] == ["", "POTA US-9999"][row]
            await pilot.press("escape", "escape")


async def test_edited_comment_left_alone_with_the_edit_setting_off(settings_path):
    save_settings(Settings("W1TST", new_comment_pota_info=True), settings_path)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"COMMENT": "POTA US-1234 NJ"})
        await pilot.press("enter")
        await edit_row(app, pilot, 0)
        await type_and_leave(app, pilot, "PARK", "5678")
        assert comment(app) == "POTA US-1234 NJ"


async def test_setting_turned_on_or_off_mid_entry(app):
    async with app.run_test() as pilot:
        await type_and_leave(app, pilot, "PARK", "1234")
        await pilot.press("f2", "space")
        await pilot.click("#save")
        assert comment(app) == "POTA US-1234"
        await pilot.press("f2", "space")
        await pilot.click("#save")
        assert comment(app) == ""


async def test_setting_turned_off_keeps_a_comment_typed_on(pota_app):
    app = pota_app
    async with app.run_test() as pilot:
        await type_and_leave(app, pilot, "PARK", "1234")
        app.query_one("#field-comment", Input).value += " Great signal"
        await pilot.press("f2", "space")
        await pilot.click("#save")
        assert comment(app) == "POTA US-1234 Great signal"
        await type_and_leave(app, pilot, "PARK", "5678")
        assert comment(app) == "POTA US-1234 Great signal"


# Storage

LOG_HEADER = "FREQ,MODE,CALL,PARK,ST,SNT,RCD,PWR,DATE,TIME,COMMENT,STATION_CALLSIGN,UUIDv4\n"


async def test_entry_is_saved_to_its_dates_file(app, settings_path):
    async with app.run_test() as pilot:
        fill(app, ENTRY | {"COMMENT": "Nice, loud"})
        await pilot.press("enter")
    header, row = (settings_path.parent / "20260925.csv").read_text().splitlines()
    assert header == LOG_HEADER.rstrip()
    saved, record_id = row.rsplit(",", 1)
    assert saved == '14285500,USB,W1ABC,US-1234,NJ,59,57,60,20260925,1953,"Nice, loud",W1TST'
    assert parse_id(record_id) == record_id


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
            LOG_HEADER
            + "".join(
                f"14285500,USB,{call},US-1234,NJ,59,57,60,{date},{time},,W1TST,{new_id()}\n"
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
        # And drawn with the overline, to the log's right edge.
        drawn = table.render_line(3)
        assert drawn.cell_length == table.size.width
        assert all(segment.style.overline for segment in drawn if segment.text)


async def test_no_divider_without_saved_entries(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        await pilot.press("enter")
        await pilot.pause()
        assert divider_rows(app) == []



# Sorting

# The log's column index of each field (the marker column is 0).
LOG_COLUMN = {name: index for index, (name, _, _) in enumerate(LOG_FIELDS, start=1)}


def headers(app) -> list[str]:
    table = app.query_one("#log-table", DataTable)
    return [str(column.label).strip() for column in table.columns.values()]


async def press_sort(app, pilot, name: str) -> None:
    """Put the cell cursor in a field's column and press f5."""
    app.query_one("#log-table", DataTable).move_cursor(column=LOG_COLUMN[name])
    await pilot.press("f5")


async def click_header(app, pilot, name: str) -> None:
    table = app.query_one("#log-table", DataTable)
    widths = [column.width for column in table.columns.values()]
    x = sum(widths[: LOG_COLUMN[name]]) + 1 - int(table.scroll_x)
    await pilot.click(table, offset=(x, 0))


THREE_SAVED = {
    "20260925": [
        ("K1BBB", "20260925", "1900"),
        ("W1CCC", "20260925", "0100"),
        ("k1aaa", "20260925", "2100"),
    ],
}


def test_date_sorts_by_date_then_time_and_time_by_time_of_day_alone():
    def entry(day, hour):
        return {"DATE": date(2026, 9, day), "TIME": time(hour, 0)}

    entries = [entry(25, 23), entry(24, 1), entry(25, 1), entry(24, 23)]
    by_date = sorted(entries, key=lambda e: sort_key(e, "DATE"))
    assert by_date == [entry(24, 1), entry(24, 23), entry(25, 1), entry(25, 23)]
    by_time = sorted(entries, key=lambda e: sort_key(e, "TIME"))
    assert by_time == [entry(24, 1), entry(25, 1), entry(24, 23), entry(25, 23)]


def test_sort_key_ignores_case_then_goes_by_timestamp():
    early = {"CALL": "w1abc", "DATE": date(2026, 9, 25), "TIME": 1, "FREQ": 7030000}
    late = early | {"CALL": "W1ABC", "TIME": 2, "FREQ": 14285500}
    assert sort_key(early, "CALL") < sort_key(late, "CALL")
    # Numbers as numbers: 7 MHz before 14 MHz.
    assert sort_key(early, "FREQ") < sort_key(late, "FREQ")


def test_header_arrow_follows_the_label_or_takes_the_padding():
    assert str(header_cell("CALL", 12)) == " CALL         "
    assert str(header_cell("CALL", 12, "▲")) == " CALL ▲       "
    # No room for a space and the arrow: it takes the right padding.
    assert str(header_cell("ST", 2, "▼")) == " ST▼"
    assert str(header_cell("ST", 2)) == " ST "


async def test_f5_sorts_by_the_cursors_column_ascending_then_descending(app, settings_path):
    write_saved_log(settings_path, THREE_SAVED)
    async with app.run_test(size=(107, 24)) as pilot:
        assert table_calls(app) == ["K1AAA", "K1BBB", "W1CCC"]
        assert "CALL" in headers(app)
        await press_sort(app, pilot, "TIME")
        assert table_calls(app) == ["W1CCC", "K1BBB", "K1AAA"]
        assert "TIME ▲" in headers(app)
        await pilot.press("f5")
        assert table_calls(app) == ["K1AAA", "K1BBB", "W1CCC"]
        assert "TIME ▼" in headers(app)
        # Another column starts ascending, and only it shows an arrow.
        await press_sort(app, pilot, "CALL")
        assert table_calls(app) == ["K1AAA", "K1BBB", "W1CCC"]
        assert [header for header in headers(app) if header.endswith(("▲", "▼"))] == ["CALL ▲"]
        # The cursor goes to the top of the sorted column.
        table = app.query_one("#log-table", DataTable)
        assert table.cursor_coordinate == (0, LOG_COLUMN["CALL"])


async def test_sort_ties_go_by_timestamp(app, settings_path):
    write_saved_log(settings_path, THREE_SAVED)
    async with app.run_test(size=(107, 24)) as pilot:
        # Every MODE is USB.
        await press_sort(app, pilot, "MODE")
        assert table_calls(app) == ["W1CCC", "K1BBB", "K1AAA"]
        await pilot.press("f5")
        assert table_calls(app) == ["K1AAA", "K1BBB", "W1CCC"]


async def test_f5_on_the_marker_column_does_nothing(app, settings_path):
    write_saved_log(settings_path, THREE_SAVED)
    async with app.run_test(size=(107, 24)) as pilot:
        app.query_one("#log-table", DataTable).move_cursor(column=0)
        await pilot.press("f5")
        assert table_calls(app) == ["K1AAA", "K1BBB", "W1CCC"]
        assert app.sort_by is None


async def test_header_click_sorts_by_that_column(app, settings_path):
    write_saved_log(settings_path, THREE_SAVED)
    async with app.run_test(size=(107, 24)) as pilot:
        await click_header(app, pilot, "TIME")
        assert table_calls(app) == ["W1CCC", "K1BBB", "K1AAA"]
        assert "TIME ▲" in headers(app)
        await click_header(app, pilot, "TIME")
        assert table_calls(app) == ["K1AAA", "K1BBB", "W1CCC"]
        assert "TIME ▼" in headers(app)


async def test_sort_takes_in_typed_entries_and_new_ones_go_above(app, settings_path):
    write_saved_log(settings_path, THREE_SAVED)
    async with app.run_test(size=(107, 24)) as pilot:
        for call, time in [("N3GHI", "2010"), ("K2DEF", "0030")]:
            fill(app, ENTRY | {"CALL": call, "TIME": time})
            await pilot.press("enter")
        assert divider_rows(app) == [2]
        await press_sort(app, pilot, "TIME")
        assert table_calls(app) == ["K2DEF", "W1CCC", "K1BBB", "N3GHI", "K1AAA"]
        # They keep their marks; nothing's in typed order, so no divider.
        assert table_markers(app) == ["•", "", "", "•", ""]
        assert divider_rows(app) == []
        # One typed after the sort goes above, with the divider back.
        fill(app, ENTRY | {"CALL": "W4JKL", "TIME": "1200"})
        await pilot.press("enter")
        assert table_calls(app) == ["W4JKL", "K2DEF", "W1CCC", "K1BBB", "N3GHI", "K1AAA"]
        assert table_markers(app) == ["•", "•", "", "", "•", ""]
        assert divider_rows(app) == [1]
        # The cursor kept its column, so f5 sorts it again, now
        # descending, taking that one in too.
        await pilot.press("f5")
        assert table_calls(app) == ["K1AAA", "N3GHI", "K1BBB", "W4JKL", "W1CCC", "K2DEF"]


async def test_refused_rows_stay_on_top_whatever_the_sort(app, settings_path):
    write_refused(settings_path)
    async with app.run_test(size=(107, 24)) as pilot:
        for _ in range(2):
            await press_sort(app, pilot, "CALL")
            assert table_calls(app) == ["K1BBB", "K1AAA"]
            assert table_markers(app) == ["!", ""]
        assert "CALL ▼" in headers(app)


async def test_no_sort_while_a_row_is_selected(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test(size=(107, 24)) as pilot:
        await select_row(app, pilot, 1)
        await pilot.press("f5")
        await click_header(app, pilot, "TIME")
        assert app.sort_by is None
        assert table_calls(app) == ["K1AAA", "K1BBB"]
        assert app.selected["CALL"] == "K1BBB"
        # Shown dimmed in the footer.
        assert not app.screen.active_bindings["f5"].enabled
        # Nor while editing.
        await pilot.press("f3", "f5")
        await click_header(app, pilot, "TIME")
        assert app.sort_by is None
        # Back to the cell cursor, it sorts.
        await pilot.press("escape", "escape")
        assert app.screen.active_bindings["f5"].enabled
        await click_header(app, pilot, "TIME")
        assert table_calls(app) == ["K1BBB", "K1AAA"]


async def test_sort_does_nothing_under_a_modal(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test(size=(107, 24)) as pilot:
        await select_row(app, pilot, 0)
        await pilot.press("f4")
        assert isinstance(app.screen, DeleteScreen)
        # f5 on its own, as it's dimmed while a row is selected.
        app.action_sort()
        assert app.sort_by is None

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


BROKEN_ROW = "14285500,USB,W1ABC,US-1234,NJ,59,57,60,20260925,1953,W1TST\n"


def file_errors_text(settings_path) -> list[str]:
    """file_errors.txt's lines below its header (written time, what to do,
    a blank line).
    """
    return (settings_path.parent / "file_errors.txt").read_text().splitlines()[3:]


async def test_row_too_broken_to_split_blocks_until_fixed_by_hand(app, settings_path):
    path = settings_path.parent / "20260925.csv"
    path.write_text(LOG_HEADER + BROKEN_ROW)
    async with app.run_test() as pilot:
        assert table_rows(app) == []
        assert not app._notifications
        assert app.screen.id == "file-errors"
        assert app.screen.message == (
            "Manual data correction required.\n"
            f"See {settings_path.parent / 'file_errors.txt'}\n"
            "\n"
            "Fix the files, then start the app again."
        )
        assert file_errors_text(settings_path) == [f"{path} row 2: has 11 values, should have 13"]
        # No Settings over it, and Enter quits.
        await pilot.press("f2")
        assert app.screen.id == "file-errors"
        await pilot.press("enter")
        assert not app.is_running


async def test_unreadable_file_and_broken_row_are_listed_in_file_order(app, settings_path):
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    first = settings_path.parent / "20260924.csv"
    first.write_bytes(b"\xff\xfe not text")
    second = settings_path.parent / "20260925.csv"
    second.write_text(LOG_HEADER + BROKEN_ROW)
    async with app.run_test():
        assert app.screen.id == "file-errors"
    assert file_errors_text(settings_path) == [
        f"{first}: isn't plain text (UTF-8)",
        f"{second} row 2: has 11 values, should have 13",
    ]


async def test_clean_start_removes_an_old_file_errors_list(app, settings_path):
    errors = settings_path.parent / "file_errors.txt"
    errors.write_text("Written by pota-logger at start, 2026-10-01 12:00 UTC.\n")
    async with app.run_test():
        assert app.screen.id != "file-errors"
    assert not errors.exists()


async def test_file_errors_list_that_cant_be_written_blocks_all_the_same(
    app, settings_path, monkeypatch
):
    (settings_path.parent / "20260925.csv").write_text(LOG_HEADER + BROKEN_ROW)

    def fail(*args):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr("pota_logger.file_errors.record", fail)
    async with app.run_test():
        assert app.screen.message == (
            "Manual data correction required.\n"
            "Couldn't write to file or directory.\n"
            "Check permissions.\n"
            "\n"
            "Fix the permissions, then start the app again."
        )


# Editing

K1AAA_ID = "1b4e28ba-2fa1-4d2b-883f-0016d3cca427"
K1BBB_ID = "9f2c4e1a-7b3d-4c8e-a5f6-0123456789ab"
K1AAA_ROW = f"14285500,USB,K1AAA,US-1234,NJ,59,57,60,20260925,2100,,W1TST,{K1AAA_ID}\n"
K1BBB_ROW = f"7030000,CW,K1BBB,US-5678,,599,579,0.5,20260925,1900,Loud,W1TST,{K1BBB_ID}\n"


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
        # Not checked against itself: an entry is no dupe of itself.
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


async def test_unchanged_edit_saves_nothing_and_leaves_no_mark(app, settings_path):
    path = write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 1)
        # The same values, typed another way.
        fill(app, {"FREQ": "7.03", "PWR": ".5", "PARK": "5678", "MODE": "cw"})
        await pilot.press("enter")
        assert not isinstance(app.screen, WarningScreen)
        assert app.query_one(EntryForm).editing is None
        assert app.selected["CALL"] == "K1BBB"
        assert app.focused.id == "log-table"
        assert table_markers(app) == ["", ""]
        assert not app._notifications
    assert path.read_text() == LOG_HEADER + K1AAA_ROW + K1BBB_ROW


async def test_unchanged_edit_skips_the_warnings(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY | FUTURE)
        await pilot.press("enter", "enter")
        await edit_row(app, pilot, 0)
        await pilot.press("enter")
        assert not isinstance(app.screen, WarningScreen)
        assert app.query_one(EntryForm).editing is None
        assert table_markers(app) == ["•"]


async def test_unchanged_edit_after_a_change_stays_marked_once(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 1)
        fill(app, {"COMMENT": "QSB"})
        await pilot.press("enter", "f3", "enter")
        assert table_markers(app) == ["", "✎"]
        assert len(app.edited_entries) == 1


async def test_bad_field_in_an_edit_is_refused_before_the_unchanged_check(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 1)
        fill(app, {"TIME": "2500"})
        await pilot.press("enter")
        assert app.query_one(EntryForm).editing is not None
        assert app.focused.id == "field-time"


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


async def test_comment_column_shows_a_files_longer_comment_whole_until_deleted(
    app, settings_path
):
    comment = "x" * (COMMENT_LENGTH + 20)
    path = write_two_saved(settings_path)
    path.write_text(LOG_HEADER + K1AAA_ROW.replace(",,", f",{comment},") + K1BBB_ROW)
    async with app.run_test() as pilot:
        assert comment_column_width(app) == len(comment)
        assert table_rows(app)[0][-1] == comment
        await select_row(app, pilot, 0)
        await pilot.press("f4", "enter", "enter")
        assert table_calls(app) == ["K1BBB"]
        assert comment_column_width(app) == len("COMMENT")


async def test_comment_column_fills_the_width_beside_the_logs_scrollbar(app, settings_path):
    rows = [K1AAA_ROW.replace("K1AAA", f"K1A{letter}") for letter in "ABCDEFGHIJKLMNOP"]
    rows = [row.replace(K1AAA_ID, new_id()) for row in rows]
    write_two_saved(settings_path).write_text(LOG_HEADER + "".join(rows))
    async with app.run_test(size=(107, 24)) as pilot:
        await pilot.pause()
        assert app.query_one("#log-table", DataTable).show_vertical_scrollbar
        assert log_fills_its_width(app)


async def test_log_fitted_to_a_new_width_keeps_the_selected_row(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test(size=(107, 24)) as pilot:
        await select_row(app, pilot, 1)
        await pilot.resize_terminal(150, 24)
        await pilot.pause()
        assert log_fills_its_width(app)
        table = app.query_one("#log-table", DataTable)
        assert (table.cursor_type, table.cursor_row) == ("row", 1)
        assert app.selected["CALL"] == "K1BBB"
        assert field_values(app)["CALL"] == "K1BBB"


async def test_log_fitted_after_a_resize_under_a_modal(app):
    async with app.run_test(size=(107, 24)) as pilot:
        await pilot.press("f2")
        await pilot.resize_terminal(150, 24)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert log_fills_its_width(app)


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
        # Esc leaves the selection: a fresh entry, PWR, DATE, and MODE
        # carried forward.
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


# Deleting

K1BBB_DELETE_MESSAGE = (
    "Delete this record?\n"
    "K1BBB on 7.030.000 CW\n"
    "2026.09.25 19:00 UTC\n"
    "Gone is gone: there's no undo.\n"
)


async def test_f4_with_no_row_selected_says_how_to_select(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await pilot.press("f4")
        assert list(app._notifications)[-1].message == (
            "Double-click a record or press Enter when log area has focus first."
        )
        assert not isinstance(app.screen, DeleteScreen)


async def test_delete_takes_enter_twice(app, settings_path):
    path = write_two_saved(settings_path)
    async with app.run_test() as pilot:
        fill(app, {"CALL": "W1ABC"})
        await select_row(app, pilot, 1)
        await pilot.press("f4")
        assert app.screen.message == (
            K1BBB_DELETE_MESSAGE + "Enter twice to delete, or Esc to keep it."
        )
        await pilot.press("enter")
        assert app.screen.message == (
            K1BBB_DELETE_MESSAGE + "Enter again to delete, or Esc to keep it."
        )
        assert path.read_text() == LOG_HEADER + K1AAA_ROW + K1BBB_ROW
        await pilot.press("enter")
        assert not isinstance(app.screen, DeleteScreen)
        assert table_calls(app) == ["K1AAA"]
        # Nothing selected, and the entry put aside is back.
        assert app.selected is None
        assert app.query_one("#log-table", DataTable).cursor_type == "cell"
        assert field_values(app)["CALL"] == "W1ABC"
        assert not form_disabled(app)
        assert all(entry["CALL"] != "K1BBB" for entry in app.query_one(EntryForm).logged)
    assert path.read_text() == LOG_HEADER + K1AAA_ROW


async def test_escape_keeps_the_entry_even_after_one_enter(app, settings_path):
    path = write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await select_row(app, pilot, 1)
        await pilot.press("f4", "enter", "escape")
        assert not isinstance(app.screen, DeleteScreen)
        assert table_calls(app) == ["K1AAA", "K1BBB"]
        assert app.selected is app.saved_entries[1]
    assert path.read_text() == LOG_HEADER + K1AAA_ROW + K1BBB_ROW


async def test_delete_button_tabbed_to_takes_enter_twice(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await select_row(app, pilot, 1)
        await pilot.press("f4", "tab", "tab")
        assert app.focused.id == "confirm"
        await pilot.press("enter")
        # A button takes no second press during its 0.2 second press
        # effect (stock).
        await pilot.pause(0.25)
        assert isinstance(app.screen, DeleteScreen)
        assert app.screen.armed
        await pilot.press("enter")
        # The button's press is a message, handled after the key.
        await pilot.pause()
        assert table_calls(app) == ["K1AAA"]


async def test_back_button_tabbed_to_keeps_the_entry(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await select_row(app, pilot, 1)
        await pilot.press("f4", "tab", "enter")
        assert not isinstance(app.screen, DeleteScreen)
        assert table_calls(app) == ["K1AAA", "K1BBB"]


async def test_delete_while_editing_drops_the_edit(app, settings_path):
    path = write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 0)
        fill(app, {"COMMENT": "Changed"})
        await pilot.press("f4", "enter", "enter")
        assert table_calls(app) == ["K1BBB"]
        form = app.query_one(EntryForm)
        assert form.editing is None
        assert form.border_title is None
        assert app.query_one("#log-table", DataTable).can_focus
        assert field_values(app)["COMMENT"] == ""
    assert path.read_text() == LOG_HEADER + K1BBB_ROW


async def test_deleted_session_entry_leaves_the_log_and_its_file(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        await pilot.press("enter")
        await select_row(app, pilot, 0)
        await pilot.press("f4", "enter", "enter")
        assert table_calls(app) == ["K1AAA", "K1BBB"]
        assert table_markers(app) == ["", ""]
        assert divider_rows(app) == []
    assert "W1ABC" not in (settings_path.parent / "20260925.csv").read_text()


async def test_failed_delete_write_keeps_the_entry(app, settings_path, monkeypatch):
    path = write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await select_row(app, pilot, 1)
        fail_to_write(monkeypatch)
        await pilot.press("f4", "enter", "enter")
        assert app.screen.message == WRITE_FAILED_MESSAGE
        await pilot.press("escape")
        assert table_calls(app) == ["K1AAA", "K1BBB"]
        assert app.selected is app.saved_entries[1]
    assert path.read_text() == LOG_HEADER + K1AAA_ROW + K1BBB_ROW


# Refused rows, fixed in the app

REFUSED_ROW = f"7030000,cw,K1BBB,1234,,599,579,.5,20260925,53,Loud,W1TST,{K1BBB_ID}\n"
# As the app keeps it, with how MODE and PWR are written fixed on load:
# still refused for PARK and TIME, which it doesn't change.
REFUSED_FIXED = REFUSED_ROW.replace(",cw,", ",CW,").replace(",.5,", ",0.5,")


def write_refused(settings_path, refused=REFUSED_ROW):
    """K1AAA on 2026-09-26, then K1BBB refused in 2026-09-25's file."""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    (settings_path.parent / "20260926.csv").write_text(
        LOG_HEADER + K1AAA_ROW.replace("20260925", "20260926")
    )
    path = settings_path.parent / "20260925.csv"
    path.write_text(LOG_HEADER + refused)
    return path


async def test_refused_row_shown_as_is_and_marked_at_the_top(app, settings_path):
    path = write_refused(settings_path)
    async with app.run_test():
        # Above K1AAA, though K1AAA is newer.
        assert table_calls(app) == ["K1BBB", "K1AAA"]
        assert table_markers(app) == ["!", ""]
        assert table_rows(app)[0] == REFUSED_FIXED.rstrip().split(",")[:-2]
        assert mark_counts(app) == ["1 record refused, marked !"]
        assert not app._notifications
    assert path.read_text() == LOG_HEADER + REFUSED_FIXED


async def test_refused_rows_stay_under_session_entries(app, settings_path):
    write_refused(settings_path)
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        await pilot.press("enter")
        assert table_calls(app) == ["W1ABC", "K1BBB", "K1AAA"]
        assert table_markers(app) == ["•", "!", ""]
        assert divider_rows(app) == [1]


async def test_selected_refused_row_shows_what_reads_as_typed(app, settings_path):
    write_refused(settings_path)
    async with app.run_test() as pilot:
        await select_row(app, pilot, 0)
        assert field_values(app) == K1BBB_VALUES | {"PARK": "1234", "TIME": "53"}
        # Esc out of editing shows it the same way.
        await pilot.press("f3", "escape")
        assert field_values(app)["TIME"] == "53"


def problem_lines(app) -> list[str]:
    """What's listed below COMMENT (a refused row's problems, or other
    copies of a record); [] while hidden.
    """
    listed = app.query_one("#entry-problems")
    return str(listed.render()).splitlines() if listed.display else []


def invalid_fields(app) -> list[str]:
    return [
        name
        for name, _, _ in FIELDS
        if app.query_one(f"#field-{name.lower()}").has_class("-invalid")
    ]


def test_mark_counts_one_line_per_mark_in_order_long_when_all_fit():
    counts = Counter({"=": 3, "!": 1, "✎": 2})
    long = ["1 record refused, marked !", "3 records are dupes, marked ="]
    assert mark_count_lines(counts, len(long[1])) == long
    assert mark_count_lines(counts, len(long[1]) - 1) == ["! 1 refused", "= 3 dupes"]
    assert mark_count_lines(Counter(), 100) == []


def test_mark_counts_say_one_for_a_lone_mark():
    # A lone U (its copy refused) or = (its copy marked U).
    counts = Counter({"U": 1, "=": 1})
    assert mark_count_lines(counts, 0) == ["U 1 shares an ID", "= 1 dupe"]
    assert mark_count_lines(counts, 100) == [
        "1 record shares a record ID, marked U",
        "1 record is a dupe, marked =",
    ]


async def test_no_mark_counts_without_marked_rows(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test():
        assert mark_counts(app) == []


async def test_mark_counts_follow_the_log_until_none_are_left(app, settings_path):
    path = write_two_saved(settings_path)
    path.write_text(LOG_HEADER + K1AAA_ROW + K1BBB_ROW + K1AAA_ROW.replace(K1AAA_ID, new_id()))
    async with app.run_test() as pilot:
        assert mark_counts(app) == ["2 records are dupes, marked ="]
        await select_row(app, pilot, 0)
        await pilot.press("f4", "enter", "enter")
        assert table_markers(app) == ["", ""]
        assert mark_counts(app) == []


async def test_refused_rows_are_counted_beside_the_buttons(app, settings_path):
    write_refused(settings_path, REFUSED_ROW + REFUSED_ROW.replace("K1BBB", "K2CCC"))
    async with app.run_test(size=(36, 24)) as pilot:
        assert mark_counts(app) == ["! 2 refused"]
        # The long form once it fits.
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert mark_counts(app) == ["2 records refused, marked !"]


async def test_selected_refused_row_lists_its_problems(app, settings_path):
    write_refused(settings_path)
    async with app.run_test() as pilot:
        assert problem_lines(app) == []
        await select_row(app, pilot, 0)
        assert problem_lines(app) == [
            "Refused from 20260925.csv row 2:",
            "- TIME '53' should be HHMM, like 2123.",
            "- PARK '1234' should be 'US-1234' in a log file. Saving makes it US-1234.",
        ]
        assert invalid_fields(app) == ["PARK", "TIME"]
        # The list stays while editing, as found in the file; a field's red
        # border goes once it's changed (stock Input behavior).
        await pilot.press("f3")
        fill(app, {"TIME": "0053"})
        assert len(problem_lines(app)) == 3
        assert invalid_fields(app) == ["PARK"]
        # Gone with another row selected, or none.
        await pilot.press("escape", "down")
        assert problem_lines(app) == []
        assert invalid_fields(app) == []
        await pilot.press("up", "escape")
        assert problem_lines(app) == []


async def test_problem_list_goes_once_the_row_is_fixed(app, settings_path):
    write_refused(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 0)
        fill(app, {"TIME": "0053"})
        await pilot.press("enter")
        assert table_markers(app)[0] == "✎"
        assert problem_lines(app) == []
        assert invalid_fields(app) == []


async def test_fixed_refused_row_is_saved_in_place_and_marked_edited(app, settings_path):
    path = write_refused(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 0)
        fill(app, {"TIME": "0053"})
        await pilot.press("enter")
        assert table_calls(app) == ["K1BBB", "K1AAA"]
        assert table_markers(app) == ["✎", ""]
        assert table_rows(app)[0][1] == "CW"
        # Now among the entries checked for dupes.
        assert any(entry["CALL"] == "K1BBB" for entry in app.query_one(EntryForm).logged)
    assert path.read_text() == LOG_HEADER + K1BBB_ROW.replace("1900", "0053").replace(
        "US-5678", "US-1234"
    )


async def test_refused_row_can_be_deleted(app, settings_path):
    path = write_refused(settings_path)
    async with app.run_test() as pilot:
        await select_row(app, pilot, 0)
        await pilot.press("f4", "enter", "enter")
        assert table_calls(app) == ["K1AAA"]
    assert path.read_text() == LOG_HEADER


async def test_refused_rows_station_callsign_is_stored_as_read(app, settings_path):
    path = write_refused(settings_path, K1BBB_ROW.replace("W1TST", "w1tst"))
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 0)
        await pilot.press("enter")
    assert path.read_text() == LOG_HEADER + K1BBB_ROW


async def test_refused_rows_other_station_callsign_cant_be_fixed_in_app(app, settings_path):
    write_refused(settings_path, K1BBB_ROW.replace("W1TST", "W1XYZ"))
    async with app.run_test() as pilot:
        await select_row(app, pilot, 0)
        assert problem_lines(app) == [
            "Refused from 20260925.csv row 2:",
            "- STATION_CALLSIGN 'W1XYZ' doesn't match the station callsign, W1TST. "
            "Manually correct CSV log file.",
        ]
        await pilot.press("f3")
        assert app.query_one(EntryForm).editing is None
        assert list(app._notifications)[-1].message == (
            "STATION_CALLSIGN 'W1XYZ' doesn't match the station callsign, W1TST. "
            "Manually correct CSV log file."
        )


async def test_log_loads_once_a_station_callsign_is_set(settings_path):
    write_refused(settings_path, K1BBB_ROW.replace("W1TST", "W1XYZ"))
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        assert app.screen.id == "station-callsign-required"
        assert table_calls(app) == []
        await pilot.press("enter")
        app.screen.query_one("#station-callsign-input", Input).value = "W1TST"
        await pilot.press("enter")
        # Then the parks list is offered (skipped here).
        assert isinstance(app.screen, ParksOfferScreen)
        await pilot.press("escape")
        assert len(app.screen_stack) == 1
        # Checked against the call just set.
        assert table_calls(app) == ["K1BBB", "K1AAA"]
        assert table_markers(app) == ["!", ""]


async def test_refused_rows_unreadable_station_callsign_cant_be_fixed_in_app(
    app, settings_path
):
    write_refused(settings_path, K1BBB_ROW.replace("W1TST", "123"))
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 0)
        assert app.query_one(EntryForm).editing is None
        assert list(app._notifications)[-1].message == (
            "STATION_CALLSIGN '123' doesn't look like a callsign, like W1ABC. "
            "Manually correct CSV log file."
        )


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


# Record IDs


async def test_records_sharing_an_id_are_marked_and_explained(app, settings_path):
    # K1AAA saved twice, and K1BBB with a version in the next day's file,
    # as an unfinished DATE move would leave.
    path = write_two_saved(settings_path)
    path.write_text(LOG_HEADER + K1AAA_ROW + K1BBB_ROW + K1AAA_ROW)
    (settings_path.parent / "20260926.csv").write_text(
        LOG_HEADER + K1BBB_ROW.replace("20260925", "20260926").replace("1900", "1905")
    )
    async with app.run_test() as pilot:
        assert table_calls(app) == ["K1BBB", "K1AAA", "K1AAA", "K1BBB"]
        assert table_markers(app) == ["U", "U", "U", "U"]
        assert mark_counts(app) == ["4 records share a record ID, marked U"]
        await select_row(app, pilot, 0)
        assert problem_lines(app) == [
            "Excluding COMMENT, duplicate record(s) exist:",
            "- Same UUIDv4 in 20260925.csv, with a different DATE and TIME.",
            "Edit field values (f3) or delete (f4) as makes sense.",
        ]
        # Either copy may be the right one.
        assert invalid_fields(app) == []
        await pilot.press("down")
        assert problem_lines(app)[1:] == [
            "- Same UUIDv4 in 20260925.csv, also same in every column.",
            "Edit field values (f3) or delete (f4) as makes sense.",
        ]
        # One copy deleted, the other's mark goes.
        await pilot.press("f4", "enter", "enter")
        assert table_calls(app) == ["K1BBB", "K1AAA", "K1BBB"]
        assert table_markers(app) == ["U", "", "U"]
        await select_row(app, pilot, 1)
        assert problem_lines(app) == []
    assert path.read_text() == LOG_HEADER + K1BBB_ROW + K1AAA_ROW


async def test_edit_keeps_the_record_id(app, settings_path):
    path = write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 0)
        fill(app, {"DATE": "260926"})
        await pilot.press("enter")
    assert path.read_text() == LOG_HEADER + K1BBB_ROW
    assert (settings_path.parent / "20260926.csv").read_text() == (
        LOG_HEADER + K1AAA_ROW.replace("20260925", "20260926")
    )


async def test_refused_rows_bad_id_is_replaced_when_fixed(app, settings_path):
    path = write_refused(settings_path, K1BBB_ROW.replace(K1BBB_ID, "not an id"))
    async with app.run_test() as pilot:
        await select_row(app, pilot, 0)
        assert problem_lines(app)[1] == (
            "- UUIDv4 'not an id' should be a UUID as the app writes it, like "
            "1b4e28ba-2fa1-4d2b-883f-0016d3cca427. Saving gives it a new one."
        )
        await pilot.press("f3", "enter")
        assert table_markers(app) == ["✎", ""]
    saved, record_id = path.read_text().removeprefix(LOG_HEADER).rstrip().rsplit(",", 1)
    assert saved + ",\n" == K1BBB_ROW.replace(K1BBB_ID, "")
    assert parse_id(record_id) == record_id


async def test_uppercase_id_is_fixed_on_load_and_matches_its_copy(app, settings_path):
    # Its ID in uppercase, refused for TIME, with a copy in the next day's
    # file.
    path = write_refused(
        settings_path, K1BBB_ROW.replace(K1BBB_ID, K1BBB_ID.upper()).replace(",1900,", ",19,")
    )
    moved = K1BBB_ROW.replace("20260925", "20260926")
    (settings_path.parent / "20260926.csv").write_text(
        LOG_HEADER + K1AAA_ROW.replace("20260925", "20260926") + moved
    )
    async with app.run_test() as pilot:
        assert table_calls(app) == ["K1BBB", "K1AAA", "K1BBB"]
        assert table_markers(app) == ["!", "", "U"]
        await select_row(app, pilot, 0)
        assert problem_lines(app) == [
            "Refused from 20260925.csv row 2:",
            "- TIME '19' should be HHMM, like 2123.",
            "Excluding COMMENT, duplicate record(s) exist:",
            "- Same UUIDv4 in 20260926.csv, with a different DATE and TIME.",
            "Edit field values (f3) or delete (f4) as makes sense.",
        ]
        await pilot.press("f3")
        fill(app, {"TIME": "1900"})
        await pilot.press("enter")
        assert table_markers(app) == ["U", "", "U"]
    assert path.read_text() == LOG_HEADER + K1BBB_ROW


async def test_filled_ids_that_cant_be_written_block_until_fixed(app, settings_path, monkeypatch):
    path = write_two_saved(settings_path)
    path.write_text(LOG_HEADER + K1AAA_ROW.replace(K1AAA_ID, "") + K1BBB_ROW)
    fail_to_write(monkeypatch)
    async with app.run_test():
        assert table_calls(app) == ["K1AAA", "K1BBB"]
        assert not app._notifications
        assert app.screen.message == (
            "Couldn't write to file or directory.\n"
            "Check permissions.\n"
            f"See {settings_path.parent / 'file_errors.txt'}\n"
            "\n"
            "Fix the files, then start the app again."
        )
    assert file_errors_text(settings_path) == [
        f"{path}: couldn't save changes made on load: Permission denied. Check permissions."
    ]
    assert path.read_text() == LOG_HEADER + K1AAA_ROW.replace(K1AAA_ID, "") + K1BBB_ROW


async def test_rows_to_fix_and_ids_unwritten_block_together(app, settings_path, monkeypatch):
    path = write_two_saved(settings_path)
    path.write_text(LOG_HEADER + K1AAA_ROW.replace(K1AAA_ID, "") + BROKEN_ROW)
    fail_to_write(monkeypatch)
    async with app.run_test():
        assert app.screen.message == (
            "Manual data correction required.\n"
            "Couldn't write to file or directory.\n"
            "Check permissions.\n"
            f"See {settings_path.parent / 'file_errors.txt'}\n"
            "\n"
            "Fix the files, then start the app again."
        )
    assert file_errors_text(settings_path) == [
        f"{path} row 3: has 11 values, should have 13",
        f"{path}: couldn't save changes made on load: Permission denied. Check permissions.",
    ]


# Dupes

K1AAA_VALUES = {
    "FREQ": "14.285.500",
    "MODE": "USB",
    "CALL": "K1AAA",
    "PARK": "US-1234",
    "ST": "NJ",
    "SNT": "59",
    "RCD": "57",
    "PWR": "60",
    "DATE": "260925",
    "TIME": "2100",
    "COMMENT": "",
}

NEW_DUPE_MESSAGE = (
    "Excluding COMMENT, attempted save\n"
    "will result in a duplicate record.\n"
    "See DATE & TIME to locate other record."
)
EDIT_DUPE_MESSAGE = NEW_DUPE_MESSAGE + (
    "\n"
    "Change field value(s), or Esc out to\n"
    "cancel.\n"
    "\n"
    "WARNING:\n"
    "Updated COMMENT will be lost after\n"
    "escaping out."
)


def modal_message(app) -> str:
    return str(app.screen.query_one("#warning-message", Static).render())


def modal_buttons(app) -> list[str]:
    return [str(button.label) for button in app.screen.query(Button)]


@pytest.mark.parametrize("key", ["enter", "escape"])
async def test_dupe_is_blocked_back_to_the_form(app, settings_path, key):
    path = write_two_saved(settings_path)
    async with app.run_test() as pilot:
        fill(app, K1AAA_VALUES | {"COMMENT": "Big signal"})
        await pilot.press("enter")
        assert isinstance(app.screen, WarningScreen)
        assert modal_message(app) == NEW_DUPE_MESSAGE
        assert modal_buttons(app) == ["Roger Roger"]
        await pilot.press(key)
        assert len(app.screen_stack) == 1
        assert app.selected is None
        assert app.focused.id == "field-freq"
        assert field_values(app) == K1AAA_VALUES | {"COMMENT": "Big signal"}
        assert table_calls(app) == ["K1AAA", "K1BBB"]
    assert path.read_text() == LOG_HEADER + K1AAA_ROW + K1BBB_ROW


async def test_entry_differing_only_in_time_is_saved(app):
    # Today's possible dupe: same call, park, day, band, and mode.
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        await pilot.press("enter")
        fill(app, ENTRY | {"TIME": "2005"})
        await pilot.press("enter")
        assert len(app.screen_stack) == 1
        assert len(table_rows(app)) == 2


async def test_unusual_call_changed_into_a_dupe_is_blocked(app, settings_path):
    write_two_saved(settings_path)
    async with app.run_test() as pilot:
        fill(app, K1AAA_VALUES | {"CALL": "K11AAA"})
        await pilot.press("enter")
        assert isinstance(app.screen, CallsignWarningScreen)
        app.screen.query_one(Input).value = "K1AAA"
        await pilot.press("enter")
        assert modal_message(app) == NEW_DUPE_MESSAGE


@pytest.mark.parametrize("key", ["enter", "escape"])
async def test_edit_into_a_dupe_is_blocked_and_stays_open(app, settings_path, key):
    path = write_two_saved(settings_path)
    async with app.run_test() as pilot:
        await edit_row(app, pilot, 1)
        fill(app, K1AAA_VALUES | {"COMMENT": "Loud"})
        await pilot.press("enter")
        assert modal_message(app) == EDIT_DUPE_MESSAGE
        await pilot.press(key)
        assert len(app.screen_stack) == 1
        form = app.query_one(EntryForm)
        assert form.editing["CALL"] == "K1BBB"
        assert field_values(app) == K1AAA_VALUES | {"COMMENT": "Loud"}
        assert not form_disabled(app)
    assert path.read_text() == LOG_HEADER + K1AAA_ROW + K1BBB_ROW


async def test_shared_id_is_listed_first_then_dupes(app, settings_path):
    # K1AAA saved twice with one ID, and once more with its own.
    path = write_two_saved(settings_path)
    path.write_text(LOG_HEADER + K1AAA_ROW + K1AAA_ROW + K1AAA_ROW.replace(K1AAA_ID, new_id()))
    async with app.run_test() as pilot:
        assert table_markers(app) == ["U", "U", "="]
        await select_row(app, pilot, 0)
        assert problem_lines(app) == [
            "Excluding COMMENT, duplicate record(s) exist:",
            "- Same UUIDv4 in 20260925.csv, also same in every column.",
            "- Another record has same COMMENT.",
            "Edit field values (f3) or delete (f4) as makes sense.",
        ]
        await pilot.press("down", "down")
        assert problem_lines(app)[1:] == [
            "- 2 other records have same COMMENT.",
            "Edit field values (f3) or delete (f4) as makes sense.",
        ]


async def test_saved_dupes_are_marked_and_explained(app, settings_path):
    # K1AAA logged three times: twice with no COMMENT, once with one.
    path = write_two_saved(settings_path)
    path.write_text(
        LOG_HEADER
        + K1AAA_ROW
        + K1BBB_ROW
        + K1AAA_ROW.replace(K1AAA_ID, new_id())
        + K1AAA_ROW.replace(K1AAA_ID, new_id()).replace(",,", ",Loud,")
    )
    async with app.run_test() as pilot:
        assert table_markers(app) == ["=", "=", "=", ""]
        assert mark_counts(app) == ["3 records are dupes, marked ="]
        await select_row(app, pilot, 0)
        assert problem_lines(app) == [
            "Excluding COMMENT, duplicate record(s) exist:",
            "- Another record has same COMMENT.",
            "- Another record has COMMENT 'Loud'.",
            "Edit field values (f3) or delete (f4) as makes sense.",
        ]
        assert invalid_fields(app) == []
        await pilot.press("down", "down")
        assert problem_lines(app)[1] == "- 2 other records without a COMMENT."
        # Deleted down to one, the mark goes.
        await pilot.press("f4", "enter", "enter")
        await select_row(app, pilot, 0)
        await pilot.press("f4", "enter", "enter")
        assert table_markers(app) == ["", ""]


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
        assert not app.query_one("#adif").can_focus


# Settings


@pytest.fixture
def no_call_app(settings_path):
    """The app at first start, with no station callsign: Settings, with
    the call to set, opens with Enter from the block.
    """
    return PotaLoggerApp(settings_path=settings_path)


def required_message(app) -> str:
    return str(app.screen.query_one("#warning-message", Static).render())


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


def setting_labels(app) -> list[str]:
    return [str(box.label) for box in app.screen.query(Checkbox)]


SETTING_LABELS = [
    "New: Pre-populate COMMENT with POTA info.",
    "Edit: Update COMMENT with POTA info.",
]


async def test_settings_after_setup_hide_the_call(app):
    # A log holds one call, so it isn't changed in Settings.
    async with app.run_test() as pilot:
        await pilot.press("f2")
        assert not app.screen.query("#station-callsign-input")
        assert setting_labels(app) == SETTING_LABELS
        assert [box.value for box in app.screen.query(Checkbox)] == [False, False]


def checkbox_marks(app) -> list[str]:
    """The character inside each checkbox, as drawn."""
    return [box.render().plain[1] for box in app.screen.query(Checkbox)]


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
        expected = Settings("W1TST", new_comment_pota_info=True, edit_comment_pota_info=True)
        assert app.settings == expected
        assert load_settings(settings_path) == expected


async def test_settings_saved_at_first_start_with_the_call(no_call_app, settings_path):
    app = no_call_app
    async with app.run_test() as pilot:
        await pilot.press("enter", *"w1tst", "tab", "space")
        await pilot.click("#save")
        assert load_settings(settings_path) == Settings("W1TST", new_comment_pota_info=True)


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A home folder in the temp dir, with ~/adif in it, for folders typed
    with ~ (which Settings saves only if they exist).
    """
    home = tmp_path / "home"
    (home / "adif").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return home


def folder_problem(app) -> str:
    shown = app.screen.query_one("#folder-problem", Static)
    return str(shown.render()) if shown.has_class("-shown") else ""


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
        assert load_settings(settings_path).adif_export_folder == ""
    assert not (home / "deve").exists()


async def test_blank_export_folder_saves_as_none_set(settings_path):
    save_settings(Settings("W1TST", adif_export_folder="~/gone"), settings_path)
    app = PotaLoggerApp(settings_path=settings_path)
    async with app.run_test() as pilot:
        await pilot.press("f2")
        app.screen.query_one("#folder-input", Input).value = ""
        await pilot.click("#save")
        assert not isinstance(app.screen, SettingsScreen)
    assert load_settings(settings_path).adif_export_folder == ""


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
        assert load_settings(settings_path).adif_export_folder == ""
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
        assert load_settings(settings_path) == Settings(station_callsign="W1ABC")


async def test_save_button_saves(no_call_app, settings_path):
    app = no_call_app
    async with app.run_test() as pilot:
        await pilot.press("enter")
        app.screen.query_one("#station-callsign-input", Input).value = "W1ABC"
        await pilot.click("#save")
        assert load_settings(settings_path) == Settings(station_callsign="W1ABC")


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


def settings_problem(app) -> str | None:
    """What's shown below the station callsign in Settings, if anything."""
    shown = app.screen.query_one("#settings-problem", Static)
    return str(shown.render()) if shown.has_class("-shown") else None


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
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


async def test_blank_station_callsign_saves_and_asks_for_one(no_call_app, settings_path):
    app = no_call_app
    async with app.run_test() as pilot:
        await pilot.press("enter")
        app.screen.query_one("#station-callsign-input", Input).value = "  "
        await pilot.press("enter")
        assert app.screen.id == "station-callsign-required"
        assert station_callsign(app) == "NOCALL"
        assert load_settings(settings_path) == Settings(station_callsign="")
        await pilot.press("enter")
        assert isinstance(app.screen, SettingsScreen)


async def open_settings_with(app, pilot, call: str) -> None:
    """From the station-callsign block, Settings with `call` saved."""
    await pilot.press("enter")
    app.screen.query_one("#station-callsign-input", Input).value = call
    await pilot.press("enter")


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
        assert load_settings(settings_path) == Settings(station_callsign="W111111AB")


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
        assert load_settings(settings_path) == Settings(station_callsign="W1ABC")


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
        assert app.settings == Settings(station_callsign="W1TST")
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


async def test_cancel_button_cancels(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2", "space")
        await pilot.click("#cancel")
        assert app.settings == Settings(station_callsign="W1TST")
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


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
        assert load_settings(settings_path) == Settings(station_callsign="W1TST")


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
        'adif_export_folder = ""\n'
    )


# Export


@pytest.fixture
def export_folder(settings_path):
    """An existing folder for exports, beside data/ in the temp dir."""
    folder = settings_path.parent.parent / "adif"
    folder.mkdir(parents=True)
    return folder


@pytest.fixture
def export_app(settings_path, export_folder):
    """The app with W1TST and an ADIF export folder set."""
    save_settings(Settings("W1TST", adif_export_folder=str(export_folder)), settings_path)
    return PotaLoggerApp(settings_path=settings_path)


def export_range(app) -> tuple[str, str]:
    return (
        app.screen.query_one("#export-from", Input).value,
        app.screen.query_one("#export-to", Input).value,
    )


def export_problem(app) -> str:
    shown = app.screen.query_one("#export-problem", Static)
    return str(shown.render()) if shown.has_class("-shown") else ""


def exported_files(folder) -> list:
    return sorted(folder.glob("*.adi")) if folder.exists() else []


THREE_DAYS = {
    "20260924": [("K1AAA", "20260924", "2300")],
    "20260925": [("W1CCC", "20260925", "1900"), ("K1BBB", "20260925", "0100")],
    "20260926": [("N1DDD", "20260926", "0005")],
}


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


async def test_export_without_a_folder_says_to_set_one(app, settings_path):
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


# POTA's parks list: offered at first start, and checked from Settings.


async def first_start(app, pilot) -> None:
    """Set the station callsign at first start."""
    await pilot.press("enter")
    app.screen.query_one("#station-callsign-input", Input).value = "W1TST"
    await pilot.press("enter")


async def parks_list_done(app, pilot) -> None:
    """Wait for the parks list's download thread and what follows it."""
    await app.workers.wait_for_complete()
    await pilot.pause()


def parks_list_row(app) -> str:
    return str(app.screen.query_one("#parks-list", Label).render())


def last_notification(app) -> str:
    return list(app._notifications)[-1].message


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


# POTA's parks list as the parks tests' app has it: a park in one state
# each (Maine, Alaska), one in two, and an inactive one.
APP_LIST = NEWER_LIST + (
    b'"US-0003","Two State Trail","1","291","US-DC,US-MD","38.9","-77.0","FM18lv"\n'
    b'"US-0004","Old Park","0","291","US-ME","44.3","-68.2","FN54vh"\n'
)


def save_parks_list(settings_path, pota) -> None:
    pota.content, pota.etag = APP_LIST, md5_etag(APP_LIST)
    download_parks(parks_folder(settings_path.parent), pota.url)


@pytest.fixture
def parks_app(app, settings_path, pota):
    """The app with POTA's parks list saved (APP_LIST)."""
    save_parks_list(settings_path, pota)
    app.parks_url = pota.url
    return app


def park_name(app) -> str:
    return str(app.query_one("#park-name", Label).render())


async def leave_park(app, pilot, text: str) -> None:
    """Type PARK as `text`, then Tab out of it."""
    app.query_one("#field-park", Input).value = text
    app.query_one("#field-park", Input).focus()
    await pilot.press("tab")


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


def st_value(app) -> str:
    return app.query_one("#field-st", Input).value


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
