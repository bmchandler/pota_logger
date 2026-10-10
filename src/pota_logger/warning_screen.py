from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class WarningScreen(ModalScreen[bool]):
    """Show an entry warning. Dismisses with True to save anyway, or False
    to go back to the entry form.

    With `can_go_back` False, it's a block instead: no Back button and no
    Esc, so Enter (on `confirm_label`'s button) is the only way on. With
    `back_button` False, there's no Back button, but Esc still goes back:
    a notice with one button, where either key closes it. `back_label`
    names the Back button.

    With two buttons, Tab moves between them (Back first); none has focus
    at first, so Enter confirms until Tab picks one, and then presses it.
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

    # Nothing focused on opening, so Enter confirms (stock focuses the
    # first button, Back). "", as None means the app's setting.
    AUTO_FOCUS = ""

    def __init__(
        self,
        message: str | Content,
        confirm_label: str = "Confirm",
        can_go_back: bool = True,
        back_button: bool = True,
        id: str | None = None,
        back_label: str = "Back",
    ) -> None:
        super().__init__(id=id)
        self.message = message
        self.confirm_label = confirm_label
        self.back_label = back_label
        self.can_go_back = can_go_back
        self.back_button = back_button

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.message, id="warning-message")
            with Horizontal(id="warning-buttons"):
                buttons = [Button(self.confirm_label, id="confirm", variant="warning")]
                if self.can_go_back and self.back_button:
                    buttons.insert(0, Button(self.back_label, id="back"))
                for button in buttons:
                    # A lone button is mouse only: Enter and Esc do it all.
                    button.can_focus = len(buttons) > 1
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
