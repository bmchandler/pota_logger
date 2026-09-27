from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class WarningScreen(ModalScreen[bool]):
    """Show an entry warning. Dismisses with True to save anyway, or False
    to go back to the entry form.
    """

    DEFAULT_CSS = """
    WarningScreen {
        align: center middle;
    }
    WarningScreen > Vertical {
        width: 48;
        height: auto;
        padding: 1 2;
        border: thick $warning;
        background: $surface;
    }
    WarningScreen #warning-message {
        width: 100%;
    }
    WarningScreen #warning-buttons {
        height: auto;
        align-horizontal: right;
        padding-top: 1;
    }
    WarningScreen Button {
        margin-left: 1;
    }
    """

    BINDINGS = [("enter", "confirm", "Confirm"), ("escape", "cancel", "Back")]

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.message, id="warning-message")
            with Horizontal(id="warning-buttons"):
                # Mouse only, so Enter always confirms instead of pressing Back.
                for button in (
                    Button("Back", id="back"),
                    Button("Confirm", id="confirm", variant="warning"),
                ):
                    button.can_focus = False
                    yield button

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.action_confirm()
        else:
            self.action_cancel()

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
