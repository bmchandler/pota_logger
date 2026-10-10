"""Saving to and loading from the log files, and record IDs."""

from datetime import time

from textual.widgets import DataTable

from pota_logger.app import PotaLoggerApp
from pota_logger.record_ids import parse_id

from tests.app.helpers import (
    BROKEN_ROW,
    ENTRY,
    ENTRY_ROW,
    K1AAA_ID,
    K1AAA_ROW,
    K1BBB_ID,
    K1BBB_ROW,
    LOG_HEADER,
    divider_rows,
    drawn_table_row,
    edit_row,
    file_errors_text,
    fill,
    invalid_fields,
    mark_counts,
    problem_lines,
    select_row,
    table_calls,
    table_markers,
    table_rows,
    write_refused,
    write_saved_log,
    write_two_saved,
)
from tests.helpers import fail_to_write


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
