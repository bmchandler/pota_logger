from collections.abc import Sequence
from datetime import date, time
from decimal import Decimal

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from rich.text import Text
from textual.widgets import Input, Label, Static

from pota_logger.ascii_text import check_ascii
from pota_logger.callsign_warning_screen import CallsignWarningScreen
from pota_logger.callsigns import is_usual_callsign, parse_callsign
from pota_logger.dates import default_date, parse_date, parse_time
from pota_logger.dupes import DUPE_BUTTON, EDIT_DUPE_MESSAGE, NEW_DUPE_MESSAGE, is_dupe
from pota_logger.entry_warnings import (
    future_time,
    state_on_non_us_park,
    voice_outside_range,
)
from pota_logger.freq import format_freq, parse_freq
from pota_logger.modes import parse_mode
from pota_logger.parks import MAX_LENGTH as PARK_MAX_LENGTH
from pota_logger.parks import parse_park
from pota_logger.power import parse_power
from pota_logger.record_ids import new_id
from pota_logger.reports import THREE_DIGIT_MODE, parse_report
from pota_logger.sidebands import check_sideband
from pota_logger.states import parse_state
from pota_logger.warning_screen import WarningScreen

# (name, placeholder, longest expected value) for the fields above COMMENT,
# in paper-log order: the log table's columns and the CSV files'.
LOG_ROW_FIELDS = [
    ("FREQ", "14.074.5", 10),  # 29.700.000
    ("MODE", "SSB", 3),
    ("CALL", "W1ABC", 12),  # VE3/W1ABC/P
    ("PARK", "1234", 8),  # US-10123
    ("ST", "NJ", 2),
    ("SNT", "59", 3),
    ("RCD", "59", 3),
    ("PWR", "60", 4),  # 1500
    ("DATE", "260925", 6),
    ("TIME", "1953", 4),
]

# The form's top row, in entry order: the fields typed on every entry
# first, then PWR, DATE, and MODE, which carry forward, so Enter is
# usually pressed before reaching them.
ENTRY_ORDER = ["FREQ", "CALL", "PARK", "ST", "SNT", "RCD", "TIME", "PWR", "DATE", "MODE"]
ROW_FIELDS = sorted(LOG_ROW_FIELDS, key=lambda field: ENTRY_ORDER.index(field[0]))

# Input border and padding (4) plus a cell for the cursor.
INPUT_EXTRA_WIDTH = 5

# COMMENT sits below the row, as wide as it, and holds what fits there.
ROW_WIDTH = sum(max_length + INPUT_EXTRA_WIDTH for _, _, max_length in ROW_FIELDS)
COMMENT_LENGTH = ROW_WIDTH - INPUT_EXTRA_WIDTH

# Every field, in entry order, and in log column order.
FIELDS = ROW_FIELDS + [("COMMENT", "", COMMENT_LENGTH)]
LOG_FIELDS = LOG_ROW_FIELDS + [("COMMENT", "", COMMENT_LENGTH)]

# Most fields take any length, so their rules can explain what's wrong.
# COMMENT takes what fits in view; PARK scrolls to ADIF's longest
# reference, which is rare enough not to widen the row for.
INPUT_LIMITS = {"PARK": PARK_MAX_LENGTH, "COMMENT": COMMENT_LENGTH}

# Fields turned from entered text into values, in entry order.
PARSERS = {
    "FREQ": parse_freq,
    "CALL": parse_callsign,
    "PARK": parse_park,
    "ST": parse_state,
    "TIME": parse_time,
    "PWR": parse_power,
    "DATE": parse_date,
    "MODE": parse_mode,
}

# Signal reports, parsed after PARSERS since their rules depend on MODE.
REPORTS = ["SNT", "RCD"]

# SNT and RCD placeholder while MODE is CW, as a hint; ROW_FIELDS has the
# usual one.
CW_REPORT_PLACEHOLDER = "599"

# Fields that may be left blank.
OPTIONAL = {"ST", "COMMENT"}

# Value each field starts with, and resets to after an entry unless it's
# carried forward.
DEFAULTS = {"MODE": "SSB"}

# Fields whose default is computed fresh at app start rather than fixed.
DEFAULT_FACTORIES = {"DATE": default_date}

