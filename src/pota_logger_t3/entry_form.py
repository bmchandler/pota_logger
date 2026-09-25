from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Label

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
    ("TIME", "1953", 9),
]


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

    def compose(self) -> ComposeResult:
        for name, placeholder, width in FIELDS:
            with Vertical() as column:
                column.styles.width = width
                yield Label(name)
                yield Input(placeholder=placeholder, id=f"field-{name.lower()}")
