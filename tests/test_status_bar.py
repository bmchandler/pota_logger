import re

from textual.app import App, ComposeResult
from textual.widgets import Static

from pota_logger_t3.status_bar import StatusBar


class StatusBarApp(App):
    def __init__(self, station_callsign: str) -> None:
        super().__init__()
        self.station_callsign = station_callsign

    def compose(self) -> ComposeResult:
        yield StatusBar(station_callsign=self.station_callsign)


def text(app: App, widget_id: str) -> str:
    return str(app.query_one(f"#{widget_id}", Static).render())


async def test_shows_station_callsign():
    app = StatusBarApp("W1TST")
    async with app.run_test():
        assert text(app, "station-callsign") == "W1TST"


async def test_empty_callsign_shows_placeholder():
    app = StatusBarApp("")
    async with app.run_test():
        assert text(app, "station-callsign") == "NOCALL"


async def test_set_station_callsign_updates_display():
    app = StatusBarApp("")
    async with app.run_test():
        app.query_one(StatusBar).set_station_callsign("W1TST")
        assert text(app, "station-callsign") == "W1TST"
        app.query_one(StatusBar).set_station_callsign("")
        assert text(app, "station-callsign") == "NOCALL"


async def test_clock_formats():
    app = StatusBarApp("W1TST")
    async with app.run_test():
        assert re.fullmatch(r"UTC \d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}", text(app, "utc-clock"))
        assert re.fullmatch(r"\S+ \d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}", text(app, "local-clock"))


async def test_layout_left_center_right():
    app = StatusBarApp("W1TST")
    async with app.run_test(size=(90, 5)):
        callsign, local, utc = (
            app.query_one(f"#{i}").region for i in ("station-callsign", "local-clock", "utc-clock")
        )
        assert callsign.x == 0
        assert callsign.right <= local.x and local.right <= utc.x
        assert utc.right == 90


async def test_callsign_and_utc_bold_local_plain():
    app = StatusBarApp("W1TST")
    async with app.run_test():
        bold = {
            i: bool(app.query_one(f"#{i}").styles.text_style.bold)
            for i in ("station-callsign", "local-clock", "utc-clock")
        }
        assert bold == {"station-callsign": True, "local-clock": False, "utc-clock": True}