# Plain-ASCII example for each field's non-ASCII message: its placeholder,
# except where that doesn't cover every case.
ASCII_EXAMPLES = {name: placeholder for name, placeholder, _ in FIELDS} | {
    "SNT": "59, or 599 on CW",
    "RCD": "59, or 599 on CW",
}

# Fields that keep their value for the next entry.
CARRY_FORWARD = {"PWR", "DATE", "MODE"}

# A saved entry's values as they'd be typed, to edit in the form; the rest
# are shown as stored.
ENTRY_FORMATTERS = {
    "FREQ": format_freq,
    "PWR": lambda watts: format(watts.normalize(), "f"),
    "DATE": lambda day: f"{day:%y%m%d}",
    "TIME": lambda when: f"{when:%H%M}",
}

# The form's border title while an entry is being edited.
EDITING_TITLE = "Editing record - Esc to cancel"

# Checks run after the unusual-CALL warning, in order: (field Esc goes back
# to, check in entry_warnings.py).
WARNINGS = [
    ("FREQ", voice_outside_range),
    ("ST", state_on_non_us_park),
    ("DATE", future_time),
]


def labeled_input(name: str, placeholder: str, max_length: int) -> Vertical:
    factory = DEFAULT_FACTORIES.get(name)
    field = Input(
        value=factory() if factory else DEFAULTS.get(name, ""),
        placeholder=placeholder,
        max_length=INPUT_LIMITS.get(name, 0),
        id=f"field-{name.lower()}",
    )
    column = Vertical(Label(name), field)
    column.styles.width = max_length + INPUT_EXTRA_WIDTH
    return column


