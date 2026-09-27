from datetime import date, time
from decimal import Decimal

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Label

from pota_logger_t3.callsign_warning_screen import CallsignWarningScreen
from pota_logger_t3.callsigns import is_usual_callsign, parse_callsign
from pota_logger_t3.dates import default_date, parse_date, parse_time
from pota_logger_t3.entry_warnings import future_time, voice_in_cw_range
from pota_logger_t3.freq import parse_freq
from pota_logger_t3.modes import parse_mode
from pota_logger_t3.power import parse_power
from pota_logger_t3.reports import parse_report
from pota_logger_t3.states import parse_state
from pota_logger_t3.warning_screen import WarningScreen

# (name, placeholder, longest expected value) in paper-log entry order.
FIELDS = [
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

# Fields turned from entered text into values, in entry order.
PARSERS = {
    "FREQ": parse_freq,
    "MODE": parse_mode,
    "CALL": parse_callsign,
    "ST": parse_state,
    "PWR": parse_power,
    "DATE": parse_date,
    "TIME": parse_time,
}

# Signal reports, parsed after PARSERS since their rules depend on MODE.
REPORTS = ["SNT", "RCD"]

# Fields that may be left blank.
OPTIONAL = {"ST"}

# Value each field starts with, and resets to after an entry.
DEFAULTS = {"MODE": "SSB"}

# Fields whose default is computed fresh at app start rather than fixed.
DEFAULT_FACTORIES = {"DATE": default_date}

# Fields that keep their value for the next entry.
CARRY_FORWARD = {"PWR", "DATE"}

# Checks run after the unusual-CALL warning, in order: (field Esc goes back
# to, check returning a warning message or None).
WARNINGS = [("FREQ", voice_in_cw_range), ("DATE", future_time)]


class EntryForm(Horizontal):
    """One row of labeled inputs for a single log entry."""

    DEFAULT_CSS = """
    EntryForm {
        height: auto;
        padding: 1 1 0 1;
    }
    EntryForm > Vertical {
        height: auto;
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

        FREQ is in Hz, PWR is watts, MODE is uppercase, DATE is a date,
        TIME is a time, and ST is uppercase (possibly blank); everything
        else is the trimmed text as entered.
        """

        def __init__(self, values: dict[str, str | int | Decimal | date | time]) -> None:
            super().__init__()
            self.values = values

    def compose(self) -> ComposeResult:
        for name, placeholder, max_length in FIELDS:
            with Vertical() as column:
                column.styles.width = max_length + INPUT_EXTRA_WIDTH
                yield Label(name)
                factory = DEFAULT_FACTORIES.get(name)
                yield Input(
                    value=factory() if factory else DEFAULTS.get(name, ""),
                    placeholder=placeholder,
                    id=f"field-{name.lower()}",
                )

    def field(self, name: str) -> Input:
        return self.query_one(f"#field-{name.lower()}", Input)

    def values(self) -> dict[str, str]:
        return {name: self.field(name).value.strip() for name, _, _ in FIELDS}

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        values = self.values()
        missing = [name for name, value in values.items() if not value and name not in OPTIONAL]
        if missing:
            self.notify(f"Missing: {', '.join(missing)}", severity="warning")
            self.field(missing[0]).focus()
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
            message = check(values)
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
        self.post_message(self.Submitted(values))
        self.clear_for_next_entry()

    def clear_for_next_entry(self) -> None:
        for name, _, _ in FIELDS:
            if name not in CARRY_FORWARD:
                self.field(name).value = DEFAULTS.get(name, "")
        self.field("FREQ").focus()
