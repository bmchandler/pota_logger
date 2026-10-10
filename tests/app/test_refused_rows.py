"""Rows refused on load, shown marked `!` and fixed in the app."""

from collections import Counter

from textual.widgets import DataTable, Input

from pota_logger.app import PotaLoggerApp, mark_count_lines
from pota_logger.entry_form import EntryForm
from pota_logger.record_ids import new_id
from pota_logger.screens.parks_offer_screen import ParksOfferScreen

from tests.app.helpers import (
    ENTRY,
    K1AAA_ID,
    K1AAA_ROW,
    K1BBB_ROW,
    K1BBB_VALUES,
    LOG_HEADER,
    REFUSED_FIXED,
    REFUSED_ROW,
    divider_rows,
    edit_row,
    field_values,
    fill,
    invalid_fields,
    mark_counts,
    problem_lines,
    select_row,
    table_calls,
    table_markers,
    table_rows,
    write_refused,
    write_two_saved,
)


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
