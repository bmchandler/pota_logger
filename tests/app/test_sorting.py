"""Sorting the log."""

from datetime import date, time

from textual.widgets import DataTable

from pota_logger.app import PotaLoggerApp, header_cell, sort_key
from pota_logger.screens.delete_screen import DeleteScreen

from tests.app.helpers import (
    BROKEN_ROW,
    ENTRY,
    LOG_COLUMN,
    LOG_HEADER,
    THREE_SAVED,
    click_header,
    comment,
    divider_rows,
    file_errors_text,
    fill,
    headers,
    press_sort,
    select_row,
    table_calls,
    table_markers,
    table_rows,
    write_refused,
    write_saved_log,
    write_two_saved,
)


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
