import pytest

from pota_logger_t3 import PotaLoggerApp


@pytest.fixture
def settings_path(tmp_path):
    """Settings file in a temp dir, so tests never touch the real data/."""
    return tmp_path / "data" / "settings.toml"


@pytest.fixture
def app(settings_path):
    return PotaLoggerApp(settings_path=settings_path)
