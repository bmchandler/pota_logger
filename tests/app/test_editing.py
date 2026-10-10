"""Selecting a log row and editing its entry."""

from textual.widgets import DataTable, Input

from pota_logger.entry_form import COMMENT_LENGTH, EntryForm
from pota_logger.record_ids import new_id
from pota_logger.screens.warning_screen import WarningScreen

from tests.app.helpers import (
    ENTRY,
    ENTRY_ROW,
    FUTURE,
    K1AAA_ID,
    K1AAA_ROW,
    K1BBB_ROW,
    K1BBB_VALUES,
    LOG_HEADER,
    WRITE_FAILED_MESSAGE,
    comment,
    comment_column_width,
    divider_rows,
    edit_row,
    field_values,
    fill,
    form_disabled,
    log_fills_its_width,
    report_placeholders,
    select_row,
    table_calls,
    table_markers,
    table_rows,
    write_two_saved,
)
from tests.helpers import fail_to_write


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


async def test_write_failed_for_another_reason_says_to_close_other_programs(
    app, monkeypatch
):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        fail_to_write(monkeypatch, error=OSError(16, "Device or resource busy"))
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
