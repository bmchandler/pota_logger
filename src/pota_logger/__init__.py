import tomllib
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.content import Content
from textual.widgets import Button, DataTable, Footer, Static

from pota_logger import file_errors
from pota_logger.dates import format_date, format_time
from pota_logger.delete_screen import DeleteScreen
from pota_logger.dupes import dupe_key
from pota_logger.entry_form import LOG_FIELDS, EntryForm
from pota_logger.freq import format_freq
from pota_logger.logbook import COLUMNS, FIX_BY_HAND, Logbook, LogWriteError, refused_texts
from pota_logger.parks import MAX_LENGTH as PARK_MAX_LENGTH
from pota_logger.power import format_power
from pota_logger.record_ids import new_id, parse_id
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
    # Fills the log's width, or as wide as the longest COMMENT shown (see
    # log_columns), at least its header.
    "COMMENT": 0,
}

# Marks entries typed this session in the log's first column, which has no
# header. Kept to one character so the column can later show other states.
SESSION_MARKER = "•"

# Marks rows refused on load, shown as they are in the file, to fix (or
# delete) in the app.
REFUSED_MARKER = "!"

# Marks saved entries that share their record ID with another: saved
# twice, or two versions of one record. A refused row keeps its `!`.
SHARED_MARKER = "U"

# Marks saved entries that are definite dupes of another (see dupes.py),
# unless they share an ID too.
DUPE_MARKER = "="

# Marks saved entries (from the log files at start) edited this session.
# Like SESSION_MARKER, it isn't saved; this session's entries keep theirs.
EDITED_MARKER = "✎"

# Counts of the saved rows marked for a problem, beside the Quit
# button while there are any, one line each: (one, several) wordings,
# long when every line fits, short otherwise.
MARK_COUNTS = {
    REFUSED_MARKER: (
        ("1 record refused, marked !", "{count} records refused, marked !"),
        ("! 1 refused", "! {count} refused"),
    ),
    # One alone when its copy is marked ! (a refused row keeps its mark).
    SHARED_MARKER: (
        ("1 record shares a record ID, marked U", "{count} records share a record ID, marked U"),
        ("U 1 shares an ID", "U {count} share an ID"),
    ),
    # One alone when its copy is marked U.
    DUPE_MARKER: (
        ("1 record is a dupe, marked =", "{count} records are dupes, marked ="),
        ("= 1 dupe", "= {count} dupes"),
    ),
}


def mark_count_lines(counts: Counter, width: int) -> list[str]:
    """MARK_COUNTS lines for the marks counted, long if all fit in `width`."""
    forms = [
        [wording[count != 1].format(count=count) for wording in MARK_COUNTS[marker]]
        for marker in MARK_COUNTS
        if (count := counts[marker])
    ]
    fits = all(len(long_form) <= width for long_form, _ in forms)
    return [long_form if fits else short_form for long_form, short_form in forms]

# The log's columns, (label, width): the marker, then the fields. Fixed
# widths: DataTable doesn't redraw rows it already drew when an auto-width
# column widens, which left the first entry truncated.
LOG_COLUMNS = [("", len(SESSION_MARKER))] + [
    (name, max(len(name), DISPLAY_LENGTHS.get(name, max_length)))
    for name, _, max_length in LOG_FIELDS
]


def log_columns(entries: list[dict], room: int = 0) -> list[tuple[str, int]]:
    """LOG_COLUMNS for the entries shown: COMMENT takes the rest of the
    `room` the table has, so the columns (and the divider) reach its right
    edge, and widens past it for the longest COMMENT, so each is seen
    whole, however long (a file's can be longer than the form takes).
    """
    longest = max((len(entry["COMMENT"]) for entry in entries), default=0)
    # Each cell carries a space of padding each side.
    rest = room - sum(width + 2 for label, width in LOG_COLUMNS if label != "COMMENT") - 2
    return [
        (label, max(width, longest, rest) if label == "COMMENT" else width)
        for label, width in LOG_COLUMNS
    ]


# Shown after a sorted column's header: ascending, descending.
SORT_ARROWS = ("▲", "▼")


