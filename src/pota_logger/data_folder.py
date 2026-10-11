"""Where the app keeps its files, and the README.txt beside them.

Run from a clone (`uv run pota-logger`), it's the clone's `data/`, for
development (git-ignored). Installed (`uv tool install`), it's
`~/.local/share/pota-logger/data/`, outside the install, which an
upgrade or uninstall replaces or removes.
"""

import os
from pathlib import Path

# src/pota_logger/data_folder.py -> the project root, in a clone.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_FOLDER = "pota-logger"

# Written beside data/ when installed, for the operator at a terminal.
# It sums up README.md's "Your data": keep the two in step.
README_TEXT = """\
POTA Logger's files
===================

pota-logger keeps its files in data/ here, and ADIF exports in exports/
(unless Settings names another folder). This file is written by the
app, and rewritten when a new version changes it: edits to it aren't
kept.

data/
  YYYYMMDD.csv     Your log: one file per UTC date (20261001.csv), one
                   contact per row. Plain CSV, for a text editor or a
                   spreadsheet.
  settings.toml    Your station callsign and settings, set in the app
                   (F2 opens Settings).
  file_errors.txt  Written at start when a file needs fixing by hand,
                   listing each problem by file and row. The app won't
                   start until they're fixed.
  pota/            POTA's parks list, if downloaded. Safe to delete: get
                   it again from Settings.

Back up data/ to keep your log. Upgrading or uninstalling pota-logger
leaves this folder alone.

One station callsign per log: when your call changes, move the old log
files out of data/, then set the new call in data/settings.toml.

Editing the files by hand
-------------------------

Do:
- Close the app first. While it runs, its next save overwrites changes
  made by anything else.
- Keep the header row exactly as it is:
  FREQ,MODE,CALL,PARK,ST,SNT,RCD,PWR,DATE,TIME,COMMENT,STATION_CALLSIGN,UUIDv4
- Put each record in the file for its DATE. To move a record to another
  day, edit its DATE in the app.
- Write values the way the app does: FREQ in Hz (14074500), MODE SSB,
  USB, LSB, or CW, calls in uppercase, PARK in full (US-0464), ST a
  state code or empty, SNT and RCD 2 digits (3 on CW), PWR in watts (60,
  0.5), DATE as YYYYMMDD, TIME as 4 digits, HHMM (0053).
- Leave UUIDv4 empty on a row you add (end the line with a comma). The
  app fills in a new ID when it starts.
- Quote a COMMENT holding a comma or a double quote: "Nice, loud". A
  double quote inside it is written twice.
- In a spreadsheet, keep TIME as text, so 0053 doesn't turn into 53.
- Save as UTF-8 CSV.

Don't:
- Copy a row to make a new record without emptying its UUIDv4.
- Make up or change an ID.
- Start or end a COMMENT with a space.
- Use non-ASCII characters or line breaks inside a value.
- Add, remove, rename, or reorder columns.
- Name other files in data/ like YYYYMMDD.csv: they'd be read as logs.

If something's off, start the app: it says which file and row, and
what's wrong.
"""


def from_source(root: Path = PROJECT_ROOT) -> bool:
    """Whether the app runs from a clone, not an install."""
    return (root / "pyproject.toml").is_file()


def user_data_home(environ=os.environ) -> Path:
    """`$XDG_DATA_HOME` when set to an absolute path, else ~/.local/share."""
    base = Path(environ.get("XDG_DATA_HOME", ""))
    return base if base.is_absolute() else Path.home() / ".local" / "share"


def data_dir(root: Path = PROJECT_ROOT, environ=os.environ) -> Path:
    if from_source(root):
        return root / "data"
    return user_data_home(environ) / APP_FOLDER / "data"


def write_readme(folder: Path) -> None:
    """Write README.txt in `folder` when it's missing or out of date."""
    path = folder / "README.txt"
    try:
        if path.is_file() and path.read_text() == README_TEXT:
            return
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(README_TEXT)
    except (OSError, UnicodeDecodeError):
        # Only a guide: a folder the app can't write is reported when it
        # saves.
        pass
