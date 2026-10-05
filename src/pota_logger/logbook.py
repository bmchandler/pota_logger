import csv
import io
import os
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

from pota_logger.ascii_text import check_ascii, check_trimmed
from pota_logger.callsigns import parse_callsign
from pota_logger.dates import parse_time
from pota_logger.entry_form import ENTRY_FORMATTERS, FIELDS, OPTIONAL, PARSERS, REPORTS
from pota_logger.freq import in_us_band
from pota_logger.modes import parse_mode
from pota_logger.parks import parse_park
from pota_logger.power import parse_power
from pota_logger.record_ids import new_id, parse_id
from pota_logger.reports import parse_report
from pota_logger.sidebands import check_sideband
from pota_logger.states import parse_state

# CSV columns: the entry fields in entry order, the station callsign, then
# the record ID. The ID is last, so a blank one can be filled in at the end
# of its line, leaving the rest of the line as it was.
COLUMNS = [name for name, _, _ in FIELDS] + ["STATION_CALLSIGN", "UUIDv4"]

# One file per UTC date, named YYYYMMDD.csv.
LOG_FILE_PATTERN = "[0-9]" * 8 + ".csv"


def log_path(log_dir: Path, day: date) -> Path:
    return log_dir / f"{day:%Y%m%d}.csv"


# Each parsed value's stored form, where it isn't the text itself.
STORED_FORMS = {
    "FREQ": str,
    "PWR": lambda watts: format(watts.normalize(), "f"),
    "DATE": lambda day: f"{day:%Y%m%d}",
    "TIME": lambda when: f"{when:%H%M}",
}


def stored_text(name: str, value) -> str:
    return STORED_FORMS.get(name, str)(value)


def to_row(values: dict) -> list[str]:
    """An entry's CSV row, in COLUMNS order, each value in its stored form."""
    return [stored_text(name, values[name]) for name in COLUMNS]


BOM = "\ufeff"


def row_line(row: list[str], ending: str = "\n") -> str:
    """A CSV row as a line of text; a COMMENT with a comma or quote is
    quoted. "\n" line endings, so the file reads cleanly in any text editor.
    """
    text = io.StringIO()
    csv.writer(text, lineterminator=ending).writerow(row)
    return text.getvalue()


def with_id(line: str, record_id: str) -> str:
    """A row's last line with its blank ID (written as nothing, or "")
    filled in, before the line ending.
    """
    text = line.rstrip("\r\n")
    return text.removesuffix('""') + record_id + line[len(text) :]


def find_row(path: Path, lines: list[str], row: list[str]) -> tuple[int, int]:
    """Find the first line(s) holding `row` below the header: the matched
    row's start and end line indexes. A quoted COMMENT may span lines, so
    csv tells which lines make up each row. Raises ValueError if it isn't
    there.
    """
    reader = csv.reader(lines)
    start = 0
    for found in reader:
        if found == row and start > 0:
            return start, reader.line_num
        start = reader.line_num
    raise ValueError(f"{path} doesn't hold this entry")


