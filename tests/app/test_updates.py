"""The check for a newer release at start, Updates in Settings, and the
upgrade on Quit.
"""

from textual.widgets import Select

from pota_logger import app as app_module
from pota_logger.app import PotaLoggerApp
from pota_logger.settings import Settings, load_settings, save_settings
from pota_logger.updates import InstallSource

from tests.app.helpers import last_notification

# Newer than any version the app will have.
FUTURE = "2999.1.1"


def updates_app(settings_path, url: str, updates: str) -> PotaLoggerApp:
    save_settings(Settings(station_callsign="W1TST", updates=updates), settings_path)
    app = PotaLoggerApp(settings_path=settings_path)
    app.install_source = InstallSource(url, None)
    return app


async def wait_for_newer_version(app, pilot) -> None:
    for _ in range(200):
        if app.newer_version is not None:
            return
        await pilot.pause(0.02)
    raise AssertionError("no newer version found")


async def test_newer_release_is_a_toast_with_the_upgrade_command(settings_path, releases):
    app = updates_app(settings_path, releases("2026.10.11", FUTURE), "notify")
    async with app.run_test() as pilot:
        await wait_for_newer_version(app, pilot)
        assert app.newer_version == FUTURE
        assert last_notification(app) == (
            f"Version {FUTURE} is available.\nQuit, then run: uv tool upgrade pota-logger"
        )
        assert not app.upgrade_on_quit()


async def test_automatic_on_quit_upgrades_without_a_toast(settings_path, releases, monkeypatch):
    monkeypatch.setattr(app_module, "can_upgrade", lambda: True)
    app = updates_app(settings_path, releases(FUTURE), "on_quit")
    async with app.run_test() as pilot:
        await wait_for_newer_version(app, pilot)
        assert not app._notifications
        assert app.upgrade_on_quit()


async def test_automatic_on_quit_without_uv_is_a_toast(settings_path, releases, monkeypatch):
    monkeypatch.setattr(app_module, "can_upgrade", lambda: False)
    app = updates_app(settings_path, releases(FUTURE), "on_quit")
    async with app.run_test() as pilot:
        await wait_for_newer_version(app, pilot)
        assert last_notification(app).startswith(f"Version {FUTURE} is available.")
        assert not app.upgrade_on_quit()


async def test_no_newer_release_no_toast_nor_upgrade(settings_path, releases, monkeypatch):
    checked = []

    def check(source):
        checked.append(source)
        return None

    monkeypatch.setattr(app_module, "check_for_release", check)
    app = updates_app(settings_path, releases(), "on_quit")
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        assert checked == [app.install_source]
        assert not app._notifications
        assert not app.upgrade_on_quit()


async def test_no_notification_doesnt_check(settings_path, releases, monkeypatch):
    checked = []
    monkeypatch.setattr(app_module, "check_for_release", checked.append)
    app = updates_app(settings_path, releases(FUTURE), "none")
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        assert checked == []


async def test_a_clone_isnt_checked(app, monkeypatch):
    checked = []
    monkeypatch.setattr(app_module, "check_for_release", checked.append)
    # Run from a clone, the app isn't an install from git.
    assert app.install_source is None
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        assert checked == []


async def test_automatic_on_quit_follows_settings_saved_since(settings_path, releases, monkeypatch):
    monkeypatch.setattr(app_module, "can_upgrade", lambda: True)
    app = updates_app(settings_path, releases(FUTURE), "notify")
    async with app.run_test() as pilot:
        await wait_for_newer_version(app, pilot)
        assert not app.upgrade_on_quit()
        await pilot.press("f2")
        app.screen.query_one("#updates", Select).value = "on_quit"
        await pilot.click("#save")
        assert app.upgrade_on_quit()


async def test_updates_shows_as_saved_and_is_picked_with_the_keyboard(app, settings_path):
    async with app.run_test() as pilot:
        await pilot.press("f2")
        select = app.screen.query_one("#updates", Select)
        assert select.value == "notify"
        assert [str(label) for label, _ in select._options] == [
            "No notification",
            "Notify",
            "Automatic on Quit",
        ]
        # First in Settings; Enter opens it, Down and Enter pick.
        assert app.focused is select
        await pilot.press("enter", "down", "enter")
        assert select.value == "on_quit"
        await pilot.click("#save")
    assert load_settings(settings_path).updates == "on_quit"


async def test_updates_at_first_start(no_call_app, settings_path):
    async with no_call_app.run_test() as pilot:
        await pilot.press("enter", *"w1tst")
        no_call_app.screen.query_one("#updates", Select).value = "none"
        await pilot.click("#save")
    assert load_settings(settings_path).updates == "none"


class FakeApp:
    def __init__(self, upgrade: bool) -> None:
        self.upgrade = upgrade

    def run(self):
        pass

    def upgrade_on_quit(self):
        return self.upgrade


def test_main_upgrades_after_the_app_closes(tmp_path, monkeypatch):
    upgrades = []
    monkeypatch.setattr(app_module, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(app_module, "upgrade", lambda: upgrades.append(True))
    monkeypatch.setattr(app_module, "PotaLoggerApp", lambda: FakeApp(False))
    app_module.main()
    assert upgrades == []
    monkeypatch.setattr(app_module, "PotaLoggerApp", lambda: FakeApp(True))
    app_module.main()
    assert upgrades == [True]
