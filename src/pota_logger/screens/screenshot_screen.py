from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, Static

from pota_logger.screens.warning_screen import WarningScreen
from pota_logger.settings import home_relative

# The modal's wording. SVG_NOTE as dictated (2026-10-13).
# The tree's most rows, and the rows the rest of the modal takes (a problem
# shown included), so the tree shrinks in a short terminal.
TREE_ROWS = 12
OTHER_ROWS = 18

SVG_NOTE = "SVG images may appear to have errors when viewed on some systems."
NO_FILE_NAME = "Save error: No file name."
NO_FOLDER = "Save error: Folder not found."
WRITE_FAILED = "Save error: Couldn't write the file."


def screenshot_name(now: datetime) -> str:
    return f"pota-logger_{now:%y%m%d_%H%M%S}.svg"


def typed_path(text: str) -> Path:
    """The path typed, `~` expanded; one not starting at the root is in
    the home folder (the folder the app runs from means nothing here).
    """
    path = Path(text).expanduser()
    return path if path.is_absolute() else Path.home() / path


class FolderTree(DirectoryTree):
    """A DirectoryTree of folders only (dot-folders too)."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if self._safe_is_dir(path)]


class ScreenshotScreen(ModalScreen[None]):
    """Save a screenshot (`svg`, taken before this opened, so it shows the
    app, not this) where the operator picks: a folder tree from the home
    folder, whose selected folder fills the path's folder part, above the
    path, filled in with `~/` and a name from the date and time. Esc
    cancels. A file already there is overwritten only after a confirm;
    a missing folder, a path naming no file, or a failed write shows why
    below the path. Dismisses after saving, with a notification.
    """

    DEFAULT_CSS = """
    ScreenshotScreen {
        align: center middle;
    }
    ScreenshotScreen > Vertical {
        width: 74;
        height: auto;
        max-height: 100%;
        padding: 1 2;
        border: thick $primary;
        background: $surface;
    }
    ScreenshotScreen #screenshot-title {
        text-style: bold;
        padding-bottom: 1;
    }
    ScreenshotScreen FolderTree {
        height: 12;
        margin-bottom: 1;
    }
    ScreenshotScreen #screenshot-problem {
        display: none;
        height: auto;
        color: $error;
    }
    ScreenshotScreen #screenshot-problem.-shown {
        display: block;
    }
    ScreenshotScreen #screenshot-note {
        padding-top: 1;
    }
    ScreenshotScreen #screenshot-buttons {
        height: auto;
        align-horizontal: right;
        padding-top: 1;
    }
    ScreenshotScreen Button {
        margin-left: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    AUTO_FOCUS = "#screenshot-path"

    def __init__(self, svg: str, name: str) -> None:
        super().__init__()
        self.svg = svg
        self.file_name = name

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Save Screenshot", id="screenshot-title")
            yield FolderTree(Path.home())
            yield Label("Save as")
            yield Input(value=f"~/{self.file_name}", id="screenshot-path")
            yield Static(id="screenshot-problem")
            yield Label(SVG_NOTE, id="screenshot-note")
            with Horizontal(id="screenshot-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", id="save", variant="primary")

    def on_resize(self, event: events.Resize) -> None:
        rows = max(3, min(TREE_ROWS, event.size.height - OTHER_ROWS))
        self.query_one(FolderTree).styles.height = rows

    def path_field(self) -> Input:
        return self.query_one("#screenshot-path", Input)

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        name = Path(self.path_field().value.strip()).name or self.file_name
        self.path_field().value = home_relative(event.path / name)

    def on_input_changed(self, event: Input.Changed) -> None:
        self.show_problem("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.action_save()
        else:
            self.action_cancel()

    def show_problem(self, problem: str) -> None:
        shown = self.query_one("#screenshot-problem", Static)
        shown.update(Text(problem))
        shown.set_class(bool(problem), "-shown")

    def action_save(self) -> None:
        text = self.path_field().value.strip()
        path = typed_path(text)
        if not text or text.endswith("/") or path.is_dir():
            self.show_problem(NO_FILE_NAME)
        elif not path.parent.is_dir():
            self.show_problem(NO_FOLDER)
        elif path.exists():
            message = f"{path.name} is already there.\nEsc to rename, or overwrite with Enter."
            self.app.push_screen(
                WarningScreen(message, confirm_label="Overwrite"),
                lambda overwrite: self.write(path) if overwrite else None,
            )
        else:
            self.write(path)

    def write(self, path: Path) -> None:
        try:
            path.write_text(self.svg, encoding="utf-8")
        except OSError:
            self.show_problem(WRITE_FAILED)
            return
        self.dismiss()
        self.app.notify(f"Saved screenshot to {home_relative(path)}", title="Screenshot", markup=False)

    def action_cancel(self) -> None:
        self.dismiss()
