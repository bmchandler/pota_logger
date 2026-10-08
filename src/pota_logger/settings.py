import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from pota_logger.ascii_text import check_ascii
from pota_logger.callsigns import parse_callsign

# src/pota_logger/settings.py -> project root
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SETTINGS_PATH = DATA_DIR / "settings.toml"


@dataclass
class Settings:
    station_callsign: str = ""
    # Whether loading fixed how the file wrote a value, so it's to be
    # saved again. Not a setting, so settings compare without it.
    fixed: bool = field(default=False, compare=False)


class StationCallsignError(ValueError):
    """A station callsign in the settings file that breaks CALL's rules.
    `text` is the call as written, for the operator to correct.
    """

    def __init__(self, message: str, text: str) -> None:
        super().__init__(message)
        self.text = text


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    """Load settings, or defaults if the file doesn't exist yet. The
    station callsign is checked like CALL ("" means none is set yet), with
    how it's written fixed, as in a log file: spaces around it, and its
    case (`fixed` says so). The unusual-call warning is for the settings
    modal only, as a call from the file is taken as meant.

    Raises tomllib.TOMLDecodeError if the file has been hand-edited into
    invalid TOML, or StationCallsignError (with a message for the
    operator) if its station callsign is refused.
    """
    if not path.exists():
        return Settings()
    with path.open("rb") as f:
        data = tomllib.load(f)
    # A hand edit is the only way to get anything but what's saved. Only
    # "" (or spaces) means none is set.
    text = str(data.get("station_callsign", ""))
    callsign = text.strip(" ") if text.isascii() else text
    if callsign:
        try:
            check_ascii("station_callsign", callsign)
            callsign = parse_callsign(callsign, "station_callsign")
        except ValueError as error:
            raise StationCallsignError(str(error), text) from None
    return Settings(station_callsign=callsign, fixed=callsign != text)


def save_settings(settings: Settings, path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSON string escaping is valid for TOML basic strings.
    path.write_text(
        f"station_callsign = {json.dumps(settings.station_callsign, ensure_ascii=False)}\n"
    )
