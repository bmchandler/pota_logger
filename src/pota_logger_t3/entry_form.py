from datetime import date, time
from decimal import Decimal

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Label

from pota_logger_t3.ascii_text import check_ascii
from pota_logger_t3.callsign_warning_screen import CallsignWarningScreen
from pota_logger_t3.callsigns import is_usual_callsign, parse_callsign
from pota_logger_t3.dates import default_date, parse_date, parse_time
from pota_logger_t3.entry_warnings import (
    future_time,
    possible_dupe,
    state_on_non_us_park,
    voice_outside_range,
)
from pota_logger_t3.freq import parse_freq
from pota_logger_t3.modes import parse_mode
from pota_logger_t3.parks import MAX_LENGTH as PARK_MAX_LENGTH
from pota_logger_t3.parks import parse_park
from pota_logger_t3.power import parse_power
from pota_logger_t3.reports import THREE_DIGIT_MODE, parse_report
from pota_logger_t3.sidebands import check_sideband
from pota_logger_t3.states import parse_state
from pota_logger_t3.warning_screen import WarningScreen

# (name, placeholder, longest expected value) in paper-log entry order, for
# the fields in the top row of the form.
ROW_FIELDS = [
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

# Input border and padding (4) plus a cell for the cursor.
INPUT_EXTRA_WIDTH = 5

# COMMENT sits below the row, as wide as it, and holds what fits there.
ROW_WIDTH = sum(max_length + INPUT_EXTRA_WIDTH for _, _, max_length in ROW_FIELDS)
COMMENT_LENGTH = ROW_WIDTH - INPUT_EXTRA_WIDTH

# Every field, in entry order.
FIELDS = ROW_FIELDS + [("COMMENT", "", COMMENT_LENGTH)]

# Most fields take any length, so their rules can explain what's wrong.
# COMMENT takes what fits in view; PARK scrolls to ADIF's longest
# reference, which is rare enough not to widen the row for.
INPUT_LIMITS = {"PARK": PARK_MAX_LENGTH, "COMMENT": COMMENT_LENGTH}

# Fields turned from entered text into values, in entry order.
PARSERS = {
    "FREQ": parse_freq,
    "MODE": parse_mode,
    "CALL": parse_callsign,
    "PARK": parse_park,
    "ST": parse_state,
    "PWR": parse_power,
    "DATE": parse_date,
    "TIME": parse_time,
}

# Signal reports, parsed after PARSERS since their rules depend on MODE.
REPORTS = ["SNT", "RCD"]

# SNT and RCD placeholder while MODE is CW, as a hint; ROW_FIELDS has the
# usual one.
CW_REPORT_PLACEHOLDER = "599"

# Fields that may be left blank.
OPTIONAL = {"ST", "COMMENT"}

# Value each field starts with, and resets to after an entry.
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
CARRY_FORWARD = {"PWR", "DATE"}

# Checks run after the unusual-CALL warning, in order: (field Esc goes back
# to, check in entry_warnings.py).
WARNINGS = [
    ("CALL", possible_dupe),
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
    EntryForm > Vertical {
        margin-bottom: 1;
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
        entered.
        """

        def __init__(self, values: dict[str, str | int | Decimal | date | time]) -> None:
            super().__init__()
            self.values = values

    def __init__(self) -> None:
        super().__init__()
        # Entries loaded at start and saved since, for the possible-dupe
        # warning.
        self.logged: list[dict] = []

    def watch_show_horizontal_scrollbar(self, show: bool) -> None:
        self.set_class(show, "-scrolling")

    def compose(self) -> ComposeResult:
        with Horizontal():
            for name, placeholder, max_length in ROW_FIELDS:
                yield labeled_input(name, placeholder, max_length)
        yield labeled_input("COMMENT", "", COMMENT_LENGTH)

    def field(self, name: str) -> Input:
        return self.query_one(f"#field-{name.lower()}", Input)

    def values(self) -> dict[str, str]:
        return {name: self.field(name).value.strip() for name, _, _ in FIELDS}

    def on_input_blurred(self, event: Input.Blurred) -> None:
        if event.input.id == "field-mode":
            self.show_report_placeholders()

    def show_report_placeholders(self) -> None:
        """Hint 599 in SNT and RCD while MODE is CW, 59 otherwise."""
        on_cw = self.field("MODE").value.strip().upper() == THREE_DIGIT_MODE
        for name, placeholder, _ in ROW_FIELDS:
            if name in REPORTS:
                self.field(name).placeholder = CW_REPORT_PLACEHOLDER if on_cw else placeholder

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
        self.check_warnings(values | {"CALL": call}, WARNINGS)

    def check_warnings(self, values: dict, warnings: list) -> None:
        for index, (name, check) in enumerate(warnings):
            message = check(values, self.logged)
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
        self.logged.append(values)
        self.post_message(self.Submitted(values))
        self.clear_for_next_entry()

    def clear_for_next_entry(self) -> None:
        for name, _, _ in FIELDS:
            if name not in CARRY_FORWARD:
                self.field(name).value = DEFAULTS.get(name, "")
        self.show_report_placeholders()
        self.field("FREQ").focus()