def write_lines(path: Path, bom: str, lines: list[str]) -> None:
    """Write a log file through a temporary file swapped in at the end, so
    a crash midway can't leave it half-written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_bytes((bom + "".join(lines)).encode("utf-8"))
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


class Problem(NamedTuple):
    """Something wrong in a log row: the column at fault, what's wrong,
    and, if saving it from the entry form fixes it, how.
    """

    field: str
    message: str
    note: str = ""


# Said of a STATION_CALLSIGN that doesn't read, as it has no field in the
# entry form.
FIX_BY_HAND = "It can't be fixed in the app: fix it by hand, or delete the record."

# How saving fixes a problem in a column with no field in the entry form.
NO_FIELD_NOTES = {
    "STATION_CALLSIGN": FIX_BY_HAND,
    "UUIDv4": "Saving gives it a new one.",
}


class Refused(NamedTuple):
    """A row refused on load that still splits into COLUMNS: its values as
    text, its file and line, and every problem found in it.
    """

    row: dict[str, str]
    path: Path
    line: int
    problems: list[Problem]


# A file's new contents, to write: its path, byte-order mark (if any), and
# lines.
Write = tuple[Path, str, list[str]]


class LogWriteError(Exception):
    """A log file couldn't be written. `writes` are the ones not done yet,
    that one first, for `Logbook.write` to try again.
    """

    def __init__(self, path: Path, error: OSError, writes: list[Write]) -> None:
        super().__init__(f"{path}: {error}")
        self.path = path
        self.error = error
        self.writes = writes


class Logbook:
    """The log files in `log_dir`, as the app's own copy of each one's lines
    (refused rows included), loaded at start. Every save changes that copy
    and writes the whole file from it, so a change made to a file by
    another program while the app runs is overwritten, never merged.
    """

    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        # Each file's byte-order mark (if any) and lines, with their endings.
        self.files: dict[Path, tuple[str, list[str]]] = {}
        # Files that aren't UTF-8 text, so they can't be kept as lines.
        self.unreadable: set[Path] = set()
        # Rows refused on load that still split into COLUMNS, to show and
        # fix in the app.
        self.refused: list[Refused] = []
        # Files whose blank IDs were filled in on load but couldn't be
        # written, with why. The app's copy holds the IDs, so the next save
        # to the file writes them.
        self.unsaved_ids: list[tuple[Path, OSError]] = []

    def write(self, writes: list[Write]) -> None:
        """Write each file in turn, keeping each as the app's copy once
        written. Raises LogWriteError at the first that can't be.
        """
        for index, (path, bom, lines) in enumerate(writes):
            try:
                write_lines(path, bom, lines)
            except OSError as error:
                raise LogWriteError(path, error, writes[index:]) from error
            self.files[path] = (bom, lines)

    def appended(self, values: dict) -> Write:
        """The file for an entry's DATE with the entry added at the end,
        and a header first if the file is new or empty. If the file
        already holds that exact row (ID included), as when a save is
        tried again after part of it was written, it's left as it is.
        """
        path = log_path(self.log_dir, values["DATE"])
        if path in self.unreadable:
            raise ValueError(f"{path} isn't plain text (UTF-8), so it's left for a fix by hand")
        bom, lines = self.files.get(path, ("", []))
        row = to_row(values)
        try:
            find_row(path, lines, row)
        except ValueError:
            pass
        else:
            return path, bom, lines
        lines = list(lines) or [row_line(COLUMNS)]
        # A hand edit may leave the last line without its line break, which
        # would join the new row onto it.
        if not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"
        lines.append(row_line(row))
        return path, bom, lines

    def append(self, values: dict) -> None:
        """Add an entry (with its STATION_CALLSIGN and ID) to its DATE's file."""
        self.write([self.appended(values)])

    def stored(self, entry: dict) -> tuple[Path, list[str]]:
        """A saved entry's file, and its row as stored there."""
        refusal = self.refusal(entry)
        if refusal is not None:
            # Its values as they are in the file, which may not match its
            # DATE.
            return refusal.path, [entry[name] for name in COLUMNS]
        return log_path(self.log_dir, entry["DATE"]), to_row(entry)

    def located(self, entry: dict) -> tuple[Path, str, list[str], int, int]:
        """A saved entry's file, that file's byte-order mark and lines, and
        the entry's start and end line indexes in them.
        """
        path, row = self.stored(entry)
        if path not in self.files:
            raise ValueError(f"{path} doesn't hold this entry")
        bom, lines = self.files[path]
        start, end = find_row(path, lines, row)
        return path, bom, lines, start, end

    def is_refused(self, entry: dict) -> bool:
        return self.refusal(entry) is not None

    def refusal(self, entry: dict) -> Refused | None:
        """Why an entry was refused on load, if it was."""
        return next((found for found in self.refused if found.row is entry), None)

    def delete(self, entry: dict) -> None:
        """Remove a saved entry's row, touching no other line of the file."""
        path, bom, lines, start, end = self.located(entry)
        self.write([(path, bom, lines[:start] + lines[end:])])

    def replace(self, old: dict, new: dict) -> None:
        """Change a saved entry's row from `old` to `new` (each with its
        STATION_CALLSIGN and ID), touching no other line of the file. `old` may be
        a refused row. When DATE moves it to another file, `new` is added to
        its date's file before `old` is removed from its own, so a crash
        between the two leaves a dupe, not a loss.
        """
        path, bom, lines, start, end = self.located(old)
        if log_path(self.log_dir, new["DATE"]) != path:
            writes = [self.appended(new), (path, bom, lines[:start] + lines[end:])]
        else:
            # The row keeps its old line ending (or none, as the last line).
            ending = lines[end - 1][len(lines[end - 1].rstrip("\r\n")) :]
            replacement = row_line(to_row(new), ending)
            writes = [(path, bom, lines[:start] + [replacement] + lines[end:])]
        self.write(writes)

    def load(self) -> tuple[list[dict], list[str]]:
        """Every entry in the log files, oldest file first, and a message
        for each row (or file) that couldn't be read, naming the file and
        row. Rows that can't be read are kept in the app's copy of the
        file; those that still split into COLUMNS go in `refused`, the
        rest are skipped. A blank ID (a row added by hand) is filled in
        with a new one and the file rewritten, the one change the app
        makes to a file on its own; a file that can't be written goes in
        `unsaved_ids`.
        """
        entries, problems = [], []
        for path in sorted(self.log_dir.glob(LOG_FILE_PATTERN)):
            try:
                text = path.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                self.unreadable.add(path)
                problems.append(f"{path}: isn't plain text (UTF-8)")
                continue
            # A spreadsheet may add a byte-order mark when saving.
            bom = BOM if text.startswith(BOM) else ""
            # newline="": split on \n, \r\n, or \r, keeping each line's
            # ending, so lines that aren't touched stay exactly as they were.
            lines = list(io.StringIO(text.removeprefix(BOM), newline=""))
            self.files[path] = (bom, lines)
            reader = csv.reader(lines)
            header = next(reader, None)
            if header != COLUMNS:
                problems.append(f"{path} row 1: header should be {','.join(COLUMNS)}")
                continue
            filled = False
            for row in reader:
                if not row:  # a blank line, e.g. left at the end by an editor
                    continue
                if len(row) == len(COLUMNS) and not row[-1]:
                    row[-1] = new_id()
                    # The row's last line, which ends with its ID.
                    last = reader.line_num - 1
                    lines[last] = with_id(lines[last], row[-1])
                    filled = True
                try:
                    values, row_problems = check_row(row, path.stem)
                except ValueError as error:
                    problems.append(f"{path} row {reader.line_num}: {error}")
                    continue
                if row_problems:
                    self.refused.append(
                        Refused(dict(zip(COLUMNS, row)), path, reader.line_num, row_problems)
                    )
                else:
                    entries.append(values)
            if filled:
                try:
                    write_lines(path, bom, lines)
                except OSError as error:
                    self.unsaved_ids.append((path, error))
        return entries, problems


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
    "UUIDv4": parse_id,
}


