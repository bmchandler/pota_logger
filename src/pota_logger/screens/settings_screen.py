from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from pota_logger.fields.ascii_text import check_ascii
from pota_logger.screens.callsign_warning_screen import CallsignWarningScreen
from pota_logger.fields.callsigns import is_usual_callsign, parse_callsign
from pota_logger.fields.dates import format_date
from pota_logger.parks_list import ParksCopy, copy_date
from pota_logger.settings import (
    EDIT_COMMENT_POTA_INFO,
    NEW_COMMENT_POTA_INFO,
    SWITCHES,
    Settings,
    folder_path,
)

# The ADIF export folder's label, as chosen (2026-10-09).
ADIF_EXPORT_FOLDER = "ADIF export folder"

# The parks list's refresh, as dictated (2026-10-09), and its copy's date
# beside it.
CHECK_FOR_UPDATED = "Check for Updated"
PARKS_LIST = "POTA parks list: {date}"


def parks_list_text(copy: ParksCopy | None) -> str:
    """The parks list's row: the copy's date, or `none` without a sound
    copy (or `date unknown`, if the server gave none).
    """
    if copy is None:
        return PARKS_LIST.format(date="none")
    day = copy_date(copy)
    return PARKS_LIST.format(date=format_date(day) if day else "date unknown")


# Where each text field's problem shows, below it.
PROBLEM_IDS = {"station-callsign-input": "settings-problem", "folder-input": "folder-problem"}

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
    files, edit settings.toml). The ADIF export folder shows always. The
    parks list's row (`parks_copy`, the saved copy) shows after setup,
    as first start offers the download on its own once the call is saved.
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
    /* Why the call or the folder wasn't saved, below it, only after a
       Save that couldn't; gone once it's edited. */
    SettingsScreen .settings-problem {
        display: none;
        height: auto;
        color: $error;
        padding: 0 1;
    }
    SettingsScreen .settings-problem.-shown {
        display: block;
    }
    SettingsScreen #folder-label {
        padding-top: 1;
    }
    /* No blank row above it, so Settings fits a 24-row terminal. */
    SettingsScreen #parks-row {
        height: auto;
    }
    SettingsScreen #parks-list {
        width: 1fr;
        padding-top: 1;
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

    def __init__(
        self,
        settings: Settings,
        with_callsign: bool = True,
        parks_copy: ParksCopy | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.with_callsign = with_callsign
        self.parks_copy = parks_copy

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Settings", id="settings-title")
            if self.with_callsign:
                yield Label("Station callsign")
                yield Input(value=self.settings.station_callsign, id="station-callsign-input")
                yield Static(id="settings-problem", classes="settings-problem")
            for key in SWITCHES:
                yield SettingCheckbox(SWITCH_LABELS[key], getattr(self.settings, key), id=key)
            yield Label(ADIF_EXPORT_FOLDER, id="folder-label")
            yield Input(value=self.settings.adif_export_folder, id="folder-input")
            yield Static(id="folder-problem", classes="settings-problem")
            if not self.with_callsign:
                with Horizontal(id="parks-row"):
                    yield Label(parks_list_text(self.parks_copy), id="parks-list")
                    yield Button(CHECK_FOR_UPDATED, id="check-parks")
            with Horizontal(id="settings-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", id="save", variant="primary")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_save()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.show_problem(PROBLEM_IDS[event.input.id], "")

    def show_problem(self, problem_id: str, problem: str) -> None:
        shown = self.query_one(f"#{problem_id}", Static)
        shown.update(Text(problem))
        shown.set_class(bool(problem), "-shown")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.action_save()
        elif event.button.id == "check-parks":
            # The app's, as it carries on if Settings closes meanwhile.
            self.app.check_parks_list()
        else:
            self.action_cancel()

    def show_parks_copy(self, copy: ParksCopy) -> None:
        """Show a copy just downloaded."""
        self.query_one("#parks-list", Label).update(parks_list_text(copy))

    def saved(self, callsign: str) -> Settings:
        switches = {key: self.query_one(f"#{key}", SettingCheckbox).value for key in SWITCHES}
        folder = self.query_one("#folder-input", Input).value.strip()
        return Settings(station_callsign=callsign, **switches, adif_export_folder=folder)

    def folder_refused(self) -> bool:
        """Refuse an ADIF export folder that isn't plain ASCII, or that
        isn't an existing folder (none is made), showing why below it.
        """
        field = self.query_one("#folder-input", Input)
        text = field.value.strip()
        try:
            check_ascii(ADIF_EXPORT_FOLDER, text, "~/Downloads")
            if text and not folder_path(text).is_dir():
                missing = "isn't a folder" if folder_path(text).exists() else "doesn't exist"
                raise ValueError(f"{ADIF_EXPORT_FOLDER} {text!r} {missing}.")
        except ValueError as error:
            self.show_problem("folder-problem", str(error))
            field.focus()
            return True
        return False

    def action_save(self) -> None:
        if not self.with_callsign:
            if not self.folder_refused():
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
                self.show_problem("settings-problem", str(error))
                field.focus()
                return
        if self.folder_refused():
            return
        if callsign and not is_usual_callsign(callsign):
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
