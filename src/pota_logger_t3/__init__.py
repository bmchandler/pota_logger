from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Footer

from pota_logger_t3.entry_form import FIELDS, EntryForm
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
    """

    # Redeclares Textual's built-in ctrl+q so it shows in the footer.
    BINDINGS = [Binding("ctrl+q", "quit", "Quit", priority=True)]

    def compose(self) -> ComposeResult:
        yield StatusBar(station_callsign="NOCALL")
        yield EntryForm()
        yield DataTable(id="log-table")
        with Horizontal(id="button-bar"):
            quit_button = Button("Quit", id="quit", variant="error")
            # Mouse only, so tabbing through fields can't land on it.
            quit_button.can_focus = False
            yield quit_button
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#log-table", DataTable)
        table.add_columns(*(name for name, _, _ in FIELDS))
        self.query_one("#field-freq").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.exit()


def main() -> None:
    PotaLoggerApp().run()
