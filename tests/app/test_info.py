"""The Info modal (f1): about the app, and where it keeps its files."""

from textual.widgets import Button

from pota_logger.screens.info_screen import CREDIT, REPO_URL, InfoScreen

from tests.app.helpers import ENTRY, field_values, fill


async def test_f1_opens_info_with_the_app_and_its_folders(export_app, export_folder, settings_path):
    async with export_app.run_test() as pilot:
        await pilot.press("f1")
        assert isinstance(export_app.screen, InfoScreen)
        text = export_app.screen.message.plain
        assert CREDIT in text and REPO_URL in text
        assert f"Data:    {settings_path.parent}\n" in text
        assert text.endswith(f"Exports: {export_folder}")
        assert [b.label.plain for b in export_app.screen.query(Button)] == ["Roger Roger"]


async def test_enter_or_esc_closes_info_and_keeps_the_form(app):
    async with app.run_test() as pilot:
        fill(app, ENTRY)
        typed = field_values(app)
        for key in ("enter", "escape"):
            await pilot.press("f1")
            # The app's keys don't reach a modal, so f1 doesn't stack another.
            await pilot.press("f1")
            assert [type(s) for s in app.screen_stack].count(InfoScreen) == 1
            await pilot.press(key)
            assert not isinstance(app.screen, InfoScreen)
            assert field_values(app) == typed

