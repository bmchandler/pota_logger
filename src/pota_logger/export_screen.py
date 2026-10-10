from datetime import UTC, date, datetime

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from pota_logger.adif import adif_file, export_file_name
from pota_logger.ascii_text import check_ascii
from pota_logger.dates import parse_date
from pota_logger.settings import folder_path

# The modal's wording, as dictated (2026-10-09).
DATES_LINE = "ADIF file, UTC dates (YYMMDD)"
NO_FOLDER = "Export error: No ADIF export folder set.\nSet one in Settings (F2)."
NOT_CLEAN = "Export error: Rows are marked !, U, or =.\nResolve and try again."
NOTHING_IN_RANGE = "Export error: No logs in date range."
WRITE_FAILED = "Export error: Couldn't write the file."
EXPORTED = "ADIF export complete."


def entries_in_range(entries: list[dict], start: date, end: date) -> list[dict]:
    """The entries dated from `start` to `end` (UTC dates, both included),
    in time order.
    """
    found = [entry for entry in entries if start <= entry["DATE"] <= end]
    return sorted(found, key=lambda entry: (entry["DATE"], entry["TIME"]))


class ExportScreen(ModalScreen[None]):
    """Export a UTC date range of the log as an ADIF file, into the folder
    set in Settings (not shown here: it's set and seen in Settings, and
    read on Export, so a folder set from here with F2 counts). Refused, with why below in the error color, while no
    folder is set, the log isn't clean (`log_clean`), a date is bad, or
    nothing is in the range; gone once a date is edited. Dismisses after
    writing the file, with a notification.
    """

    DEFAULT_CSS = """
    ExportScreen {
        align: center middle;
    }
    ExportScreen > Vertical {
        width: 56;
        height: auto;
        padding: 1 2;
        border: thick $primary;
        background: $surface;
    }
    ExportScreen #export-title {
        text-style: bold;
        padding-bottom: 1;
    }
    ExportScreen #export-dates-line {
        padding-bottom: 1;
    }
    ExportScreen #export-dates {
        height: auto;
    }
    ExportScreen #export-dates > Vertical {
        width: 14;
        height: auto;
    }
    ExportScreen #export-problem {
        display: none;
        height: auto;
        padding-top: 1;
        color: $error;
    }
    ExportScreen #export-problem.-shown {
        display: block;
    }
    ExportScreen #export-buttons {
        height: auto;
        align-horizontal: right;
        padding-top: 1;
    }
    ExportScreen Button {
        margin-left: 1;
    }
    """

    # The app's keys don't reach a modal, so F2 is passed on here: the
    # no-folder message says to set one in Settings (F2).
    BINDINGS = [("escape", "cancel", "Cancel"), ("f2", "app.open_settings", "Settings")]

    def __init__(self, entries: list[dict], log_clean: bool, start: date, end: date) -> None:
        super().__init__()
        self.entries = entries
        self.log_clean = log_clean
        self.start = start
        self.end = end

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Export", id="export-title")
            yield Label(DATES_LINE, id="export-dates-line")
            with Horizontal(id="export-dates"):
                with Vertical():
                    yield Label("From")
                    yield Input(value=f"{self.start:%y%m%d}", id="export-from")
                with Vertical():
                    yield Label("To")
                    yield Input(value=f"{self.end:%y%m%d}", id="export-to")
            yield Static(id="export-problem")
            with Horizontal(id="export-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Export", id="export", variant="primary")

    def on_input_changed(self, event: Input.Changed) -> None:
        self.show_problem("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_export()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export":
            self.action_export()
        else:
            self.action_cancel()

    def show_problem(self, problem: str) -> None:
        shown = self.query_one("#export-problem", Static)
        shown.update(Text(problem))
        shown.set_class(bool(problem), "-shown")

    def date_field(self, field_id: str, name: str) -> date | None:
        """A date field's date, or None with why shown and the field
        focused.
        """
        field = self.query_one(f"#{field_id}", Input)
        try:
            check_ascii(name, field.value, "260923")
            return parse_date(field.value, name)
        except ValueError as error:
            self.show_problem(str(error))
            field.focus()
            return None

    def action_export(self) -> None:
        folder = self.app.settings.adif_export_folder
        if not folder:
            self.show_problem(NO_FOLDER)
            return
        if not self.log_clean:
            self.show_problem(NOT_CLEAN)
            return
        start = self.date_field("export-from", "From")
        if start is None:
            return
        end = self.date_field("export-to", "To")
        if end is None:
            return
        if start > end:
            self.show_problem(f"From {start:%y%m%d} is after To {end:%y%m%d}")
            self.query_one("#export-from", Input).focus()
            return
        entries = entries_in_range(self.entries, start, end)
        if not entries:
            self.show_problem(NOTHING_IN_RANGE)
            return
        created = datetime.now(UTC)
        # Into the folder as it is: none is made (Settings saves only one
        # that exists, but it may have gone since).
        path = folder_path(folder) / export_file_name(start, end, created)
        try:
            # "x": never over another file, should two land in one second.
            with path.open("x", encoding="ascii", newline="\n") as file:
                file.write(adif_file(entries, created, self.app.parks))
        except OSError as error:
            self.show_problem(f"{WRITE_FAILED}\n{error}")
            return
        self.app.notify(EXPORTED)
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
