"""Definite dupes: blocked on Enter, and marked `=` when saved."""

import pytest
from textual.widgets import Input

from pota_logger.entry_form import EntryForm
from pota_logger.record_ids import new_id
from pota_logger.screens.callsign_warning_screen import CallsignWarningScreen
from pota_logger.screens.warning_screen import WarningScreen

from tests.app.helpers import (
    EDIT_DUPE_MESSAGE,
    ENTRY,
    K1AAA_ID,
    K1AAA_ROW,
    K1AAA_VALUES,
    K1BBB_ROW,
    LOG_HEADER,
    NEW_DUPE_MESSAGE,
    edit_row,
    field_values,
    fill,
    form_disabled,
    invalid_fields,
    mark_counts,
    modal_buttons,
    modal_message,
    problem_lines,
    select_row,
    table_calls,
    table_markers,
    table_rows,
    write_two_saved,
)


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
