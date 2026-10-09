import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from pota_logger.ascii_text import check_ascii
from pota_logger.callsigns import parse_callsign

# src/pota_logger/settings.py -> project root
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SETTINGS_PATH = DATA_DIR / "settings.toml"


# Settings' labels in the modal, as dictated.
NEW_COMMENT_POTA_INFO = "New: Pre-populate COMMENT with POTA info."
EDIT_COMMENT_POTA_INFO = "Edit: Update COMMENT with POTA info."

# The on/off settings, by their key in the file.
SWITCHES = ["new_comment_pota_info", "edit_comment_pota_info"]


@dataclass
class Settings:
    station_callsign: str = ""
    # COMMENT starts as "POTA ", then takes PARK and ST as they're
    # entered: in a new entry, and in an edited one.
    new_comment_pota_info: bool = False
    edit_comment_pota_info: bool = False
    # Where ADIF export writes its files, as typed (`~` is expanded, see
    # folder_path). "" means none is set, and ADIF export is refused
    # until one is. Settings saves only a folder that exists; none is
    # ever made, so a typo can't send files somewhere unexpected.
    adif_export_folder: str = ""
    # Whether loading fixed how the file wrote a value, so it's to be
    # saved again. Not a setting, so settings compare without it.
    fixed: bool = field(default=False, compare=False)
    # What in the file needs fixing by hand, other than the call (those
    # settings are off meanwhile). Not a setting either.
    problems: list[str] = field(default_factory=list, compare=False)


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

    An on/off setting that isn't `true` or `false` is off, with a
    message in `problems`; so is an ADIF export folder that isn't plain
    ASCII text (spaces around it are fixed, like the call's).

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
    switches = {}
    problems = []
    for key in SWITCHES:
        value = data.get(key, False)
        if isinstance(value, bool):
            switches[key] = value
        else:
            problems.append(f"{key} {value!r} must be true or false")
    folder, folder_fixed = load_folder(data.get("adif_export_folder", ""), problems)
    return Settings(
        station_callsign=callsign,
        **switches,
        adif_export_folder=folder,
        fixed=callsign != text or folder_fixed,
        problems=problems,
    )


def load_folder(value, problems: list[str]) -> tuple[str, bool]:
    """The ADIF export folder from the file, and whether spaces around it
    were dropped; "" (none set) with a message in `problems` if it isn't
    plain ASCII text.
    """
    if not isinstance(value, str):
        problems.append(f"adif_export_folder {value!r} must be a folder, in quotes")
        return "", False
    try:
        check_ascii("adif_export_folder", value)
    except ValueError as error:
        problems.append(str(error))
        return "", False
    folder = value.strip(" ")
    return folder, folder != value


def folder_path(folder: str) -> Path:
    """The ADIF export folder as set, `~` expanded."""
    return Path(folder).expanduser()


def save_settings(settings: Settings, path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSON string escaping is valid for TOML basic strings.
    lines = [f"station_callsign = {json.dumps(settings.station_callsign, ensure_ascii=False)}"]
    lines += [f"{key} = {json.dumps(getattr(settings, key))}" for key in SWITCHES]
    lines.append(f"adif_export_folder = {json.dumps(settings.adif_export_folder)}")
    path.write_text("".join(f"{line}\n" for line in lines))
