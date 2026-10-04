import tomllib
from pathlib import Path

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Footer, Static

from pota_logger.dates import format_date, format_time
from pota_logger.delete_screen import DeleteScreen
from pota_logger.entry_form import FIELDS, EntryForm
from pota_logger.freq import format_freq
from pota_logger.logbook import Logbook, LogWriteError
from pota_logger.parks import MAX_LENGTH as PARK_MAX_LENGTH
from pota_logger.power import format_power
from pota_logger.settings import (
    SETTINGS_PATH,
    Settings,
    StationCallsignError,
    load_settings,
    save_settings,
)
from pota_logger.settings_screen import SettingsScreen
from pota_logger.status_bar import StatusBar
from pota_logger.theme import POTA_THEME
from pota_logger.warning_screen import WarningScreen


# How parsed values are shown in the log table, and their widths when
# wider than the entered text.
FORMATTERS = {
    "FREQ": format_freq,
    "PWR": format_power,
    "DATE": format_date,
    "TIME": format_time,
}
DISPLAY_LENGTHS = {
    "PARK": PARK_MAX_LENGTH,
    "PWR": len("1500W"),
    "DATE": len("2026.09.23"),
    "TIME": len("21:23"),
}

# Marks entries typed this session in the log's first column, which has no
# header. Kept to one character so the column can later show other states.
SESSION_MARKER = "•"

# Marks saved entries (from the log files at start) edited this session.
# Like SESSION_MARKER, it isn't saved; this session's entries keep theirs.
EDITED_MARKER = "✎"

# The log's columns, (label, width): the marker, then the fields. Fixed
# widths: DataTable doesn't redraw rows it already drew when an auto-width
# column widens, which left the first entry truncated.
LOG_COLUMNS = [("", len(SESSION_MARKER))] + [
    (name, max(len(name), DISPLAY_LENGTHS.get(name, max_length)))
    for name, _, max_length in FIELDS
]

# Style of the first saved row when entries were typed this session: a
# divider between those above (as typed) and the saved ones (sorted). An
# overline sits on the cell's top edge, where an underline would sit at the
# font's underline position, partway up a highlighted row. A terminal
# without overline support just draws no divider.
DIVIDER_STYLE = "overline"

# What the delete modal says, above its Enter-twice line.
DELETE_MESSAGE = (
    "Delete this record?\n"
    "{CALL} on {FREQ} {MODE}\n"
    "{DATE} {TIME} UTC\n"
    "Gone is gone: there's no undo."
)

# f3 or f4 with no log row selected.
SELECT_FIRST = "Double-click a record or press Enter when log area has focus first."

# When a log file can't be written: Enter tries again, Esc goes back with
# nothing saved. One message when permissions are at fault, the other for
# anything else, most likely another program holding the file.
WRITE_FAILED_PERMISSION = (
    "Couldn't save to {name}:\n"
    "Permission Denied - Check file system\n"
    "permissions on file.\n"
    "Enter to try again, or Esc to go back."
)
WRITE_FAILED = (
    "Couldn't save to {name}:\n"
    "Close all programs that have the file\n"
    "open. Changes made there will be lost, so\n"
    "copy them somewhere first if desired.\n"
    "Never edit a raw log during app use.\n"
    "Enter to try again, or Esc to go back."
)

# Shown, as a block, while no station callsign is set: at start, on Enter
# in the form, and when Settings is left without one.
STATION_CALLSIGN_REQUIRED = (
    "A transmitting station callsign\nis required.\nPress Enter to go to Settings."
)


def log_cell(value: str, width: int, style: str = "") -> Text:
    """A log cell, padded one space each side. The cells carry their own
    padding (the table's cell_padding is 0) so the divider's line runs
    unbroken across the row. Text, not str, so DataTable doesn't read
    brackets in a COMMENT as markup.
    """
    return Text(f" {value:<{width}} ", style=style)


def log_row(values: dict, marker: str = "", style: str = "") -> list[Text]:
    """An entry's cells in the log table: its marker, then FIELDS order."""
    shown = values | {
        name: format_value(values[name]) for name, format_value in FORMATTERS.items()
    }
    cells = [marker] + [shown[name] for name, _, _ in FIELDS]
    return [log_cell(cell, width, style) for cell, (_, width) in zip(cells, LOG_COLUMNS)]


