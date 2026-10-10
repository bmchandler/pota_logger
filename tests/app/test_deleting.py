"""Deleting an entry."""

from textual.widgets import DataTable

from pota_logger.entry_form import EntryForm
from pota_logger.screens.delete_screen import DeleteScreen

from tests.app.helpers import (
    ENTRY,
    K1AAA_ROW,
    K1BBB_DELETE_MESSAGE,
    K1BBB_ROW,
    LOG_HEADER,
    WRITE_FAILED_MESSAGE,
    divider_rows,
    edit_row,
    field_values,
    fill,
    form_disabled,
    select_row,
    table_calls,
    table_markers,
    write_two_saved,
)
from tests.helpers import fail_to_write


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
