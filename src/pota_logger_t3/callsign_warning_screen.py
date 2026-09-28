from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from pota_logger_t3.ascii_text import check_ascii
from pota_logger_t3.callsigns import parse_callsign


class CallsignWarningScreen(ModalScreen[str | None]):
    """Warn about an unusual CALL, which can be corrected here. Dismisses with
    the call to log, or None to go back to the entry form.
    """

    DEFAULT_CSS = """
    CallsignWarningScreen {
        align: center middle;
    }
    CallsignWarningScreen > Vertical {
        width: 44;
        height: auto;
        padding: 1 2;
        border: thick $warning;
        background: $surface;
    }
    CallsignWarningScreen #callsign-warning-message {
        width: 100%;
        padding-bottom: 1;
    }
    CallsignWarningScreen #callsign-warning-buttons {
        height: auto;
        align-horizontal: right;
        padding-top: 1;
    }
    CallsignWarningScreen Button {
        margin-left: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Back")]

    def __init__(self, call: str) -> None:
        super().__init__()
        self.call = call

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(
                f"{self.call} is an unusual callsign.\nCorrect and/or confirm with Enter.",
                id="callsign-warning-message",
            )
            yield Input(value=self.call, id="callsign-warning-input")
            with Horizontal(id="callsign-warning-buttons"):
                yield Button("Back", id="back")
                yield Button("Confirm", id="confirm", variant="warning")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.action_confirm()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.action_confirm()
        else:
            self.action_cancel()

    def action_confirm(self) -> None:
        text = self.query_one("#callsign-warning-input", Input).value.strip()
        try:
            check_ascii("CALL", text, "W1ABC")
            call = parse_callsign(text)
        except ValueError as error:
            self.notify(str(error), severity="warning")
            return
        self.dismiss(call)

    def action_cancel(self) -> None:
        self.dismiss(None)
