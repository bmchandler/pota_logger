import tomllib
from pathlib import Path

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Footer, Static

from pota_logger_t3.dates import format_date, format_time
from pota_logger_t3.entry_form import FIELDS, EntryForm
from pota_logger_t3.freq import format_freq
from pota_logger_t3.logbook import append_entry, load_entries
from pota_logger_t3.parks import MAX_LENGTH as PARK_MAX_LENGTH
from pota_logger_t3.power import format_power
from pota_logger_t3.settings import SETTINGS_PATH, Settings, load_settings, save_settings
from pota_logger_t3.settings_screen import SettingsScreen
from pota_logger_t3.status_bar import StatusBar
from pota_logger_t3.theme import POTA_THEME


# How parsed values are shown in the log table, and their widths when
# wider than the entered text.
FORMATTERS = {
    "FREQ": format_freq,
    "PWR": format_power,
    "DATE": format_date,
    "TIME": format_time,
}
DISPLAY_LENGTHS = {
    "PARK": PARK_MAX_LENGTH,
    "PWR": len("1500W"),
    "DATE": len("2026.09.23"),
    "TIME": len("21:23"),
}


def log_row(values: dict) -> list:
    """An entry's cells in the log table, in FIELDS order."""
    shown = values | {
        name: format_value(values[name]) for name, format_value in FORMATTERS.items()
    }
    return [shown[name] for name, _, _ in FIELDS]


class PotaLoggerApp(App):
    """POTA logger TUI."""

    CSS = """
    #log-table {
        /* Full width: left to itself, it came out narrower beside the
           entry form's side margins. */
        width: 100%;
        height: 1fr;
    }
    #button-bar {
        height: auto;
        align-horizontal: right;
    }
    #button-bar > Button {
        margin-left: 1;
    }
    /* Footer shares its row with the terminal size, on the right. */
    #footer-bar {
        dock: bottom;
        height: 1;
    }
    #footer-bar > Footer {
        dock: none;
        width: 1fr;
    }
    #terminal-size {
        width: auto;
        padding: 0 1;
        color: $footer-foreground;
        background: $footer-background;
    }
    """

    # No command palette: "palette" is unfamiliar to most operators, and
    # its Theme command would switch away from the POTA theme.
    ENABLE_COMMAND_PALETTE = False

    # Redeclares Textual's built-in ctrl+q so it shows in the footer.
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("f2", "open_settings", "Settings"),
        Binding("ctrl+s", "screenshot", "Screenshot"),
    ]

    def __init__(self, settings_path: Path = SETTINGS_PATH) -> None:
        super().__init__()
        self.register_theme(POTA_THEME)
        self.theme = POTA_THEME.name
        self.settings_path = settings_path
        # Log files sit beside the settings, in data/.
        self.log_dir = settings_path.parent
        self.settings_error: str | None = None
        try:
            self.settings = load_settings(settings_path)
        except tomllib.TOMLDecodeError as error:
            self.settings = Settings()
            self.settings_error = f"Couldn't read {settings_path}: {error}"

    def compose(self) -> ComposeResult:
        yield StatusBar(station_callsign=self.settings.station_callsign)
        yield EntryForm()
        yield DataTable(id="log-table")
        with Horizontal(id="button-bar"):
            # Mouse only, so tabbing through fields can't land on them.
            for button in (
                Button("Settings", id="settings"),
                Button("Quit", id="quit", variant="warning"),
            ):
                button.can_focus = False
                yield button
        with Horizontal(id="footer-bar"):
            yield Footer()
            yield Static(id="terminal-size")

    def on_resize(self, event: events.Resize) -> None:
        self.query_one("#terminal-size", Static).update(f"{event.size.width}x{event.size.height}")

    def on_mount(self) -> None:
        table = self.query_one("#log-table", DataTable)
        # Fixed widths: DataTable doesn't redraw rows it already drew when an
        # auto-width column widens, which left the first entry truncated.
        for name, _, max_length in FIELDS:
            table.add_column(name, width=max(len(name), DISPLAY_LENGTHS.get(name, max_length)))
        self.query_one("#field-freq").focus()
        if self.settings_error:
            self.notify(self.settings_error, severity="error", timeout=30)
        entries, problems = load_entries(self.log_dir)
        self.query_one(EntryForm).logged.extend(entries)
        # Saved entries newest first; entries typed this session go above
        # them in the order typed, to check against the paper log.
        self.saved_entries = sorted(
            entries, key=lambda entry: (entry["DATE"], entry["TIME"]), reverse=True
        )
        self.session_entries: list[dict] = []
        self.show_log()
        for problem in problems:
            self.notify(f"Skipped {problem}", severity="error", timeout=30)

    def on_entry_form_submitted(self, event: EntryForm.Submitted) -> None:
        try:
            append_entry(self.log_dir, event.values, self.settings.station_callsign)
        except OSError as error:
            self.notify(
                f"Couldn't save the entry to a file: {error}", severity="error", timeout=30
            )
        self.session_entries.append(event.values)
        self.show_log()
        self.call_after_refresh(self.scroll_to_row, len(self.session_entries) - 1)

    def show_log(self) -> None:
        # DataTable can't insert a row mid-table, so it's redrawn in full.
        table = self.query_one("#log-table", DataTable)
        table.clear()
        table.add_rows(log_row(entry) for entry in self.session_entries + self.saved_entries)

    def scroll_to_row(self, index: int) -> None:
        """Scroll the log just enough to show a row, from the top."""
        table = self.query_one("#log-table", DataTable)
        rows_in_view = table.scrollable_content_region.height - table.header_height
        table.scroll_to(y=max(0, index - rows_in_view + 1), animate=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.exit()
        elif event.button.id == "settings":
            self.action_open_settings()

    def action_screenshot(self) -> None:
        # Textual's own screenshot: an SVG saved to the Downloads folder,
        # with a notification.
        self.deliver_screenshot()

    def action_open_settings(self) -> None:
        # App bindings stay live under a modal, so don't stack a second one,
        # even when another modal (its unusual-callsign warning) is on top.
        if any(isinstance(screen, SettingsScreen) for screen in self.screen_stack):
            return
        self.push_screen(SettingsScreen(self.settings), self.apply_settings)

    def apply_settings(self, settings: Settings | None) -> None:
        if settings is None:
            return
        self.settings = settings
        save_settings(settings, self.settings_path)
        self.query_one(StatusBar).set_station_callsign(settings.station_callsign)


def main() -> None:
    PotaLoggerApp().run()
