import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

# src/pota_logger_t3/settings.py -> project root
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SETTINGS_PATH = DATA_DIR / "settings.toml"


@dataclass
class Settings:
    station_callsign: str = ""


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    """Load settings, or defaults if the file doesn't exist yet.

    Raises tomllib.TOMLDecodeError if the file has been hand-edited into
    invalid TOML.
    """
    if not path.exists():
        return Settings()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Settings(station_callsign=str(data.get("station_callsign", "")))


def save_settings(settings: Settings, path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSON string escaping is valid for TOML basic strings.
    path.write_text(
        f"station_callsign = {json.dumps(settings.station_callsign, ensure_ascii=False)}\n"
    )
