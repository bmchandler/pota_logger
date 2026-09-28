from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from pota_logger_t3.ascii_text import check_ascii
from pota_logger_t3.callsign_warning_screen import CallsignWarningScreen
from pota_logger_t3.callsigns import is_usual_callsign, parse_callsign
from pota_logger_t3.settings import Settings


class SettingsScreen(ModalScreen[Settings | None]):
    """Edit app settings. Dismisses with new Settings, or None if cancelled."""

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }
    SettingsScreen > Vertical {
        width: 44;
        height: auto;
        padding: 1 2;
        border: thick $primary;
        background: $surface;
    }
    SettingsScreen #settings-title {
        text-style: bold;
        padding-bottom: 1;
    }
    SettingsScreen #settings-buttons {
        height: auto;
        align-horizontal: right;
        padding-top: 1;
    }
    SettingsScreen Button {
        margin-left: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Settings", id="settings-title")
            yield Label("Station callsign")
            yield Input(value=self.settings.station_callsign, id="station-callsign-input")
            with Horizontal(id="settings-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", id="save", variant="primary")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.action_save()
        else:
            self.action_cancel()

    def action_save(self) -> None:
        field = self.query_one("#station-callsign-input", Input)
        # Blank is allowed: the status bar shows NOCALL until one is set.
        text = field.value.strip()
        callsign = ""
        if text:
            try:
                check_ascii("Station callsign", text, "W1ABC")
                callsign = parse_callsign(text, "Station callsign")
            except ValueError as error:
                self.notify(str(error), severity="warning")
                field.focus()
                return
            if not is_usual_callsign(callsign):
                self.app.push_screen(
                    CallsignWarningScreen(callsign, "Station callsign"), self.confirm_unusual_call
                )
                return
        self.dismiss(Settings(station_callsign=callsign))

    def confirm_unusual_call(self, call: str | None) -> None:
        if call is None:
            self.query_one("#station-callsign-input", Input).focus()
            return
        self.dismiss(Settings(station_callsign=call))

    def action_cancel(self) -> None:
        self.dismiss(None)