def stored_form_problem(name: str, text: str, stored: str) -> str:
    """Why a value that loads isn't written as the app writes it: a short
    form the entry form takes (PARK 1234), lowercase (uppercase for the
    record ID), or a number written another way (PWR .5, FREQ with a
    leading zero).
    """
    if text.upper() == stored:
        return f"{name} {text!r} should be uppercase, like {stored}"
    # A record ID, the one value stored lowercase. Too long to repeat.
    if text.lower() == stored:
        return f"{name} {text!r} should be lowercase"
    return f"{name} {text!r} should be {stored!r} in a log file"


def check_row(row: list[str], file_date: str) -> tuple[dict, list[Problem]]:
    """An entry from its CSV row in the file for `file_date` (YYYYMMDD),
    checked against the entry form's rules that refuse a value, and held
    to exactly what the app writes, with every problem found. Each column
    is checked on its own; a check that depends on another column (SNT and
    RCD on MODE, the sideband on FREQ and MODE, the file on DATE) is left
    out while that column is at fault. Warnings aren't checked: a saved
    entry was either confirmed when entered, or hand-edited on purpose.

    Raises ValueError if the row doesn't split into COLUMNS.
    """
    if len(row) != len(COLUMNS):
        raise ValueError(f"has {len(row)} values, should have {len(COLUMNS)}")
    texts = dict(zip(COLUMNS, row))
    values: dict = {}
    problems = []
    for name in COLUMNS:
        text = texts[name]
        try:
            check_ascii(name, text)
            check_trimmed(name, text)
            if not text:
                if name not in OPTIONAL:
                    raise ValueError(f"Missing: {name}")
                values[name] = ""
            elif name in LOADERS:
                values[name] = LOADERS[name](text)
            elif name in REPORTS:
                if "MODE" in values:
                    values[name] = parse_report(name, text, values["MODE"])
            else:
                values[name] = text
        except ValueError as error:
            problems.append(Problem(name, str(error), NO_FIELD_NOTES.get(name, "")))
    for name in COLUMNS:
        if name in values:
            stored = stored_text(name, values[name])
            if texts[name] != stored:
                message = stored_form_problem(name, texts[name], stored)
                note = "Saving makes it lowercase." if name == "UUIDv4" else f"Saving makes it {stored}."
                problems.append(Problem(name, message, note))
    if "DATE" in values:
        day = f"{values['DATE']:%Y%m%d}"
        if day != file_date:
            problems.append(
                Problem(
                    "DATE",
                    f"DATE {day!r} should match the file name, {file_date}.csv",
                    f"Saving moves it to {day}.csv.",
                )
            )
    if "FREQ" in values and "MODE" in values:
        try:
            check_sideband(values["FREQ"], values["MODE"])
        except ValueError as error:
            problems.append(Problem("MODE", str(error)))
    if problems:
        problems = with_form_notes(texts, problems)
    return values, problems


