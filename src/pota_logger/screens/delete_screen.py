from textual.widgets import Label

from pota_logger.screens.warning_screen import WarningScreen

# The last line of the delete modal, before and after the first Enter.
ENTER_TWICE = "Enter twice to delete, or Esc to keep it."
ENTER_AGAIN = "Enter again to delete, or Esc to keep it."


class DeleteScreen(WarningScreen):
    """Confirm deleting an entry. It takes Enter (or the Delete button)
    twice, so a quick delete still works but one stray Enter doesn't.
    Dismisses with True to delete, or False (Esc, Back) to keep it.
    """

    def __init__(self, message: str) -> None:
        super().__init__(f"{message}\n{ENTER_TWICE}", confirm_label="Delete")
        self.armed = False

    def action_confirm(self) -> None:
        if self.armed:
            self.dismiss(True)
            return
        self.armed = True
        self.message = self.message.removesuffix(ENTER_TWICE) + ENTER_AGAIN
        self.query_one("#warning-message", Label).update(self.message)
