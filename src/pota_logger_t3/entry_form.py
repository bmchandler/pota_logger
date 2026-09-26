from datetime import date, time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Label

from pota_logger_t3.dates import parse_date, parse_time
from pota_logger_t3.freq import parse_freq

# (name, placeholder, longest expected value) in paper-log entry order.
FIELDS = [
    ("FREQ", "14.074.5", 10),  # 29.700.000
    ("MODE", "SSB", 3),
    ("CALL", "W1ABC", 12),  # VE3/W1ABC/P
    ("PARK", "1234", 8),  # US-10123
    ("ST", "NJ", 2),
    ("SNT", "59", 3),
    ("RCD", "59", 3),
    ("PWR", "60W", 4),  # 100W
    ("DATE", "260925", 6),
    ("TIME", "1953", 4),
]

# Input border and padding (4) plus a cell for the cursor.
INPUT_EXTRA_WIDTH = 5

# Fields turned from entered text into values, in entry order.
PARSERS = {"FREQ": parse_freq, "DATE": parse_date, "TIME": parse_time}

# Value each field starts with, and resets to after an entry.
DEFAULTS = {"MODE": "SSB"}

# Fields that keep their value for the next entry.
CARRY_FORWARD = {"PWR", "DATE"}


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

        FREQ is in Hz, DATE is a date, and TIME is a time; everything else
        is the trimmed text as entered.
        """

        def __init__(self, values: dict[str, str | int | date | time]) -> None:
            super().__init__()
            self.values = values

    def compose(self) -> ComposeResult:
        for name, placeholder, max_length in FIELDS:
            with Vertical() as column:
                column.styles.width = max_length + INPUT_EXTRA_WIDTH
                yield Label(name)
                yield Input(
                    value=DEFAULTS.get(name, ""),
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
        missing = [name for name, value in values.items() if not value]
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
        self.post_message(self.Submitted(values | parsed))
        self.clear_for_next_entry()

    def clear_for_next_entry(self) -> None:
        for name, _, _ in FIELDS:
            if name not in CARRY_FORWARD:
                self.field(name).value = DEFAULTS.get(name, "")
        self.field("FREQ").focus()
