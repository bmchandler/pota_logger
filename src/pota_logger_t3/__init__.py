from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static


class PotaLoggerApp(App):
    """POTA logger TUI."""

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Hello, POTA!")
        yield Footer()


def main() -> None:
    PotaLoggerApp().run()
