import csv
import io
import os
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from pota_logger.ascii_text import check_ascii, check_trimmed
from pota_logger.callsigns import parse_callsign
from pota_logger.dates import parse_time
from pota_logger.entry_form import FIELDS, OPTIONAL, REPORTS
from pota_logger.freq import in_us_band
from pota_logger.modes import parse_mode
from pota_logger.parks import parse_park
from pota_logger.power import parse_power
from pota_logger.reports import parse_report
from pota_logger.sidebands import check_sideband
from pota_logger.states import parse_state

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


BOM = "﻿"


def find_row(path: Path, row: list[str]) -> tuple[str, list[str], int, int]:
    """Find the first line(s) holding `row` below the header: the file's
    byte-order mark (if any), its lines with their endings, and the
    matched row's start and end line indexes. Raises ValueError if it
    isn't there, e.g. after a hand edit while the app was open.
    """
    text = path.read_bytes().decode("utf-8")
    bom = BOM if text.startswith(BOM) else ""
    # newline="": split on \n, \r\n, or \r, as reading a log does, and keep
    # each line's ending, so lines that aren't touched stay exactly as they
    # were. A quoted COMMENT may span lines, so csv tells which lines make
    # up each row.
    lines = list(io.StringIO(text.removeprefix(BOM), newline=""))
    reader = csv.reader(lines)
    start = 0
    for found in reader:
        if found == row and start > 0:
            return bom, lines, start, reader.line_num
        start = reader.line_num
    raise ValueError(f"{path} no longer holds this entry as it was loaded")


def write_lines(path: Path, bom: str, lines: list[str]) -> None:
    """Write a log file through a temporary file swapped in at the end, so
    a crash midway can't leave it half-written.
    """
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes((bom + "".join(lines)).encode("utf-8"))
    os.replace(temporary, path)


def replace_entry(log_dir: Path, old: dict, new: dict) -> None:
    """Change a saved entry's row from `old` to `new` (each with its
    STATION_CALLSIGN), touching no other line of the file. When DATE
    changes, `new` is appended to its date's file before `old` is removed
    from its own, so a crash between the two leaves a dupe, not a loss.
    """
    path = log_path(log_dir, old["DATE"])
    bom, lines, start, end = find_row(path, to_row(old, old["STATION_CALLSIGN"]))
    if new["DATE"] != old["DATE"]:
        append_entry(log_dir, new, new["STATION_CALLSIGN"])
        replacement = []
    else:
        # The row keeps its old line ending (or none, as the last line).
        ending = lines[end - 1][len(lines[end - 1].rstrip("\r\n")) :]
        text = io.StringIO()
        csv.writer(text, lineterminator=ending).writerow(
            to_row(new, new["STATION_CALLSIGN"])
        )
        replacement = [text.getvalue()]
    write_lines(path, bom, lines[:start] + replacement + lines[end:])


# Conversions back from stored text, strict enough not to misread a value
# (e.g. a spreadsheet saving TIME 0053 as 53), then each field's own entry
# rules, so a hand edit can't load what the entry form would refuse. Last,
# each value must be written exactly as the app writes it.
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
        day = date(int(text[:4]), int(text[4:6]), int(text[6:]))
    except ValueError:
        raise ValueError(f"DATE {text!r} isn't a real date") from None
    # The entry form's YYMMDD covers only these, so an edit couldn't keep
    # another year.
    if not 2000 <= day.year <= 2099:
        raise ValueError(f"DATE {text!r} isn't in 2000-2099, the years the entry form takes")
    return day


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


def check_stored_form(name: str, text: str, stored: str) -> None:
    """Refuse a value that loads, but isn't written as the app writes it:
    a short form the entry form takes (PARK 1234), lowercase, or a number
    written another way (PWR .5, FREQ with a leading zero).
    """
    if text == stored:
        return
    if text.upper() == stored:
        raise ValueError(f"{name} {text!r} should be uppercase, like {stored}")
    raise ValueError(f"{name} {text!r} should be {stored!r} in a log file")


def from_row(row: list[str], file_date: str) -> dict:
    """An entry from its CSV row in the file for `file_date` (YYYYMMDD),
    checked against the entry form's rules that refuse a value, and held
    to exactly what the app writes. Its warnings aren't checked: a saved
    entry was either confirmed when entered, or hand-edited on purpose.

    Raises ValueError naming what's wrong.
    """
    if len(row) != len(COLUMNS):
        raise ValueError(f"has {len(row)} values, should have {len(COLUMNS)}")
    values = dict(zip(COLUMNS, row))
    for name in COLUMNS:
        check_ascii(name, values[name])
        check_trimmed(name, values[name])
    missing = [name for name in COLUMNS if not values[name] and name not in OPTIONAL]
    if missing:
        raise ValueError(f"Missing: {', '.join(missing)}")
    for name, load in LOADERS.items():
        values[name] = load(values[name]) if values[name] else ""
    for name in REPORTS:
        values[name] = parse_report(name, values[name], values["MODE"])
    for name, text, stored in zip(COLUMNS, row, to_row(values, values["STATION_CALLSIGN"])):
        check_stored_form(name, text, stored)
    day = f"{values['DATE']:%Y%m%d}"
    if day != file_date:
        raise ValueError(f"DATE {day!r} should match the file name, {file_date}.csv")
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
                        file_entries.append(from_row(row, path.stem))
                    except ValueError as error:
                        file_problems.append(f"{path} row {reader.line_num}: {error}")
            except UnicodeDecodeError:
                problems.append(f"{path}: isn't plain text (UTF-8)")
                continue
            entries.extend(file_entries)
            problems.extend(file_problems)
    return entries, problems
