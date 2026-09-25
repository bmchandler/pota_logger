from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer

from pota_logger_t3.entry_form import FIELDS, EntryForm
from pota_logger_t3.status_bar import StatusBar


class PotaLoggerApp(App):
    """POTA logger TUI."""

    CSS = """
    #log-table {
        height: 1fr;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield StatusBar(station_callsign="NOCALL")
        yield EntryForm()
        yield DataTable(id="log-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#log-table", DataTable)
        table.add_columns(*(name for name, _, _ in FIELDS))
        self.query_one("#field-freq").focus()


def main() -> None:
    PotaLoggerApp().run()
