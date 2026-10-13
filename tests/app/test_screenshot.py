"""Ctrl+S: the screenshot's Save As modal."""


from textual.widgets import Input, Static

from pota_logger.screens import screenshot_screen
from pota_logger.screens.screenshot_screen import (
    NO_FILE_NAME,
    NO_FOLDER,
    SVG_NOTE,
    WRITE_FAILED,
    FolderTree,
    ScreenshotScreen,
)
from pota_logger.screens.warning_screen import WarningScreen

from tests.app.helpers import last_notification

NAME = "pota-logger_261013_181822.svg"


def path_field(app) -> Input:
    return app.screen.query_one("#screenshot-path", Input)


def problem(app) -> str:
    shown = app.screen.query_one("#screenshot-problem", Static)
    return str(shown.render()) if shown.has_class("-shown") else ""


async def open_save_as(app, pilot, monkeypatch) -> None:
    monkeypatch.setattr("pota_logger.app.screenshot_name", lambda now: NAME)
    await pilot.press("ctrl+s")


async def save_as(app, pilot, text: str) -> None:
    path_field(app).value = text
    await pilot.press("enter")


async def tree_labels(app, pilot) -> list[str]:
    tree = app.screen.query_one(FolderTree)
    while not tree.root.children:
        await pilot.pause(0.05)
    return [str(node.label) for node in tree.root.children]


async def test_ctrl_s_opens_save_as_in_home_and_enter_saves(app, home, monkeypatch):
    async with app.run_test() as pilot:
        await open_save_as(app, pilot, monkeypatch)
        assert isinstance(app.screen, ScreenshotScreen)
        assert app.focused is path_field(app)
        assert path_field(app).value == f"~/{NAME}"
        assert str(app.screen.query_one("#screenshot-note").render()) == SVG_NOTE
        await pilot.press("enter")
        assert not isinstance(app.screen, ScreenshotScreen)
        svg = (home / NAME).read_text()
        assert svg.startswith("<svg")
        assert last_notification(app) == f"Saved screenshot to ~/{NAME}"


async def test_screenshot_shows_the_app_not_the_modal(app, home, monkeypatch):
    async with app.run_test() as pilot:
        await open_save_as(app, pilot, monkeypatch)
        await pilot.press("enter")
        svg = (home / NAME).read_text()
        assert "FREQ" in svg
        assert "Save&#160;Screenshot" not in svg and "Save Screenshot" not in svg


async def test_esc_cancels_saving_nothing(app, home, monkeypatch):
    async with app.run_test() as pilot:
        await open_save_as(app, pilot, monkeypatch)
        await pilot.press("escape")
        assert not isinstance(app.screen, ScreenshotScreen)
        assert not (home / NAME).exists()


async def test_tree_lists_folders_only_dot_folders_too(app, home, monkeypatch):
    (home / ".config").mkdir()
    (home / "notes.txt").write_text("x")
    async with app.run_test() as pilot:
        await open_save_as(app, pilot, monkeypatch)
        assert await tree_labels(app, pilot) == [".config", "adif"]


async def test_picking_a_folder_fills_the_paths_folder_part(app, home, monkeypatch):
    async with app.run_test() as pilot:
        await open_save_as(app, pilot, monkeypatch)
        path_field(app).value = "~/my shot.svg"
        await tree_labels(app, pilot)
        tree = app.screen.query_one(FolderTree)
        tree.focus()
        tree.move_cursor(tree.root.children[0])
        await pilot.press("enter")
        await pilot.pause()
        assert path_field(app).value == "~/adif/my shot.svg"
        await pilot.press("tab", "enter")
        assert (home / "adif" / "my shot.svg").exists()


async def test_path_typed_without_home_or_root_saves_in_home(app, home, monkeypatch):
    async with app.run_test() as pilot:
        await open_save_as(app, pilot, monkeypatch)
        await save_as(app, pilot, "adif/a.svg")
        assert (home / "adif" / "a.svg").exists()


async def test_missing_folder_refused_until_the_path_changes(app, home, monkeypatch):
    async with app.run_test() as pilot:
        await open_save_as(app, pilot, monkeypatch)
        await save_as(app, pilot, "~/nowhere/a.svg")
        assert isinstance(app.screen, ScreenshotScreen)
        assert problem(app) == NO_FOLDER
        assert not (home / "nowhere").exists()
        await pilot.press("backspace")
        assert problem(app) == ""


async def test_path_naming_no_file_refused(app, home, monkeypatch):
    async with app.run_test() as pilot:
        await open_save_as(app, pilot, monkeypatch)
        for text in ("~/adif/", "~/adif", "  "):
            await save_as(app, pilot, text)
            assert problem(app) == NO_FILE_NAME


async def test_existing_file_overwritten_only_on_confirm(app, home, monkeypatch):
    (home / NAME).write_text("old")
    async with app.run_test() as pilot:
        await open_save_as(app, pilot, monkeypatch)
        await pilot.press("enter")
        assert isinstance(app.screen, WarningScreen)
        await pilot.press("escape")
        assert isinstance(app.screen, ScreenshotScreen)
        assert (home / NAME).read_text() == "old"
        await pilot.press("enter")
        await pilot.press("enter")
        assert not isinstance(app.screen, (ScreenshotScreen, WarningScreen))
        assert (home / NAME).read_text().startswith("<svg")


async def test_failed_write_shown_and_modal_kept(app, home, monkeypatch):
    def fail(self, *args, **kwargs):
        raise PermissionError(13, "Permission denied")

    async with app.run_test() as pilot:
        await open_save_as(app, pilot, monkeypatch)
        monkeypatch.setattr(screenshot_screen.Path, "write_text", fail)
        await pilot.press("enter")
        assert isinstance(app.screen, ScreenshotScreen)
        assert problem(app) == WRITE_FAILED


async def test_tree_shrinks_to_fit_a_short_terminal(app, home, monkeypatch):
    async with app.run_test(size=(107, 24)) as pilot:
        await open_save_as(app, pilot, monkeypatch)
        await pilot.pause()
        assert app.screen.query_one(FolderTree).size.height == 6
        assert app.screen.query_one("#save").region.bottom <= 24