def header_cell(label: str, width: int, arrow: str = "") -> Text:
    """A log column's header, with `arrow` if the log is sorted by it:
    after a space when that fits the column, or else in the cell's right
    padding.
    """
    if arrow and len(label) + 2 <= width:
        return log_cell(f"{label} {arrow}", width)
    return Text(f" {label:<{width}}{arrow or ' '}")


def sort_key(entry: dict, name: str) -> tuple:
    """An entry's place in a Sort by column `name`: its value (text
    ignoring case), then its timestamp. So DATE sorts by date, then time
    of day; TIME by time of day alone, then date (0100 on any date before
    2300 on any date). DATE descending is the usual newest-first order.
    """
    value = entry[name]
    if isinstance(value, str):
        value = value.casefold()
    return (value, entry["DATE"], entry["TIME"])


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

# Listed below COMMENT for an entry with other copies: under a heading, a
# line for each other entry sharing its record ID, then the definite dupes
# grouped by COMMENT, then a hint.
REPEATS_HEADING = "Excluding COMMENT, duplicate record(s) exist:"
SHARED_SAME = "- Same UUIDv4 in {name}, also same in every column."
SHARED_DIFFERENT = "- Same UUIDv4 in {name}, with a different {columns}."
REPEATS_HINT = "Edit field values (f3) or delete (f4) as makes sense."

# Definite dupes, one line for those alike in COMMENT: (one, several).
DUPE_SAME = ("- Another record has same COMMENT.", "- {count} other records have same COMMENT.")
DUPE_OTHER_COMMENT = (
    "- Another record has COMMENT {comment!r}.",
    "- {count} other records have COMMENT {comment!r}.",
)
DUPE_NO_COMMENT = ("- Another record without a COMMENT.", "- {count} other records without a COMMENT.")

# A file changed on load (blank record IDs filled in, values fixed) that
# couldn't be written, in file_errors.txt.
UNSAVED_ON_LOAD = "{path}: couldn't save changes made on load: {error}. Check permissions."

# The block at start while log files need fixing by hand: lines for rows
# or files that can't be read, for files that can't be written (or
# file_errors.txt itself), where the errors are listed, and what to do.
DATA_CORRECTION = "Manual data correction required."
WRITE_FAILED_FILES = "Couldn't write to file or directory.\nCheck permissions."
SEE_FILE_ERRORS = "See {path}"
FIX_FILES = "Fix the files, then start the app again."
FIX_PERMISSIONS = "Fix the permissions, then start the app again."

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
# in the form, and when Settings is left without one. A problem with the
# settings file goes between the two, in the error color, until a call is
# saved.
STATION_CALLSIGN_REQUIRED = "A valid callsign for transmitting\nstation is required."
GO_TO_SETTINGS = "Press Enter to go to Settings."


def log_cell(value: str, width: int, style: str = "") -> Text:
    """A log cell, padded one space each side. The cells carry their own
    padding (the table's cell_padding is 0) so the divider's line runs
    unbroken across the row. Text, not str, so DataTable doesn't read
    brackets in a COMMENT as markup.
    """
    return Text(f" {value:<{width}} ", style=style)


def log_row(
    values: dict,
    columns: list[tuple[str, int]],
    marker: str = "",
    style: str = "",
    as_is: bool = False,
) -> list[Text]:
    """An entry's cells in the log table (`columns` from log_columns): its
    marker, then LOG_FIELDS order. `as_is` shows a refused row's values as they
    are in the file.
    """
    shown = values
    if not as_is:
        shown = values | {
            name: format_value(values[name]) for name, format_value in FORMATTERS.items()
        }
    cells = [marker] + [shown[name] for name, _, _ in LOG_FIELDS]
    return [log_cell(cell, width, style) for cell, (_, width) in zip(cells, columns)]


