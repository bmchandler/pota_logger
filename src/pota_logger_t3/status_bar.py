from datetime import UTC, datetime

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

CLOCK_FORMAT = "%Y.%m.%d %H:%M:%S"


class StatusBar(Horizontal):
    """Top bar: station callsign on the left, local and UTC clocks on the right."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $panel;
    }
    StatusBar > Static {
        width: 1fr;
        padding: 0 1;
    }
    #station-callsign {
        text-style: bold;
    }
    #local-clock {
        text-align: center;
    }
    #utc-clock {
        text-align: right;
    }
    """

    def __init__(self, station_callsign: str) -> None:
        super().__init__()
        self.station_callsign = station_callsign

    def compose(self) -> ComposeResult:
        yield Static(self.station_callsign or "NOCALL", id="station-callsign")
        yield Static(id="local-clock")
        yield Static(id="utc-clock")

    def set_station_callsign(self, station_callsign: str) -> None:
        self.station_callsign = station_callsign
        self.query_one("#station-callsign", Static).update(station_callsign or "NOCALL")

    def on_mount(self) -> None:
        self.update_clocks()
        self.set_interval(1, self.update_clocks)

    def update_clocks(self) -> None:
        now = datetime.now(UTC)
        local = now.astimezone()
        self.query_one("#local-clock", Static).update(
            f"{local.strftime('%Z')} {local.strftime(CLOCK_FORMAT)}"
        )
        self.query_one("#utc-clock", Static).update(f"UTC {now.strftime(CLOCK_FORMAT)}")
