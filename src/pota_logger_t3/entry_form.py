from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Label

from pota_logger_t3.freq import parse_freq

# (name, placeholder, width) in paper-log entry order.
# Widths are longest expected value + 1 cursor cell + 4 cells of border and padding.
FIELDS = [
    ("FREQ", "14.074.5", 15),
    ("MODE", "SSB", 8),
    ("CALL", "W1ABC", 17),
    ("PARK", "1234", 13),
    ("ST", "NJ", 7),
    ("SNT", "59", 8),
    ("RCD", "59", 8),
    ("PWR", "60W", 9),
    ("DATE", "20260925", 13),
    ("TIME", "1953", 9),
]

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

        FREQ is in Hz; everything else is the trimmed text as entered.
        """

        def __init__(self, values: dict[str, str | int]) -> None:
            super().__init__()
            self.values = values

    def compose(self) -> ComposeResult:
        for name, placeholder, width in FIELDS:
            with Vertical() as column:
                column.styles.width = width
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
        try:
            freq_hz = parse_freq(values["FREQ"])
        except ValueError as error:
            self.notify(str(error), severity="warning")
            self.field("FREQ").focus()
            return
        self.post_message(self.Submitted(values | {"FREQ": freq_hz}))
        self.clear_for_next_entry()

    def clear_for_next_entry(self) -> None:
        for name, _, _ in FIELDS:
            if name not in CARRY_FORWARD:
                self.field(name).value = DEFAULTS.get(name, "")
        self.field("FREQ").focus()