class PotaLoggerApp(App):
    """POTA logger TUI."""

    CSS = """
    #log-table {
        /* Full width: left to itself, it came out narrower beside the
           entry form's side margins. */
        width: 100%;
        height: 1fr;
    }
    /* A selected row keeps the focused cursor's darker highlight while
       the form has focus. */
    #log-table.-selected > .datatable--cursor {
        background: $block-cursor-background;
        color: $block-cursor-foreground;
        text-style: $block-cursor-text-style;
    }
    #button-bar {
        height: auto;
        align-horizontal: right;
    }
    #button-bar > Button {
        margin-left: 1;
    }
    /* Footer shares its row with the terminal size, on the right. */
    #footer-bar {
        dock: bottom;
        height: 1;
    }
    #footer-bar > Footer {
        dock: none;
        width: 1fr;
    }
    #terminal-size {
        width: auto;
        padding: 0 1;
        color: $footer-foreground;
        background: $footer-background;
    }
    """

    # No command palette: "palette" is unfamiliar to most operators, and
    # its Theme command would switch away from the POTA theme.
    ENABLE_COMMAND_PALETTE = False

    # Redeclares Textual's built-in ctrl+q so it shows in the footer.
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("f2", "open_settings", "Settings"),
        Binding("f3", "edit_entry", "Edit"),
        Binding("f4", "delete_entry", "Delete"),
        Binding("ctrl+s", "screenshot", "Screenshot"),
        # Shown in the form's border title while editing, not the footer.
        Binding("escape", "step_back", "Back", show=False),
    ]

    def __init__(self, settings_path: Path = SETTINGS_PATH) -> None:
        super().__init__()
        self.register_theme(POTA_THEME)
        self.theme = POTA_THEME.name
        self.settings_path = settings_path
        # Log files sit beside the settings, in data/.
        self.logbook = Logbook(settings_path.parent)
        self.settings_error: str | None = None
        # A refused station callsign from the file, shown in Settings to
        # correct (most likely a slip) until a call is saved.
        self.station_callsign_to_fix = ""
        try:
            self.settings = load_settings(settings_path)
        except tomllib.TOMLDecodeError as error:
            self.settings = Settings()
            self.settings_error = f"Couldn't read {settings_path}: {error}"
        except StationCallsignError as error:
            # None is set, so the app asks for one.
            self.settings = Settings()
            self.settings_error = f"{settings_path}: {error}"
            self.station_callsign_to_fix = error.text

    def compose(self) -> ComposeResult:
        yield StatusBar(station_callsign=self.settings.station_callsign)
        yield EntryForm()
        yield DataTable(id="log-table", cell_padding=0)
        with Horizontal(id="button-bar"):
            # Mouse only, so tabbing through fields can't land on them.
            for button in (
                Button("Settings", id="settings"),
                Button("Quit", id="quit", variant="warning"),
            ):
                button.can_focus = False
                yield button
        with Horizontal(id="footer-bar"):
            yield Footer()
            yield Static(id="terminal-size")

    def on_resize(self, event: events.Resize) -> None:
        self.query_one("#terminal-size", Static).update(f"{event.size.width}x{event.size.height}")

    def on_mount(self) -> None:
        table = self.query_one("#log-table", DataTable)
        for label, width in LOG_COLUMNS:
            table.add_column(log_cell(label, width), width=width + 2)
        self.query_one("#field-freq").focus()
        if self.settings_error:
            self.notify(self.settings_error, severity="error", timeout=30)
        entries, problems = self.logbook.load()
        self.query_one(EntryForm).logged.extend(entries)
        # Saved entries newest first; entries typed this session go above
        # them in the order typed, to check against the paper log.
        self.saved_entries = sorted(
            entries, key=lambda entry: (entry["DATE"], entry["TIME"]), reverse=True
        )
        self.session_entries: list[dict] = []
        # Saved entries edited this session, marked in the log.
        self.edited_entries: list[dict] = []
        # The entry whose log row is selected, shown in the form.
        self.selected: dict | None = None
        self.show_log()
        for problem in problems:
            self.notify(f"Skipped {problem}", severity="error", timeout=30)
        if not self.settings.station_callsign:
            self.require_station_callsign()

    def save(self, write, saved, failed: str) -> None:
        """Run `write` (a Logbook change), then `saved` once it's written. If
        a file can't be written, a modal offers to try again; Esc leaves
        things as they were (the entry still in the form). A `failed`
        notification covers anything else that stops the save.
        """
        try:
            write()
        except LogWriteError as error:
            message = (
                WRITE_FAILED_PERMISSION
                if isinstance(error.error, PermissionError)
                else WRITE_FAILED
            ).format(name=error.path.name)
            # `error` itself is cleared when this block ends.
            writes = error.writes

            def try_again(retry: bool) -> None:
                if retry:
                    self.save(lambda: self.logbook.write(writes), saved, failed)

            # No id: trying again may open the next one before this one's gone.
            self.push_screen(WarningScreen(message, confirm_label="Try again"), try_again)
        except ValueError as error:
            self.notify(f"{failed}: {error}", severity="error", timeout=30)
        else:
            saved()

    def on_entry_form_submitted(self, event: EntryForm.Submitted) -> None:
        self.save(
            lambda: self.logbook.append(event.values),
            lambda: self.entry_saved(event.values),
            "Couldn't save the entry",
        )

    def entry_saved(self, values: dict) -> None:
        self.query_one(EntryForm).entry_saved(values)
        self.session_entries.append(values)
        self.show_log()
        # Highlighted, so f3 edits the entry just typed. scroll_to_row
        # brings it into view.
        row = len(self.session_entries) - 1
        self.query_one("#log-table", DataTable).move_cursor(row=row, scroll=False)
        self.call_after_refresh(self.scroll_to_row, row)

    def log_entries(self) -> list[dict]:
        """The entries in the log table's order: this session's, then saved."""
        return self.session_entries + self.saved_entries

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "step_back":
            return self.selected is not None
        return True

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        """Double-click, or Enter, on a cell selects its row."""
        table = self.query_one("#log-table", DataTable)
        self.selected = self.log_entries()[event.coordinate.row]
        table.cursor_type = "row"
        table.add_class("-selected")
        self.query_one(EntryForm).show(self.selected)
        table.focus()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """The selection follows the row cursor, except while editing,
        when the cursor stays on the entry being edited.
        """
        if self.selected is None:
            return
        table = self.query_one("#log-table", DataTable)
        form = self.query_one(EntryForm)
        if form.editing is not None:
            row = self.log_row_of(self.selected)
            if table.cursor_row != row:
                table.move_cursor(row=row, scroll=False)
            return
        entry = self.log_entries()[table.cursor_row]
        if entry is not self.selected:
            self.selected = entry
            form.show(entry)

    def log_row_of(self, entry: dict) -> int:
        return next(i for i, logged in enumerate(self.log_entries()) if logged is entry)

    def action_edit_entry(self) -> None:
        # App bindings stay live under a modal; edit only from the main screen.
        if len(self.screen_stack) > 1:
            return
        form = self.query_one(EntryForm)
        if form.editing is not None:
            return
        if self.selected is None:
            self.notify(SELECT_FIRST, severity="warning")
            return
        # While editing, the form keeps focus; the log still scrolls.
        self.query_one("#log-table", DataTable).can_focus = False
        form.edit()

    def action_delete_entry(self) -> None:
        # App bindings stay live under a modal; delete only from the main
        # screen. Allowed while editing: the edit goes with the entry.
        if len(self.screen_stack) > 1:
            return
        if self.selected is None:
            self.notify(SELECT_FIRST, severity="warning")
            return
        entry = self.selected
        shown = entry | {
            name: format_value(entry[name]) for name, format_value in FORMATTERS.items()
        }

        def confirmed(delete: bool) -> None:
            if delete:
                self.save(
                    lambda: self.logbook.delete(entry),
                    lambda: self.entry_deleted(entry),
                    "Couldn't delete the entry",
                )

        self.push_screen(DeleteScreen(DELETE_MESSAGE.format(**shown)), confirmed)

    def entry_deleted(self, entry: dict) -> None:
        """Drop a deleted entry from the log, leaving nothing selected and
        the form ready for a new entry (what it held before put back).
        """
        form = self.query_one(EntryForm)
        for entries in (
            self.session_entries,
            self.saved_entries,
            self.edited_entries,
            form.logged,
        ):
            entries[:] = [logged for logged in entries if logged is not entry]
        table = self.query_one("#log-table", DataTable)
        row = table.cursor_row
        self.show_log()
        if table.row_count:
            table.move_cursor(row=min(row, table.row_count - 1))
        if form.editing is not None:
            form.finish_edit(entry)
            table.can_focus = True
        self.leave_selection()

    def action_step_back(self) -> None:
        """Esc: from editing to the row still selected (changes dropped),
        then to no row selected, with the form as it was before.
        """
        table = self.query_one("#log-table", DataTable)
        form = self.query_one(EntryForm)
        if form.editing is not None:
            form.finish_edit(self.selected)
            table.can_focus = True
            table.focus()
            return
        self.leave_selection()

    def leave_selection(self) -> None:
        """No row selected, with the form as it was before."""
        table = self.query_one("#log-table", DataTable)
        self.selected = None
        table.cursor_type = "cell"
        table.remove_class("-selected")
        self.query_one(EntryForm).hide()

    def on_entry_form_edited(self, event: EntryForm.Edited) -> None:
        # Until it's saved, the form stays in edit mode, to try again or
        # cancel.
        self.save(
            lambda: self.logbook.replace(event.old, event.new),
            lambda: self.edit_saved(event),
            "Couldn't save the change",
        )

    def edit_saved(self, event: EntryForm.Edited) -> None:
        # The entry keeps its place in the log until the next start, even if
        # DATE or TIME changed, and stays selected.
        form = self.query_one(EntryForm)
        # Marked edited once; edited again, the mark carries over below.
        if any(entry is event.old for entry in self.saved_entries) and not any(
            entry is event.old for entry in self.edited_entries
        ):
            self.edited_entries.append(event.old)
        for entries in (
            self.session_entries,
            self.saved_entries,
            self.edited_entries,
            form.logged,
        ):
            for index, entry in enumerate(entries):
                if entry is event.old:
                    entries[index] = event.new
        self.selected = event.new
        self.show_log()
        table = self.query_one("#log-table", DataTable)
        table.move_cursor(row=self.log_row_of(event.new))
        form.finish_edit(event.new)
        table.can_focus = True
        table.focus()

    def show_log(self) -> None:
        # DataTable can't insert a row mid-table, so it's redrawn in full.
        table = self.query_one("#log-table", DataTable)
        table.clear()
        saved_rows = [
            log_row(
                entry,
                EDITED_MARKER if any(entry is edited for edited in self.edited_entries) else "",
                # The divider, over the first saved row.
                DIVIDER_STYLE if self.session_entries and index == 0 else "",
            )
            for index, entry in enumerate(self.saved_entries)
        ]
        table.add_rows(
            [log_row(entry, SESSION_MARKER) for entry in self.session_entries] + saved_rows
        )

    def scroll_to_row(self, index: int) -> None:
        """Scroll the log just enough to show a row, from the top."""
        table = self.query_one("#log-table", DataTable)
        rows_in_view = table.scrollable_content_region.height - table.header_height
        table.scroll_to(y=max(0, index - rows_in_view + 1), animate=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.exit()
        elif event.button.id == "settings":
            self.action_open_settings()

    def action_screenshot(self) -> None:
        # Textual's own screenshot: an SVG saved to the Downloads folder,
        # with a notification.
        self.deliver_screenshot()

    def action_open_settings(self) -> None:
        # App bindings stay live under a modal, so don't stack a second one,
        # even when another modal (its unusual-callsign warning) is on top.
        # Under the station-callsign block, Enter is the way to Settings.
        if any(
            isinstance(screen, SettingsScreen) or screen.id == "station-callsign-required"
            for screen in self.screen_stack
        ):
            return
        self.show_settings()

    def show_settings(self) -> None:
        shown = Settings(
            station_callsign=self.settings.station_callsign or self.station_callsign_to_fix
        )
        self.push_screen(SettingsScreen(shown), self.apply_settings)

    def require_station_callsign(self) -> None:
        """Block until a station callsign is set: Enter opens Settings, and
        leaving it without one comes back here. Ctrl+Q still quits.
        """
        self.push_screen(
            WarningScreen(
                STATION_CALLSIGN_REQUIRED,
                confirm_label="Settings",
                can_go_back=False,
                id="station-callsign-required",
            ),
            lambda _: self.show_settings(),
        )

    def apply_settings(self, settings: Settings | None) -> None:
        if settings is not None:
            self.settings = settings
            self.station_callsign_to_fix = ""
            save_settings(settings, self.settings_path)
            self.query_one(StatusBar).set_station_callsign(settings.station_callsign)
        if not self.settings.station_callsign:
            self.require_station_callsign()


def main() -> None:
    PotaLoggerApp().run()
