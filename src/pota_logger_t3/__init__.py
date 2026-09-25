from textual.app import App, ComposeResult
from textual.widgets import Footer, Static

from pota_logger_t3.status_bar import StatusBar


class PotaLoggerApp(App):
    """POTA logger TUI."""

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield StatusBar(station_callsign="NOCALL")
        yield Static("Hello, POTA!")
        yield Footer()


def main() -> None:
    PotaLoggerApp().run()
