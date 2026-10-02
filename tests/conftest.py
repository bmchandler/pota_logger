import pytest

from pota_logger import PotaLoggerApp
from pota_logger.settings import Settings, save_settings


@pytest.fixture
def settings_path(tmp_path):
    """Settings file in a temp dir, so tests never touch the real data/.
    Not written yet, so an app started on it has no station callsign.
    """
    return tmp_path / "data" / "settings.toml"


@pytest.fixture
def app(settings_path):
    """The app with station callsign W1TST set, as entries need one."""
    save_settings(Settings(station_callsign="W1TST"), settings_path)
    return PotaLoggerApp(settings_path=settings_path)