def with_form_notes(row: dict[str, str], problems: list[Problem]) -> list[Problem]:
    """Note how saving fixes each problem in a field that the entry form
    would take as shown there (e.g. FREQ 14.250, read as MHz), as it does
    a stored-form problem.
    """
    shown = refused_texts(row)
    try:
        mode = parse_mode(shown["MODE"].strip())
    except ValueError:
        mode = None
    noted = []
    for problem in problems:
        text = shown.get(problem.field, "").strip()
        if not problem.note and text:
            try:
                check_ascii(problem.field, text)
                if problem.field in REPORTS:
                    if mode is None:
                        raise ValueError
                    value = parse_report(problem.field, text, mode)
                else:
                    value = PARSERS[problem.field](text)
            except (KeyError, ValueError):
                pass
            else:
                problem = problem._replace(
                    note=f"Saving makes it {stored_text(problem.field, value)}."
                )
        noted.append(problem)
    return noted


# A refused row's fields that are shown in the form as they'd be typed,
# when they read; the rest are shown as they are in the file. TIME is left
# as it is: TIME 53 could be 00:53 or 05:03.
REFUSED_LOADERS = {"FREQ": load_freq, "PWR": load_power, "DATE": load_date}


def refused_texts(row: dict[str, str]) -> dict[str, str]:
    """A refused row's values for the entry form, to fix."""
    texts = {}
    for name, _, _ in FIELDS:
        texts[name] = row[name]
        if name in REFUSED_LOADERS:
            try:
                texts[name] = ENTRY_FORMATTERS[name](REFUSED_LOADERS[name](row[name]))
            except (ValueError, ArithmeticError):
                pass
    return texts
