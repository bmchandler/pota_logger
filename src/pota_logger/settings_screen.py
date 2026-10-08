from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from pota_logger.ascii_text import check_ascii
from pota_logger.callsign_warning_screen import CallsignWarningScreen
from pota_logger.callsigns import is_usual_callsign, parse_callsign
from pota_logger.settings import (
    EDIT_COMMENT_POTA_INFO,
    NEW_COMMENT_POTA_INFO,
    SWITCHES,
    Settings,
)

# Each on/off setting's label, by its key.
SWITCH_LABELS = {
    "new_comment_pota_info": NEW_COMMENT_POTA_INFO,
    "edit_comment_pota_info": EDIT_COMMENT_POTA_INFO,
}


class SettingCheckbox(Checkbox):
    """A checkbox whose X shows only when it's checked. Stock, a dimmed X
    shows when unchecked too, which reads as checked.
    """

    @property
    def BUTTON_INNER(self) -> str:  # noqa: N802 (Textual's name)
        return "X" if self.value else " "


class SettingsScreen(ModalScreen[Settings | None]):
    """Edit app settings. Dismisses with new Settings, or None if cancelled.
    The station callsign shows only while none is set (`with_callsign`):
    a log holds one call, so changing it means a new log (archive the
    files, edit settings.toml).
    """

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }
    SettingsScreen > Vertical {
        width: 56;
        height: auto;
        padding: 1 2;
        border: thick $primary;
        background: $surface;
    }
    SettingsScreen #settings-title {
        text-style: bold;
        padding-bottom: 1;
    }
    /* Why the call wasn't saved, below it, only after a Save that
       couldn't; gone once it's edited. */
    SettingsScreen #settings-problem {
        display: none;
        height: auto;
        color: $error;
        padding: 0 1;
    }
    SettingsScreen #settings-problem.-shown {
        display: block;
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

    def __init__(self, settings: Settings, with_callsign: bool = True) -> None:
        super().__init__()
        self.settings = settings
        self.with_callsign = with_callsign

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Settings", id="settings-title")
            if self.with_callsign:
                yield Label("Station callsign")
                yield Input(value=self.settings.station_callsign, id="station-callsign-input")
                yield Static(id="settings-problem")
            for key in SWITCHES:
                yield SettingCheckbox(SWITCH_LABELS[key], getattr(self.settings, key), id=key)
            with Horizontal(id="settings-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", id="save", variant="primary")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_save()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.show_problem("")

    def show_problem(self, problem: str) -> None:
        shown = self.query_one("#settings-problem", Static)
        shown.update(Text(problem))
        shown.set_class(bool(problem), "-shown")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.action_save()
        else:
            self.action_cancel()

    def saved(self, callsign: str) -> Settings:
        switches = {key: self.query_one(f"#{key}", SettingCheckbox).value for key in SWITCHES}
        return Settings(station_callsign=callsign, **switches)

    def action_save(self) -> None:
        if not self.with_callsign:
            self.dismiss(self.saved(self.settings.station_callsign))
            return
        field = self.query_one("#station-callsign-input", Input)
        # Blank is saved as is; the app then asks for a call again.
        text = field.value.strip()
        callsign = ""
        if text:
            try:
                check_ascii("Station callsign", text, "W1ABC")
                callsign = parse_callsign(text, "Station callsign")
            except ValueError as error:
                self.show_problem(str(error))
                field.focus()
                return
            if not is_usual_callsign(callsign):
                self.app.push_screen(
                    CallsignWarningScreen(callsign, "Station callsign"), self.confirm_unusual_call
                )
                return
        self.dismiss(self.saved(callsign))

    def confirm_unusual_call(self, call: str | None) -> None:
        if call is None:
            self.query_one("#station-callsign-input", Input).focus()
            return
        self.dismiss(self.saved(call))

    def action_cancel(self) -> None:
        self.dismiss(None)
