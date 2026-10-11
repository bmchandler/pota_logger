"""What the app tests share: entries, log rows, and ways to read and drive the app."""

from datetime import date, time

from textual.widgets import Button, Checkbox, DataTable, Input, Label, Static

from pota_logger.entry_form import FIELDS, LOG_FIELDS, EntryForm
from pota_logger.parks_list import download_parks, md5_etag, parks_folder
from pota_logger.record_ids import new_id
from pota_logger.settings import default_export_folder

from tests.conftest import NEWER_LIST


def station_callsign(app) -> str:
    return str(app.query_one("#station-callsign", Static).render())


def footer_keys(app) -> list[str]:
    return [key for key, active in app.screen.active_bindings.items() if active.binding.show]


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


FUTURE = {"DATE": "991231"}


def report_placeholders(app) -> list[str]:
    return [app.query_one(f"#field-{name}", Input).placeholder for name in ("snt", "rcd")]


def drawn_table_row(app, row_index: int) -> str:
    """Text the log table actually draws for a data row (line 0 is the header)."""
    return app.query_one("#log-table", DataTable).render_line(row_index + 1).text


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


def comment(app) -> str:
    return app.query_one("#field-comment", Input).value


async def type_and_leave(app, pilot, name: str, value: str) -> None:
    """Set a field's value from inside it, then Tab out."""
    field = app.query_one(f"#field-{name.lower()}", Input)
    field.focus()
    field.value = value
    await pilot.press("tab")


LOG_HEADER = "FREQ,MODE,CALL,PARK,ST,SNT,RCD,PWR,DATE,TIME,COMMENT,STATION_CALLSIGN,UUIDv4\n"


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


BROKEN_ROW = "14285500,USB,W1ABC,US-1234,NJ,59,57,60,20260925,1953,W1TST\n"


def file_errors_text(settings_path) -> list[str]:
    """file_errors.txt's lines below its header (written time, what to do,
    a blank line).
    """
    return (settings_path.parent / "file_errors.txt").read_text().splitlines()[3:]


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



WRITE_FAILED_MESSAGE = (
    "Couldn't save to 20260925.csv:\n"
    "Permission Denied - Check file system\n"
    "permissions on file.\n"
    "Enter to try again, or Esc to go back."
)


K1BBB_DELETE_MESSAGE = (
    "Delete this record?\n"
    "K1BBB on 7.030.000 CW\n"
    "2026.09.25 19:00 UTC\n"
    "Gone is gone: there's no undo.\n"
)


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


def required_message(app) -> str:
    return str(app.screen.query_one("#warning-message", Static).render())


def setting_labels(app) -> list[str]:
    return [str(box.label) for box in app.screen.query(Checkbox)]


SETTING_LABELS = [
    "New: Pre-populate COMMENT with POTA info.",
    "Edit: Update COMMENT with POTA info.",
]


def checkbox_marks(app) -> list[str]:
    """The character inside each checkbox, as drawn."""
    return [box.render().plain[1] for box in app.screen.query(Checkbox)]


def folder_problem(app) -> str:
    shown = app.screen.query_one("#folder-problem", Static)
    return str(shown.render()) if shown.has_class("-shown") else ""


def settings_problem(app) -> str | None:
    """What's shown below the station callsign in Settings, if anything."""
    shown = app.screen.query_one("#settings-problem", Static)
    return str(shown.render()) if shown.has_class("-shown") else None


async def open_settings_with(app, pilot, call: str) -> None:
    """From the station-callsign block, Settings with `call` saved."""
    await pilot.press("enter")
    app.screen.query_one("#station-callsign-input", Input).value = call
    await pilot.press("enter")


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


# POTA's parks list as the parks tests' app has it: a park in one state
# each (Maine, Alaska), one in two, and an inactive one.
APP_LIST = NEWER_LIST + (
    b'"US-0003","Two State Trail","1","291","US-DC,US-MD","38.9","-77.0","FM18lv"\n'
    b'"US-0004","Old Park","0","291","US-ME","44.3","-68.2","FN54vh"\n'
)


def save_parks_list(settings_path, pota) -> None:
    pota.content, pota.etag = APP_LIST, md5_etag(APP_LIST)
    download_parks(parks_folder(settings_path.parent), pota.url)


def park_name(app) -> str:
    return str(app.query_one("#park-name", Label).render())


async def leave_park(app, pilot, text: str) -> None:
    """Type PARK as `text`, then Tab out of it."""
    app.query_one("#field-park", Input).value = text
    app.query_one("#field-park", Input).focus()
    await pilot.press("tab")


def st_value(app) -> str:
    return app.query_one("#field-st", Input).value


def exports(settings_path) -> str:
    """The default ADIF export folder, which the app sets when none is."""
    return default_export_folder(settings_path.parent)