def id_key(entry: dict) -> str | None:
    """An entry's record ID, to match on; None if it doesn't read (a
    refused row's).
    """
    try:
        return parse_id(entry["UUIDv4"])
    except ValueError:
        return None


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
    #mark-counts {
        width: 1fr;
        height: 3;
        padding: 0 1;
        color: $error;
    }
    /* Notifications sit a row above the Quit button (3
       rows) and the footer (1), not over them, and a row above the
       log's sideways scrollbar while it shows. */
    ToastRack {
        margin: 0 0 5 0;
    }
    ToastRack.-log-scrolls-sideways {
        margin: 0 0 6 0;
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
        Binding("f5", "sort", "Sort"),
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
            if self.settings.fixed and not self.settings.problems:
                # How the call was written, fixed. If it can't be saved, it's
                # fixed again at the next start (as it is while the file has
                # a problem to fix by hand, which saving would hide).
                try:
                    save_settings(self.settings, settings_path)
                except OSError:
                    pass
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
            yield Static(id="mark-counts")
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
        # Raises notifications above the log's sideways scrollbar (CSS).
        # On the rack, not the screen, so only the rack is restyled.
        self.watch(
            table,
            "show_horizontal_scrollbar",
            lambda shown: table.screen.query("ToastRack").set_class(shown, "-log-scrolls-sideways"),
        )
        # Once laid out: COMMENT fills the log's width, which changes with
        # the window and the log's vertical scrollbar, and the mark counts'
        # long or short form follows their width.
        table.screen.screen_layout_refresh_signal.subscribe(self, lambda _: self.fit_log(table))
        self.query_one("#field-freq").focus()
        # Filled by load_log once there's a station callsign to check the
        # rows against.
        self.saved_entries: list[dict] = []
        self.log_loaded = False
        # Entries typed this session, marked in the log; those typed since
        # the last Sort (or start) go above the saved ones, as typed.
        self.session_entries: list[dict] = []
        self.typed_entries: list[dict] = []
        # The column the log is sorted by and whether descending, once
        # sorted.
        self.sort_by: tuple[str, bool] | None = None
        # Saved entries edited this session, marked in the log.
        self.edited_entries: list[dict] = []
        # The entry whose log row is selected, shown in the form.
        self.selected: dict | None = None
        self.mark_counts_text = ""
        if self.settings.station_callsign:
            self.load_log()
        else:
            self.show_log()
            self.require_station_callsign()

    def load_log(self) -> None:
        """Load the log files, checked against the station callsign, and
        show them, blocking if any need fixing by hand.
        """
        self.log_loaded = True
        entries, problems = self.logbook.load(self.settings.station_callsign)
        problems += [f"{self.settings_path}: {problem}" for problem in self.settings.problems]
        self.query_one(EntryForm).logged.extend(entries)
        # Saved entries newest first, under any refused rows (in file order,
        # to be seen and fixed); entries typed this session go above them in
        # the order typed, to check against the paper log.
        self.saved_entries = [found.row for found in self.logbook.refused] + sorted(
            entries, key=lambda entry: (entry["DATE"], entry["TIME"]), reverse=True
        )
        self.show_log()
        self.block_on_file_errors(problems)

    def block_on_file_errors(self, problems: list[str]) -> bool:
        """Record what in the log files needs fixing by hand (rows or files
        that can't be read, `problems`, and changes made on load that
        couldn't be written) in file_errors.txt, and block with Quit as the only way on
        if there's anything; True if so. With nothing, file_errors.txt goes.
        """
        unsaved = [
            UNSAVED_ON_LOAD.format(path=path, error=error.strerror or error)
            for path, error in self.logbook.unsaved
        ]
        try:
            path = file_errors.record(
                self.logbook.log_dir, problems + unsaved, datetime.now(UTC)
            )
        except OSError:
            path = None
        if not problems and not unsaved:
            # An old file_errors.txt that can't be removed is left: without
            # write access, saving says so anyway.
            return False
        lines = [DATA_CORRECTION] if problems else []
        if unsaved or path is None:
            lines.append(WRITE_FAILED_FILES)
        if path is None:
            lines += ["", FIX_PERMISSIONS]
        else:
            lines += [SEE_FILE_ERRORS.format(path=path), "", FIX_FILES]
        self.push_screen(
            WarningScreen(
                "\n".join(lines), confirm_label="Quit", can_go_back=False, id="file-errors"
            ),
            lambda _: self.exit(),
        )
        return True

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
        self.typed_entries.append(values)
        table = self.query_one("#log-table", DataTable)
        # Redrawing puts the cursor back in the first column; it stays in
        # its own, so f5 sorts by the same column.
        column = table.cursor_column
        self.show_log()
        # Highlighted, so f3 edits the entry just typed. scroll_to_row
        # brings it into view.
        row = len(self.typed_entries) - 1
        table.move_cursor(row=row, column=column, scroll=False)
        self.call_after_refresh(self.scroll_to_row, row)

    def log_entries(self) -> list[dict]:
        """The entries in the log table's order: those typed since the last
        Sort, then saved (or sorted).
        """
        return self.typed_entries + self.saved_entries

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "step_back":
            return self.selected is not None
        # Only with the cell cursor, whose column is the one to sort by:
        # shown dimmed while a row is selected.
        if action == "sort":
            return None if self.selected is not None else True
        return True

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        """Double-click, or Enter, on a cell selects its row."""
        table = self.query_one("#log-table", DataTable)
        self.selected = self.log_entries()[event.coordinate.row]
        table.cursor_type = "row"
        table.add_class("-selected")
        self.query_one(EntryForm).show(self.selected, *self.entry_view(self.selected))
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
            form.show(entry, *self.entry_view(entry))

    def entry_view(self, entry: dict) -> tuple[dict[str, str] | None, list[tuple[str, str]]]:
        """What the form shows for an entry besides the entry itself: for
        a refused row, its values as texts, and its problems as (field,
        line) pairs under a heading naming its file and row (any other
        entry is shown as it'd be typed); then, if it shares its record ID,
        where the other copies are.
        """
        refusal = self.logbook.refusal(entry)
        if refusal is None:
            return None, self.repeat_lines(entry)
        problems = [("", f"Refused from {refusal.path.name} row {refusal.line}:")] + [
            (problem.field, f"- {problem.message}. {problem.note}".rstrip())
            for problem in refusal.problems
        ]
        return refused_texts(entry), problems + self.repeat_lines(entry)

    def repeat_lines(self, entry: dict) -> list[tuple[str, str]]:
        """The entry's other copies, as lines for the form: those sharing
        its record ID first, with what differs, then its definite dupes
        (refused rows aside), grouped by how their COMMENT compares. No
        field is marked: either copy may be the right one.
        """
        record_id = id_key(entry)
        shared = [
            other
            for other in self.log_entries()
            if other is not entry and record_id is not None and id_key(other) == record_id
        ]
        key = dupe_key(entry)
        dupes = [
            other
            for other in self.log_entries()
            if other is not entry
            and not any(other is copy for copy in shared)
            and not self.logbook.is_refused(entry)
            and not self.logbook.is_refused(other)
            and dupe_key(other) == key
        ]
        if not shared and not dupes:
            return []
        lines = [REPEATS_HEADING]
        _, own = self.logbook.stored(entry)
        for other in shared:
            path, row = self.logbook.stored(other)
            columns = [
                name
                for name, mine, theirs in zip(COLUMNS, own, row)
                if mine != theirs and name != "UUIDv4"
            ]
            if columns:
                listed = " and ".join([", ".join(columns[:-1]), columns[-1]] if columns[1:] else columns)
                lines.append(SHARED_DIFFERENT.format(name=path.name, columns=listed))
            else:
                lines.append(SHARED_SAME.format(name=path.name))
        # The same COMMENT first, then the others in log order.
        comments = Counter(other["COMMENT"] for other in dupes)
        order = sorted(comments, key=lambda comment: comment != entry["COMMENT"])
        for comment in order:
            if comment == entry["COMMENT"]:
                wording = DUPE_SAME
            elif comment:
                wording = DUPE_OTHER_COMMENT
            else:
                wording = DUPE_NO_COMMENT
            count = comments[comment]
            lines.append(wording[count > 1].format(count=count, comment=comment))
        return [("", line) for line in lines + [REPEATS_HINT]]

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
        refusal = self.logbook.refusal(self.selected)
        # A STATION_CALLSIGN that doesn't read or isn't the station
        # callsign: the form has no field for it.
        by_hand = [
            problem for problem in (refusal.problems if refusal else []) if problem.note == FIX_BY_HAND
        ]
        if by_hand:
            self.notify(f"{by_hand[0].message}. {FIX_BY_HAND}", severity="warning", timeout=30)
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
        shown = entry
        if not self.logbook.is_refused(entry):
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
            self.typed_entries,
            self.saved_entries,
            self.edited_entries,
            form.logged,
        ):
            entries[:] = [logged for logged in entries if logged is not entry]
        table = self.query_one("#log-table", DataTable)
        row, column = table.cursor_coordinate
        self.show_log()
        if table.row_count:
            table.move_cursor(row=min(row, table.row_count - 1), column=column)
        if form.editing is not None:
            form.finish_edit(entry, *self.entry_view(entry))
            table.can_focus = True
        self.leave_selection()

    def action_step_back(self) -> None:
        """Esc: from editing to the row still selected (changes dropped),
        then to no row selected, with the form as it was before.
        """
        table = self.query_one("#log-table", DataTable)
        form = self.query_one(EntryForm)
        if form.editing is not None:
            form.finish_edit(self.selected, *self.entry_view(self.selected))
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
        if self.logbook.is_refused(event.old):
            # An ID that doesn't read can't be kept.
            try:
                parse_id(event.new["UUIDv4"])
            except ValueError:
                event.new["UUIDv4"] = new_id()
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
        # A fixed refused row joins the entries checked for dupes.
        if self.logbook.is_refused(event.old):
            form.logged.append(event.new)
        # Marked edited once; edited again, the mark carries over below.
        if not any(
            entry is event.old for entry in self.session_entries + self.edited_entries
        ):
            self.edited_entries.append(event.old)
        for entries in (
            self.session_entries,
            self.typed_entries,
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
        form.finish_edit(event.new, *self.entry_view(event.new))
        table.can_focus = True
        table.focus()

    def action_sort(self) -> None:
        # App bindings stay live under a modal; sort only from the main
        # screen.
        if len(self.screen_stack) > 1:
            return
        self.sort_log(self.query_one("#log-table", DataTable).cursor_column)

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        # Like f5, only while no row is selected.
        if self.selected is None:
            self.sort_log(event.column_index)

    def sort_log(self, column: int) -> None:
        """Sort every entry by a log column, ascending, or descending if
        it's sorted ascending already, under any refused rows (in their
        order: their values may not read). Entries typed since go above,
        as typed. The cursor goes to the top of the column.
        """
        # The marker column has no header to sort by.
        if column == 0:
            return
        name = LOG_FIELDS[column - 1][0]
        descending = self.sort_by == (name, False)
        self.sort_by = (name, descending)
        entries = self.log_entries()
        refused = [entry for entry in entries if self.logbook.is_refused(entry)]
        rest = [entry for entry in entries if not self.logbook.is_refused(entry)]
        self.saved_entries = refused + sorted(
            rest, key=lambda entry: sort_key(entry, name), reverse=descending
        )
        self.typed_entries = []
        self.show_log()
        self.query_one("#log-table", DataTable).move_cursor(row=0, column=column)

    def show_log(self) -> None:
        # DataTable can't insert a row mid-table, so it's redrawn in full,
        # columns too, as COMMENT's width follows the entries shown.
        table = self.query_one("#log-table", DataTable)
        table.clear(columns=True)
        columns = self.log_columns()
        for label, width in columns:
            arrow = ""
            if self.sort_by is not None and self.sort_by[0] == label:
                arrow = SORT_ARROWS[self.sort_by[1]]
            table.add_column(header_cell(label, width, arrow), width=width + 2)
        repeats = self.repeats()
        saved_rows = [
            log_row(
                entry,
                columns,
                self.saved_marker(entry, *repeats),
                # The divider, over the first saved row.
                DIVIDER_STYLE if self.typed_entries and index == 0 else "",
                as_is=self.logbook.is_refused(entry),
            )
            for index, entry in enumerate(self.saved_entries)
        ]
        table.add_rows(
            [log_row(entry, columns, SESSION_MARKER) for entry in self.typed_entries]
            + saved_rows
        )
        self.mark_counts = Counter(str(row[0]).strip() for row in saved_rows)
        self.show_mark_counts()

    def show_mark_counts(self) -> None:
        shown = self.query_one("#mark-counts", Static)
        text = "\n".join(mark_count_lines(self.mark_counts, shown.content_region.width))
        # Only on a change: an update lays the screen out again.
        if text != self.mark_counts_text:
            self.mark_counts_text = text
            shown.update(Text(text))

    def log_columns(self) -> list[tuple[str, int]]:
        table = self.query_one("#log-table", DataTable)
        return log_columns(self.log_entries(), table.scrollable_content_region.width)

    def fit_log(self, table: DataTable) -> None:
        """Redraw the log if its width calls for a different COMMENT column,
        keeping the cursor and scroll where they were, and fit the mark
        counts to theirs. Not under a modal: the log is laid out again when
        it's back on top.
        """
        if table.screen is not self.screen:
            return
        self.show_mark_counts()
        widths = [column.width - 2 for column in table.columns.values()]
        if widths == [width for _, width in self.log_columns()]:
            return
        cursor = table.cursor_coordinate
        x, y = table.scroll_x, table.scroll_y
        self.show_log()
        table.move_cursor(row=cursor.row, column=cursor.column, scroll=False)
        table.scroll_to(x, y, animate=False)

    def repeats(self) -> tuple[set[str], set[tuple]]:
        """Record IDs held by more than one entry in the log, and the dupe
        keys of entries that are definite dupes (refused rows aside, as
        their values are text as found).
        """
        entries = self.log_entries()
        ids = Counter(id_key(entry) for entry in entries)
        keys = Counter(dupe_key(entry) for entry in entries if not self.logbook.is_refused(entry))
        return (
            {record_id for record_id, count in ids.items() if count > 1 and record_id},
            {key for key, count in keys.items() if count > 1},
        )

    def saved_marker(self, entry: dict, shared_ids: set[str], dupe_keys: set[tuple]) -> str:
        # This session's entries keep their mark once sorted in.
        if any(entry is typed for typed in self.session_entries):
            return SESSION_MARKER
        if self.logbook.is_refused(entry):
            return REFUSED_MARKER
        if id_key(entry) in shared_ids:
            return SHARED_MARKER
        if dupe_key(entry) in dupe_keys:
            return DUPE_MARKER
        if any(entry is edited for edited in self.edited_entries):
            return EDITED_MARKER
        return ""

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
        # Under the station-callsign block, Enter is the way to Settings;
        # under the file errors block, there's no way on but Quit.
        if any(
            isinstance(screen, SettingsScreen)
            or screen.id in ("station-callsign-required", "file-errors")
            for screen in self.screen_stack
        ):
            return
        self.show_settings()

    def show_settings(self) -> None:
        # The station callsign only while none is set: a log holds one.
        with_callsign = not self.settings.station_callsign
        shown = replace(
            self.settings,
            station_callsign=self.settings.station_callsign or self.station_callsign_to_fix,
        )
        self.push_screen(SettingsScreen(shown, with_callsign), self.apply_settings)

    def require_station_callsign(self) -> None:
        """Block until a station callsign is set: Enter opens Settings, and
        leaving it without one comes back here. Ctrl+Q still quits.
        """
        if self.settings_error:
            message = Content.assemble(
                STATION_CALLSIGN_REQUIRED + "\n\n",
                (self.settings_error, "$error"),
                "\n\n" + GO_TO_SETTINGS,
            )
        else:
            message = Content(STATION_CALLSIGN_REQUIRED + "\n" + GO_TO_SETTINGS)
        self.push_screen(
            WarningScreen(
                message,
                confirm_label="Settings",
                can_go_back=False,
                id="station-callsign-required",
            ),
            lambda _: self.show_settings(),
        )

    def apply_settings(self, settings: Settings | None) -> None:
        if settings is not None:
            self.settings = settings
            # Saving rewrites the file, so whatever was wrong with it goes.
            self.settings_error = None
            self.station_callsign_to_fix = ""
            save_settings(settings, self.settings_path)
            self.query_one(StatusBar).set_station_callsign(settings.station_callsign)
            self.query_one(EntryForm).settings_changed()
        if not self.settings.station_callsign:
            self.require_station_callsign()
        elif not self.log_loaded:
            self.load_log()


def main() -> None:
    PotaLoggerApp().run()
