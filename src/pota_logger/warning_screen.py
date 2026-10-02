from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class WarningScreen(ModalScreen[bool]):
    """Show an entry warning. Dismisses with True to save anyway, or False
    to go back to the entry form.

    With `can_go_back` False, it's a block instead: no Back button and no
    Esc, so Enter (on `confirm_label`'s button) is the only way on.
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

    def __init__(
        self,
        message: str,
        confirm_label: str = "Confirm",
        can_go_back: bool = True,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.message = message
        self.confirm_label = confirm_label
        self.can_go_back = can_go_back

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.message, id="warning-message")
            with Horizontal(id="warning-buttons"):
                # Mouse only, so Enter always confirms instead of pressing Back.
                buttons = [Button(self.confirm_label, id="confirm", variant="warning")]
                if self.can_go_back:
                    buttons.insert(0, Button("Back", id="back"))
                for button in buttons:
                    button.can_focus = False
                    yield button

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        return action != "cancel" or self.can_go_back

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.action_confirm()
        else:
            self.action_cancel()

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
