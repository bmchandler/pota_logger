"""Fixtures for the app tests, beside tests/conftest.py's."""

import pytest

from pota_logger.app import PotaLoggerApp
from pota_logger.settings import Settings, save_settings

from tests.app.helpers import save_parks_list


@pytest.fixture
def pota_app(settings_path):
    """The app with both POTA info settings on."""
    save_settings(
        Settings("W1TST", new_comment_pota_info=True, edit_comment_pota_info=True), settings_path
    )
    return PotaLoggerApp(settings_path=settings_path)


@pytest.fixture
def no_call_app(settings_path):
    """The app at first start, with no station callsign: Settings, with
    the call to set, opens with Enter from the block.
    """
    return PotaLoggerApp(settings_path=settings_path)


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A home folder in the temp dir, with ~/adif in it, for folders typed
    with ~ (which Settings saves only if they exist).
    """
    home = tmp_path / "home"
    (home / "adif").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def export_folder(settings_path):
    """An existing folder for exports, beside data/ in the temp dir."""
    folder = settings_path.parent.parent / "adif"
    folder.mkdir(parents=True)
    return folder


@pytest.fixture
def export_app(settings_path, export_folder):
    """The app with W1TST and an ADIF export folder set."""
    save_settings(Settings("W1TST", adif_export_folder=str(export_folder)), settings_path)
    return PotaLoggerApp(settings_path=settings_path)


@pytest.fixture
def parks_app(app, settings_path, pota):
    """The app with POTA's parks list saved (APP_LIST)."""
    save_parks_list(settings_path, pota)
    app.parks_url = pota.url
    return app
