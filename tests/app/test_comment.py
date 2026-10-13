"""COMMENT, and the POTA info Settings can put in it."""

import pytest
from textual.widgets import DataTable, Input

from pota_logger.app import PotaLoggerApp
from pota_logger.entry_form import COMMENT_LENGTH, ROW_FIELDS, pota_info
from pota_logger.settings import Settings, save_settings

from tests.app.helpers import (
    ENTRY,
    comment,
    comment_column_width,
    edit_row,
    field_values,
    fill,
    log_fills_its_width,
    select_row,
    table_rows,
    type_and_leave,
)


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
        await pilot.press("f2", "tab", "space")
        await pilot.click("#save")
        assert comment(app) == "POTA US-1234"
        await pilot.press("f2", "tab", "space")
        await pilot.click("#save")
        assert comment(app) == ""


async def test_setting_turned_off_keeps_a_comment_typed_on(pota_app):
    app = pota_app
    async with app.run_test() as pilot:
        await type_and_leave(app, pilot, "PARK", "1234")
        app.query_one("#field-comment", Input).value += " Great signal"
        await pilot.press("f2", "tab", "space")
        await pilot.click("#save")
        assert comment(app) == "POTA US-1234 Great signal"
        await type_and_leave(app, pilot, "PARK", "5678")
        assert comment(app) == "POTA US-1234 Great signal"
