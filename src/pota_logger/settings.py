import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

from pota_logger.ascii_text import check_ascii, check_trimmed
from pota_logger.callsigns import parse_callsign

# src/pota_logger/settings.py -> project root
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SETTINGS_PATH = DATA_DIR / "settings.toml"


@dataclass
class Settings:
    station_callsign: str = ""


class StationCallsignError(ValueError):
    """A station callsign in the settings file that breaks CALL's rules.
    `text` is the call as written, for the operator to correct.
    """

    def __init__(self, message: str, text: str) -> None:
        super().__init__(message)
        self.text = text


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    """Load settings, or defaults if the file doesn't exist yet. The
    station callsign is checked like CALL ("" means none is set yet), and
    must be exactly as saved: no spaces around it, and uppercase. The
    unusual-call warning is for the settings modal only, as a call from
    the file is taken as meant.

    Raises tomllib.TOMLDecodeError if the file has been hand-edited into
    invalid TOML, or StationCallsignError (with a message for the
    operator) if its station callsign is refused.
    """
    if not path.exists():
        return Settings()
    with path.open("rb") as f:
        data = tomllib.load(f)
    # Held to exactly what's saved, as a hand edit is the only way to get
    # anything else: only "" means none is set.
    callsign = str(data.get("station_callsign", ""))
    if callsign:
        try:
            check_ascii("station_callsign", callsign)
            check_trimmed("station_callsign", callsign)
            parsed = parse_callsign(callsign, "station_callsign")
            if parsed != callsign:
                raise ValueError(
                    f"station_callsign {callsign!r} should be uppercase, like {parsed}"
                )
        except ValueError as error:
            raise StationCallsignError(str(error), callsign) from None
    return Settings(station_callsign=callsign)


def save_settings(settings: Settings, path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSON string escaping is valid for TOML basic strings.
    path.write_text(
        f"station_callsign = {json.dumps(settings.station_callsign, ensure_ascii=False)}\n"
    )