class EntryForm(Vertical):
    """Labeled inputs for a single log entry: a row, then COMMENT below."""

    DEFAULT_CSS = """
    /* Scrolls sideways only when the window is narrower than the form.
       Margins sit outside the scrollbar, so it lines up with the fields.
       The row below COMMENT is inside, above the scrollbar; while the
       scrollbar shows, a margin below it keeps the gap before the log. */
    EntryForm {
        height: auto;
        margin: 1 1 0 1;
        overflow-x: auto;
        overflow-y: hidden;
    }
    EntryForm.-scrolling {
        /* All four sides: margin-bottom alone would reset the others. */
        margin: 1;
    }
    /* While editing, a top border with the title takes the place of the
       top margin, so nothing below moves. */
    EntryForm.-editing {
        border-top: solid $warning;
        border-title-color: $warning;
        margin: 0 1 0 1;
    }
    EntryForm.-editing.-scrolling {
        margin: 0 1 1 1;
    }
    EntryForm > Vertical {
        margin-bottom: 1;
    }
    /* What's wrong with the entry shown (a row refused on load, or one
       sharing its record ID), below COMMENT, only while there's something. */
    EntryForm #entry-problems {
        display: none;
        height: auto;
        color: $error;
        margin: 0 0 1 0;
        padding: 0 1;
    }
    EntryForm #entry-problems.-shown {
        display: block;
    }
    EntryForm Horizontal, EntryForm Vertical {
        height: auto;
    }
    EntryForm Horizontal {
        width: auto;
    }
    EntryForm Label {
        padding: 0 1;
    }
    EntryForm Input {
        padding: 0 1;
    }
    """

    class Submitted(Message):
        """Posted when Enter is pressed with every field filled in and valid.

        FREQ is in Hz, PWR is watts, MODE is uppercase, PARK is a full POTA
        reference (e.g. US-0464), DATE is a date, TIME is a time, and ST is
        uppercase (possibly blank); everything else is the trimmed text as
        entered. STATION_CALLSIGN is the one set in Settings, and UUIDv4 a
        new record ID. The form keeps the entry until the app calls
        `entry_saved`, once it's saved.
        """

        def __init__(self, values: dict[str, str | int | Decimal | date | time]) -> None:
            super().__init__()
            self.values = values

    class Edited(Message):
        """Posted when Enter saves an edited entry, as Submitted does a new
        one: `old` is the entry as it was, `new` as changed. The form stays
        in edit mode until the app calls `finish_edit`, once it's saved.
        """

        def __init__(self, old: dict, new: dict) -> None:
            super().__init__()
            self.old = old
            self.new = new

    def __init__(self) -> None:
        super().__init__()
        # Entries loaded at start and saved since, to block a definite
        # dupe.
        self.logged: list[dict] = []
        # The logged entry shown (its log row selected), read-only until
        # it's edited; then also `editing`. What the form held before, and
        # the field last typed in, come back when it's no longer shown.
        self.shown: dict | None = None
        self.editing: dict | None = None
        self.put_aside: dict[str, str] = {}
        self.last_field: Input | None = None

    def watch_show_horizontal_scrollbar(self, show: bool) -> None:
        self.set_class(show, "-scrolling")

    def compose(self) -> ComposeResult:
        with Horizontal():
            for name, placeholder, max_length in ROW_FIELDS:
                yield labeled_input(name, placeholder, max_length)
        yield labeled_input("COMMENT", "", COMMENT_LENGTH)
        yield Static(id="entry-problems")

    def field(self, name: str) -> Input:
        return self.query_one(f"#field-{name.lower()}", Input)

    def values(self) -> dict[str, str]:
        return {name: self.field(name).value.strip() for name, _, _ in FIELDS}

    def on_input_blurred(self, event: Input.Blurred) -> None:
        if event.input.id == "field-mode":
            self.show_report_placeholders()

    def show_report_placeholders(self) -> None:
        """Hint 599 in SNT and RCD while MODE is CW, 59 otherwise. While an
        entry is shown read-only, there are none, since a placeholder in a
        dimmed field reads like a value.
        """
        read_only = self.shown is not None and self.editing is None
        on_cw = self.field("MODE").value.strip().upper() == THREE_DIGIT_MODE
        for name, placeholder, _ in FIELDS:
            if read_only:
                placeholder = ""
            elif name in REPORTS and on_cw:
                placeholder = CW_REPORT_PLACEHOLDER
            self.field(name).placeholder = placeholder

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        # Not while an entry is shown, so Esc returns to the entry put aside.
        if isinstance(event.widget, Input) and self.shown is None:
            self.last_field = event.widget

    def show(
        self,
        entry: dict,
        texts: dict[str, str] | None = None,
        problems: Sequence[tuple[str, str]] = (),
    ) -> None:
        """Show a logged entry, read-only, putting aside what the form held.
        Showing another entry meanwhile keeps that put aside. For a row
        refused on load, `texts` are the values to show (not the entry's
        own as they'd be typed), and `problems` are (field, line) pairs
        listed below COMMENT, each field marked invalid; a line with no
        field is a heading.
        """
        if self.shown is None:
            self.put_aside = {name: self.field(name).value for name, _, _ in FIELDS}
        self.shown = entry
        for name, _, _ in FIELDS:
            if texts is None:
                self.field(name).value = ENTRY_FORMATTERS.get(name, str)(entry[name])
            else:
                self.field(name).value = texts[name]
            self.field(name).disabled = True
        self.show_problems(problems)
        self.show_report_placeholders()

    def show_problems(self, problems: Sequence[tuple[str, str]]) -> None:
        listed = self.query_one("#entry-problems", Static)
        # Text, not str, so a value with brackets isn't read as markup.
        listed.update(Text("\n".join(line for _, line in problems)))
        listed.set_class(bool(problems), "-shown")
        at_fault = {field for field, _ in problems}
        for name, _, _ in FIELDS:
            self.field(name).set_class(name in at_fault, "-invalid")

    def edit(self) -> None:
        """Edit the entry shown."""
        self.editing = self.shown
        for name, _, _ in FIELDS:
            self.field(name).disabled = False
        self.show_report_placeholders()
        self.border_title = EDITING_TITLE
        self.add_class("-editing")
        self.field("FREQ").focus()

    def finish_edit(
        self,
        entry: dict,
        texts: dict[str, str] | None = None,
        problems: Sequence[tuple[str, str]] = (),
    ) -> None:
        """Leave edit mode, saved or cancelled, showing the entry (as saved,
        or as it was) read-only again.
        """
        self.editing = None
        self.border_title = None
        self.remove_class("-editing")
        self.show(entry, texts, problems)

    def hide(self) -> None:
        """Stop showing a logged entry, putting back what the form held,
        with focus on the field last typed in.
        """
        self.shown = None
        for name, value in self.put_aside.items():
            self.field(name).value = value
        for name, _, _ in FIELDS:
            self.field(name).disabled = False
        self.show_problems([])
        self.show_report_placeholders()
        if self.last_field is not None:
            self.last_field.focus()
        else:
            self.field("FREQ").focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        # Every entry records it (ADIF STATION_CALLSIGN), and a log row
        # without one is refused on load.
        if not self.app.settings.station_callsign:
            self.app.require_station_callsign()
            return
        values = self.values()
        missing = [name for name, value in values.items() if not value and name not in OPTIONAL]
        if missing:
            self.notify(f"Missing: {', '.join(missing)}", severity="warning")
            self.field(missing[0]).focus()
            return
        for name, value in values.items():
            try:
                check_ascii(name, value, ASCII_EXAMPLES[name])
            except ValueError as error:
                self.notify(str(error), severity="warning")
                self.field(name).focus()
                return
        parsed = {}
        for name, parse in PARSERS.items():
            try:
                parsed[name] = parse(values[name])
            except ValueError as error:
                self.notify(str(error), severity="warning")
                self.field(name).focus()
                return
        for name in REPORTS:
            try:
                parsed[name] = parse_report(name, values[name], parsed["MODE"])
            except ValueError as error:
                self.notify(str(error), severity="warning")
                self.field(name).focus()
                return
        try:
            check_sideband(parsed["FREQ"], parsed["MODE"])
        except ValueError as error:
            self.notify(str(error), severity="warning")
            self.field("MODE").focus()
            return
        if self.blocked_as_dupe(values | parsed):
            return
        if not is_usual_callsign(parsed["CALL"]):
            self.app.push_screen(
                CallsignWarningScreen(parsed["CALL"]),
                lambda call: self.confirm_unusual_call(values | parsed, call),
            )
            return
        self.check_warnings(values | parsed, WARNINGS)

    def confirm_unusual_call(self, values: dict, call: str | None) -> None:
        if call is None:
            self.field("CALL").focus()
            return
        # Changed in the modal, it's checked again.
        if self.blocked_as_dupe(values | {"CALL": call}):
            return
        self.check_warnings(values | {"CALL": call}, WARNINGS)

    def blocked_as_dupe(self, values: dict) -> bool:
        """Block a definite dupe of a logged entry with a modal, which
        closes back to the form (a new entry, or an edit still open) as
        typed.
        """
        logged = [entry for entry in self.logged if entry is not self.editing]
        if not is_dupe(values | {"STATION_CALLSIGN": self.app.settings.station_callsign}, logged):
            return False
        message = NEW_DUPE_MESSAGE if self.editing is None else EDIT_DUPE_MESSAGE
        self.app.push_screen(WarningScreen(message, confirm_label=DUPE_BUTTON, back_button=False))
        return True

    def check_warnings(self, values: dict, warnings: list) -> None:
        # An edited entry isn't checked against itself, e.g. as a dupe.
        logged = [entry for entry in self.logged if entry is not self.editing]
        for index, (name, check) in enumerate(warnings):
            message = check(values, logged)
            if message:
                rest = warnings[index + 1 :]

                def confirmed(ok: bool, name=name, rest=rest) -> None:
                    if ok:
                        self.check_warnings(values, rest)
                    else:
                        self.field(name).focus()

                self.app.push_screen(WarningScreen(message), confirmed)
                return
        self.submit(values)

    def submit(self, values: dict) -> None:
        # A log holds one call, the station callsign (a refused row's is it,
        # or it can't be edited).
        values = values | {"STATION_CALLSIGN": self.app.settings.station_callsign}
        if self.editing is not None:
            # An edited entry keeps its record ID.
            self.post_message(self.Edited(self.editing, values | {"UUIDv4": self.editing["UUIDv4"]}))
            return
        self.post_message(self.Submitted(values | {"UUIDv4": new_id()}))

    def entry_saved(self, values: dict) -> None:
        self.logged.append(values)
        self.clear_for_next_entry()

    def clear_for_next_entry(self) -> None:
        for name, _, _ in FIELDS:
            if name not in CARRY_FORWARD:
                self.field(name).value = DEFAULTS.get(name, "")
        self.show_report_placeholders()
        self.field("FREQ").focus()
