import tomllib

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Footer

from pota_logger_t3.entry_form import FIELDS, EntryForm
from pota_logger_t3.settings import SETTINGS_PATH, Settings, load_settings, save_settings
from pota_logger_t3.settings_screen import SettingsScreen
from pota_logger_t3.status_bar import StatusBar


class PotaLoggerApp(App):
    """POTA logger TUI."""

    CSS = """
    #log-table {
        height: 1fr;
    }
    #button-bar {
        height: auto;
        align-horizontal: right;
    }
    #button-bar > Button {
        margin-left: 1;
    }
    """

    # Redeclares Textual's built-in ctrl+q so it shows in the footer.
    BINDINGS = [Binding("ctrl+q", "quit", "Quit", priority=True)]

    def __init__(self) -> None:
        super().__init__()
        self.settings_error: str | None = None
        try:
            self.settings = load_settings()
        except tomllib.TOMLDecodeError as error:
            self.settings = Settings()
            self.settings_error = f"Couldn't read {SETTINGS_PATH}: {error}"

    def compose(self) -> ComposeResult:
        yield StatusBar(station_callsign=self.settings.station_callsign)
        yield EntryForm()
        yield DataTable(id="log-table")
        with Horizontal(id="button-bar"):
            # Mouse only, so tabbing through fields can't land on them.
            for button in (
                Button("Settings", id="settings"),
                Button("Quit", id="quit", variant="error"),
            ):
                button.can_focus = False
                yield button
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#log-table", DataTable)
        table.add_columns(*(name for name, _, _ in FIELDS))
        self.query_one("#field-freq").focus()
        if self.settings_error:
            self.notify(self.settings_error, severity="error", timeout=30)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.exit()
        elif event.button.id == "settings":
            self.push_screen(SettingsScreen(self.settings), self.apply_settings)

    def apply_settings(self, settings: Settings | None) -> None:
        if settings is None:
            return
        self.settings = settings
        save_settings(settings)
        self.query_one(StatusBar).set_station_callsign(settings.station_callsign)


def main() -> None:
    PotaLoggerApp().run()
