"""The app's layout, focus, keys, and quitting."""

from datetime import date

from textual.command import CommandPalette
from textual.widgets import Button, DataTable, Input, Static

from pota_logger.entry_form import COMMENT_LENGTH, ROW_FIELDS, EntryForm
from pota_logger.fields import dates

from tests.app.helpers import comment, footer_keys


async def test_focus_starts_on_freq(app):
    async with app.run_test():
        assert app.focused.id == "field-freq"


async def test_uses_pota_theme(app):
    async with app.run_test():
        assert app.theme == "pota"


async def test_footer_shows_quit_info_settings_edit_delete_sort_export_and_screenshot(app):
    async with app.run_test():
        assert footer_keys(app) == ["ctrl+q", "f1", "f2", "f3", "f4", "f5", "f6", "ctrl+s"]


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
