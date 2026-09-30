import csv
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from pota_logger_t3.ascii_text import check_ascii
from pota_logger_t3.callsigns import parse_callsign
from pota_logger_t3.dates import parse_time
from pota_logger_t3.entry_form import FIELDS, OPTIONAL, REPORTS
from pota_logger_t3.freq import in_us_band
from pota_logger_t3.modes import parse_mode
from pota_logger_t3.parks import parse_park
from pota_logger_t3.power import parse_power
from pota_logger_t3.reports import parse_report
from pota_logger_t3.sidebands import check_sideband
from pota_logger_t3.states import parse_state

# CSV columns: the entry fields in entry order, then the station callsign.
COLUMNS = [name for name, _, _ in FIELDS] + ["STATION_CALLSIGN"]

# One file per UTC date, named YYYYMMDD.csv.
LOG_FILE_PATTERN = "[0-9]" * 8 + ".csv"


def log_path(log_dir: Path, day: date) -> Path:
    return log_dir / f"{day:%Y%m%d}.csv"


def to_row(values: dict, station_callsign: str) -> list[str]:
    """An entry's CSV row, in COLUMNS order, each value in its stored form."""
    stored = values | {
        "FREQ": str(values["FREQ"]),
        "PWR": format(values["PWR"].normalize(), "f"),
        "DATE": f"{values['DATE']:%Y%m%d}",
        "TIME": f"{values['TIME']:%H%M}",
        "STATION_CALLSIGN": station_callsign,
    }
    return [stored[name] for name in COLUMNS]


def append_entry(log_dir: Path, values: dict, station_callsign: str) -> None:
    """Append an entry to the file for its DATE, with a header if it's new."""
    path = log_path(log_dir, values["DATE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_bytes() if path.exists() else b""
    is_new = not existing
    # A hand edit may leave the last line without its line break, which
    # would join the new row onto it.
    needs_break = not is_new and not existing.endswith(b"\n")
    # "\n" line endings, so the file reads cleanly in any text editor.
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        if is_new:
            writer.writerow(COLUMNS)
        if needs_break:
            f.write("\n")
        writer.writerow(to_row(values, station_callsign))


# Conversions back from stored text, strict enough not to misread a value
# (e.g. a spreadsheet saving TIME 0053 as 53), then each field's own entry
# rules, so a hand edit can't load what the entry form would refuse.
DIGITS = re.compile(r"[0-9]+")
NUMBER = re.compile(r"[0-9]+(\.[0-9]*)?|\.[0-9]+")


def load_freq(text: str) -> int:
    if not DIGITS.fullmatch(text):
        raise ValueError(f"FREQ {text!r} should be Hz, like 14074500")
    hz = int(text)
    if not in_us_band(hz):
        raise ValueError(f"FREQ {text!r} isn't in a US amateur band (80m to 10m)")
    return hz


def load_power(text: str) -> Decimal:
    if not NUMBER.fullmatch(text):
        raise ValueError(f"PWR {text!r} should be watts, like 60 or 0.5")
    return parse_power(text)


def load_date(text: str) -> date:
    if len(text) != 8 or not DIGITS.fullmatch(text):
        raise ValueError(f"DATE {text!r} should be YYYYMMDD, like 20260925")
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    except ValueError:
        raise ValueError(f"DATE {text!r} isn't a real date") from None


# Fields turned from stored text into values, in column order. The rest
# (SNT, RCD, COMMENT) are kept as text; SNT and RCD are checked after these
# since their rules depend on MODE.
LOADERS = {
    "FREQ": load_freq,
    "MODE": parse_mode,
    "CALL": parse_callsign,
    "PARK": parse_park,
    "ST": parse_state,
    "PWR": load_power,
    "DATE": load_date,
    "TIME": parse_time,
    "STATION_CALLSIGN": lambda text: parse_callsign(text, "STATION_CALLSIGN"),
}

# May be blank: the entry form's optional fields, and the station callsign,
# which entries saved before it was set are stored without.
OPTIONAL_COLUMNS = OPTIONAL | {"STATION_CALLSIGN"}


def from_row(row: list[str]) -> dict:
    """An entry from its CSV row, checked against the entry form's rules
    that refuse a value. Its warnings aren't checked: a saved entry was
    either confirmed when entered, or hand-edited on purpose.

    Raises ValueError naming what's wrong.
    """
    if len(row) != len(COLUMNS):
        raise ValueError(f"has {len(row)} values, should have {len(COLUMNS)}")
    values = dict(zip(COLUMNS, row))
    for name in COLUMNS:
        check_ascii(name, values[name])
    missing = [
        name for name in COLUMNS if not values[name].strip() and name not in OPTIONAL_COLUMNS
    ]
    if missing:
        raise ValueError(f"Missing: {', '.join(missing)}")
    for name, load in LOADERS.items():
        values[name] = load(values[name]) if values[name].strip() else ""
    for name in REPORTS:
        values[name] = parse_report(name, values[name], values["MODE"])
    check_sideband(values["FREQ"], values["MODE"])
    return values


def load_entries(log_dir: Path) -> tuple[list[dict], list[str]]:
    """Every entry in the log files, oldest file first, and a message for
    each row (or file) that couldn't be read, naming the file and row.
    Rows that can't be read are skipped; the file itself is left as is.
    """
    entries, problems = [], []
    for path in sorted(log_dir.glob(LOG_FILE_PATTERN)):
        # utf-8-sig: a spreadsheet may add a byte-order mark when saving.
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            file_entries, file_problems = [], []
            try:
                header = next(reader, None)
                if header != COLUMNS:
                    problems.append(f"{path} row 1: header should be {','.join(COLUMNS)}")
                    continue
                for row in reader:
                    if not row:  # a blank line, e.g. left at the end by an editor
                        continue
                    try:
                        file_entries.append(from_row(row))
                    except ValueError as error:
                        file_problems.append(f"{path} row {reader.line_num}: {error}")
            except UnicodeDecodeError:
                problems.append(f"{path}: isn't plain text (UTF-8)")
                continue
            entries.extend(file_entries)
            problems.extend(file_problems)
    return entries, problems
