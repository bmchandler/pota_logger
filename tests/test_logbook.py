import os
from datetime import date, time
from decimal import Decimal
from pathlib import Path

import pytest

from pota_logger.logbook import Logbook, LogWriteError, Problem, Refused, refused_texts

HEADER = "FREQ,MODE,CALL,PARK,ST,SNT,RCD,PWR,DATE,TIME,COMMENT,STATION_CALLSIGN,UUIDv4\n"

ID = "1b4e28ba-2fa1-4d2b-883f-0016d3cca427"
OTHER_ID = "9f2c4e1a-7b3d-4c8e-a5f6-0123456789ab"

# An entry as the entry form hands it over, parsed.
ENTRY = {
    "FREQ": 14285500,
    "MODE": "USB",
    "CALL": "W1ABC",
    "PARK": "US-1234",
    "ST": "NJ",
    "SNT": "59",
    "RCD": "57",
    "PWR": Decimal("60"),
    "DATE": date(2026, 9, 25),
    "TIME": time(19, 53),
    "COMMENT": "",
    "UUIDv4": ID,
}
ROW = f"14285500,USB,W1ABC,US-1234,NJ,59,57,60,20260925,1953,,W1TST,{ID}\n"


@pytest.fixture
def log_dir(tmp_path):
    return tmp_path / "data"


def loaded(log_dir) -> Logbook:
    book = Logbook(log_dir)
    book.load("W1TST")
    return book


# Each as the app does it on a fresh start.
def load_entries(log_dir):
    """Entries, and a message for every row or file refused, whether
    skipped or kept in `refused` to fix in the app.
    """
    book = Logbook(log_dir)
    entries, problems = book.load("W1TST")
    refused = [
        f"{found.path} row {found.line}: {problem.message}"
        for found in book.refused
        for problem in found.problems
    ]
    return entries, refused + problems


def append_entry(log_dir, values, station_callsign):
    loaded(log_dir).append(values | {"STATION_CALLSIGN": station_callsign})


def replace_entry(log_dir, old, new):
    loaded(log_dir).replace(old, new)


def write_log(log_dir, name, text):
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / name).write_text(text)


def test_first_entry_creates_file_with_header(log_dir):
    append_entry(log_dir, ENTRY, "W1TST")
    assert (log_dir / "20260925.csv").read_text() == HEADER + ROW


def test_entries_append_to_their_dates_file(log_dir):
    append_entry(log_dir, ENTRY, "W1TST")
    append_entry(log_dir, ENTRY | {"CALL": "K2DEF"}, "W1TST")
    append_entry(log_dir, ENTRY | {"DATE": date(2026, 9, 26)}, "W1TST")
    assert (log_dir / "20260925.csv").read_text() == (
        HEADER + ROW + ROW.replace("W1ABC", "K2DEF")
    )
    assert (log_dir / "20260926.csv").read_text() == HEADER + ROW.replace("20260925", "20260926")


@pytest.mark.parametrize(("watts", "stored"), [("60", "60"), (".5", "0.5"), ("2.50", "2.5")])
def test_power_stored_as_plain_decimal(log_dir, watts, stored):
    append_entry(log_dir, ENTRY | {"PWR": Decimal(watts)}, "W1TST")
    row = (log_dir / "20260925.csv").read_text().splitlines()[1]
    assert row.split(",")[7] == stored


def test_early_time_keeps_leading_zeros(log_dir):
    append_entry(log_dir, ENTRY | {"TIME": time(0, 5)}, "W1TST")
    assert ",0005," in (log_dir / "20260925.csv").read_text()


def test_comment_with_commas_and_quotes_is_quoted(log_dir):
    comment = 'POTA US-1234, "nice sig"'
    append_entry(log_dir, ENTRY | {"COMMENT": comment}, "W1TST")
    assert ',"POTA US-1234, ""nice sig""",' in (log_dir / "20260925.csv").read_text()
    entries, problems = load_entries(log_dir)
    assert entries[0]["COMMENT"] == comment
    assert problems == []


def test_append_adds_missing_final_line_break(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW.rstrip("\n"))
    append_entry(log_dir, ENTRY | {"UUIDv4": OTHER_ID}, "W1TST")
    assert (log_dir / "20260925.csv").read_text() == HEADER + ROW + ROW.replace(ID, OTHER_ID)


def test_empty_file_gets_a_header(log_dir):
    write_log(log_dir, "20260925.csv", "")
    append_entry(log_dir, ENTRY, "W1TST")
    assert (log_dir / "20260925.csv").read_text() == HEADER + ROW


def test_round_trip(log_dir):
    append_entry(log_dir, ENTRY, "W1TST")
    entries, problems = load_entries(log_dir)
    assert entries == [ENTRY | {"STATION_CALLSIGN": "W1TST"}]
    assert problems == []


def test_no_data_dir_loads_nothing(log_dir):
    assert load_entries(log_dir) == ([], [])


def test_loads_files_in_date_order_and_ignores_others(log_dir):
    write_log(
        log_dir, "20260926.csv", HEADER + ROW.replace("W1ABC", "K2DEF").replace("20260925", "20260926")
    )
    write_log(log_dir, "20260925.csv", HEADER + ROW)
    write_log(log_dir, "notes.csv", "not a log\n")
    entries, _ = load_entries(log_dir)
    assert [entry["CALL"] for entry in entries] == ["W1ABC", "K2DEF"]


def test_loads_file_saved_with_bom_and_crlf(log_dir):
    log_dir.mkdir(parents=True)
    (log_dir / "20260925.csv").write_bytes(
        b"\xef\xbb\xbf" + (HEADER + ROW).replace("\n", "\r\n").encode()
    )
    entries, problems = load_entries(log_dir)
    assert len(entries) == 1
    assert problems == []


def test_blank_lines_are_skipped(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW + "\n\n")
    entries, problems = load_entries(log_dir)
    assert len(entries) == 1
    assert problems == []


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (ROW.replace(",1953,", ",53,"), "TIME '53' should be HHMM, like 2123"),
        (ROW.replace(",1953,", ",2460,"), "TIME '2460' isn't a real time (0000 to 2359)"),
        (ROW.replace("20260925", "2026-09-25"), "DATE '2026-09-25' should be YYYYMMDD, like 20260925"),
        (ROW.replace("20260925", "20260931"), "DATE '20260931' isn't a real date"),
        (ROW.replace("20260925", "19991231"), "DATE '19991231' isn't in 2000-2099, the years the entry form takes"),
        (ROW.replace("20260925", "21000101"), "DATE '21000101' isn't in 2000-2099, the years the entry form takes"),
        (ROW.replace("14285500", "14.2855"), "FREQ '14.2855' should be Hz, like 14074500"),
        (ROW.replace(",60,", ",60W,"), "PWR '60W' should be watts, like 60 or 0.5"),
        (ROW.replace(",W1TST", ""), "has 12 values, should have 13"),
        # Each field's entry rules, as in the operator's hand-edit tests.
        (ROW.replace("14285500", "13285500"), "FREQ '13285500' isn't in a US amateur band (80m to 10m)"),
        (ROW.replace(",USB,", ",ABC,"), "MODE 'ABC' should be SSB, USB, LSB, or CW"),
        (ROW.replace(",W1ABC,", ",W1/,"), "CALL 'W1/' has an empty part next to a /"),
        (ROW.replace("US-1234", "1234X"), "PARK '1234X' isn't a POTA park; use a form like 1234 or JP-1234"),
        (ROW.replace("US-1234", "US-1234@US-NJ"), "PARK 'US-1234@US-NJ': @ form not accepted for input; ADIF export only"),
        (ROW.replace(",NJ,", ",NNN,"), "ST 'NNN' isn't a US state; use a code like NJ, or blank"),
        (ROW.replace(",NJ,", ",NN,"), "ST 'NN' isn't a US state; use a code like NJ, or blank"),
        (ROW.replace(",59,57,", ",99,57,"), "SNT '99' isn't a real report: readability is 1-5"),
        (ROW.replace(",59,57,", ",59,99,"), "RCD '99' isn't a real report: readability is 1-5"),
        (ROW.replace(",59,57,", ",599,57,"), "SNT '599' needs MODE CW for a 3-digit report"),
        (
            ROW.replace(",USB,", ",CW,").replace(",59,57,", ",59,579,"),
            "SNT '59' needs 3 digits on CW, like 599",
        ),
        (ROW.replace(",60,", ",9999,"), "PWR '9999' should be between .1 and 1500 watts"),
        (
            ROW.replace("14285500,USB", "14150500,SSB"),
            "SSB on 14.150.500 is within 3 kHz of 20m's voice edge; log USB or LSB",
        ),
        (ROW.replace(",W1ABC,", ",,"), "Missing: CALL"),
        (ROW.replace(",,W1TST", ",Café,W1TST"), "COMMENT 'Café' has non-ASCII characters: 'é'."),
        (ROW.replace(",W1TST", ",W1"), "STATION_CALLSIGN 'W1' doesn't look like a callsign, like W1ABC"),
        (ROW.replace(",W1TST", ","), "Missing: STATION_CALLSIGN"),
        # One call per log: the station callsign, in any case.
        (ROW.replace(",W1TST", ",W1XYZ"), "STATION_CALLSIGN 'W1XYZ' doesn't match the station callsign, W1TST"),
        # COMMENT, the operator's own note, is never changed on load.
        (ROW.replace(",,W1TST", ",Nice signal ,W1TST"), "COMMENT 'Nice signal ' should have no spaces around it, like Nice signal"),
        # No short forms: they change what's written, not just how.
        (ROW.replace("US-1234", "1234"), "PARK '1234' should be 'US-1234' in a log file"),
        (ROW.replace("US-1234", "US1234"), "PARK 'US1234' should be 'US-1234' in a log file"),
        (ROW.replace("US-1234", "us464"), "PARK 'us464' should be 'US-0464' in a log file"),
        # DATE as its file's name.
        (ROW.replace("20260925", "20260924"), "DATE '20260924' should match the file name, 20260925.csv"),
    ],
)
def test_bad_row_is_skipped_and_named(log_dir, row, message):
    write_log(log_dir, "20260925.csv", HEADER + row + ROW.replace("W1ABC", "K2DEF"))
    entries, problems = load_entries(log_dir)
    assert [entry["CALL"] for entry in entries] == ["K2DEF"]
    assert problems == [f"{log_dir / '20260925.csv'} row 2: {message}"]


@pytest.mark.parametrize(
    ("row", "fixed"),
    [
        # Spaces around a value.
        (ROW.replace(",W1ABC,", ", W1ABC ,"), ROW),
        (ROW.replace(",NJ,", ", ,"), ROW.replace(",NJ,", ",,")),
        (ROW.replace(",W1TST", ",W1TST "), ROW),
        (ROW.replace(ID, f" {ID}"), ROW),
        # Its case.
        (ROW.replace(",USB,", ",usb,"), ROW),
        (ROW.replace(",W1ABC,", ",w1abc,"), ROW),
        (ROW.replace("US-1234", "us-1234"), ROW),
        (ROW.replace(",NJ,", ",nj,"), ROW),
        (ROW.replace(",W1TST", ",w1tst"), ROW),
        (ROW.replace(ID, ID.upper()), ROW),
        # A number written another way.
        (ROW.replace("14285500", "014285500"), ROW),
        (ROW.replace(",60,", ",60.0,"), ROW),
        (ROW.replace(",60,", ",060,"), ROW),
        (ROW.replace(",60,", ",.5,"), ROW.replace(",60,", ",0.5,")),
    ],
)
def test_how_a_value_is_written_is_fixed_on_load(log_dir, row, fixed):
    write_log(log_dir, "20260925.csv", HEADER + row + OTHER_ROW)
    entries, problems = load_entries(log_dir)
    assert len(entries) == 2
    assert problems == []
    assert (log_dir / "20260925.csv").read_text() == HEADER + fixed + OTHER_ROW


def test_fixed_on_load_in_a_row_still_refused(log_dir):
    # PARK's short form and COMMENT's spaces are left, to fix in the app.
    row = ROW.replace(",W1ABC,US-1234,", ",w1abc ,1234,").replace(",,W1TST", ",Loud ,W1TST")
    write_log(log_dir, "20260925.csv", HEADER + row)
    book = Logbook(log_dir)
    book.load("W1TST")
    fixed = row.replace(",w1abc ,", ",W1ABC,")
    assert (log_dir / "20260925.csv").read_text() == HEADER + fixed
    [refused] = book.refused
    assert refused.row["CALL"] == "W1ABC"
    assert [problem.field for problem in refused.problems] == ["COMMENT", "PARK"]


def test_blank_optional_values_load(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW.replace(",NJ,", ",,"))
    entries, problems = load_entries(log_dir)
    assert entries == [ENTRY | {"ST": "", "STATION_CALLSIGN": "W1TST"}]
    assert problems == []


def test_entry_warnings_arent_checked(log_dir):
    # An unusual call, logged twice: the entry form warns on both, but a
    # saved entry was either confirmed then or hand-edited on purpose.
    row = ROW.replace(",W1ABC,", ",W100AW,")
    write_log(log_dir, "20260925.csv", HEADER + row + row)
    entries, problems = load_entries(log_dir)
    assert len(entries) == 2
    assert problems == []


def test_wrong_header_skips_the_file(log_dir):
    write_log(log_dir, "20260925.csv", ROW)
    entries, problems = load_entries(log_dir)
    assert entries == []
    assert problems == [
        f"{log_dir / '20260925.csv'} row 1: header should be {HEADER.rstrip()}"
    ]


def test_non_utf8_file_is_skipped_whole(log_dir):
    log_dir.mkdir(parents=True)
    (log_dir / "20260925.csv").write_bytes((HEADER + ROW).encode() + b"caf\xe9\n")
    entries, problems = load_entries(log_dir)
    assert entries == []
    assert problems == [f"{log_dir / '20260925.csv'}: isn't plain text (UTF-8)"]


# Changing a saved entry

SAVED = ENTRY | {"STATION_CALLSIGN": "W1TST"}
OTHER_ROW = ROW.replace(",W1ABC,", ",K2DEF,").replace(ID, OTHER_ID)


def test_changed_entry_rewrites_only_its_row(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + OTHER_ROW + ROW + OTHER_ROW)
    replace_entry(log_dir, SAVED, SAVED | {"COMMENT": "Nice, loud"})
    assert (log_dir / "20260925.csv").read_text() == (
        HEADER + OTHER_ROW + ROW.replace(",,", ',"Nice, loud",') + OTHER_ROW
    )


def test_change_leaves_other_lines_exactly_as_they_were(log_dir):
    # A byte-order mark, \r\n endings, a blank line, a refused row, and a
    # COMMENT spanning two lines, as a spreadsheet or hand edit may leave.
    others = (
        f"14285500,USB,K2DEF,US-1234,NJ,59,57,60,20260925,53,,W1TST,{OTHER_ID}\r\n"
        "\r\n"
        f'14285500,USB,K2DEF,US-1234,NJ,59,57,60,20260925,1953,"Two\r\nlines",W1TST,{OTHER_ID}\r\n'
    )
    original = "﻿" + HEADER.replace("\n", "\r\n") + others + ROW.replace("\n", "\r\n")
    log_dir.mkdir(parents=True)
    (log_dir / "20260925.csv").write_bytes(original.encode())
    replace_entry(log_dir, SAVED, SAVED | {"CALL": "N3GHI"})
    assert (log_dir / "20260925.csv").read_bytes().decode() == original.replace(
        ",W1ABC,", ",N3GHI,"
    )


def test_last_row_without_line_break_stays_without(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW.rstrip("\n"))
    replace_entry(log_dir, SAVED, SAVED | {"CALL": "N3GHI"})
    assert (log_dir / "20260925.csv").read_text() == (
        HEADER + ROW.replace(",W1ABC,", ",N3GHI,").rstrip("\n")
    )


def test_only_the_first_of_identical_rows_changes(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW + ROW)
    replace_entry(log_dir, SAVED, SAVED | {"CALL": "N3GHI"})
    assert (log_dir / "20260925.csv").read_text() == (
        HEADER + ROW.replace(",W1ABC,", ",N3GHI,") + ROW
    )


def test_new_date_moves_the_row_to_that_dates_file(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW + OTHER_ROW)
    replace_entry(log_dir, SAVED, SAVED | {"DATE": date(2026, 9, 26)})
    assert (log_dir / "20260925.csv").read_text() == HEADER + OTHER_ROW
    assert (log_dir / "20260926.csv").read_text() == (
        HEADER + ROW.replace("20260925", "20260926")
    )


def test_missing_row_changes_nothing(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + OTHER_ROW)
    with pytest.raises(ValueError, match="doesn't hold this entry"):
        replace_entry(log_dir, SAVED, SAVED | {"DATE": date(2026, 9, 26)})
    assert (log_dir / "20260925.csv").read_text() == HEADER + OTHER_ROW
    assert sorted(path.name for path in log_dir.iterdir()) == ["20260925.csv"]


# The app's copy of the files, as the only source of truth while it runs


def test_change_by_another_program_is_overwritten_on_append(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW)
    book = loaded(log_dir)
    write_log(log_dir, "20260925.csv", HEADER + OTHER_ROW)
    book.append(SAVED | {"CALL": "N3GHI"})
    assert (log_dir / "20260925.csv").read_text() == (
        HEADER + ROW + ROW.replace(",W1ABC,", ",N3GHI,")
    )


def test_change_saves_even_if_the_row_moved_in_the_file(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW + OTHER_ROW)
    book = loaded(log_dir)
    write_log(log_dir, "20260925.csv", HEADER + OTHER_ROW + ROW)
    book.replace(SAVED, SAVED | {"CALL": "N3GHI"})
    assert (log_dir / "20260925.csv").read_text() == (
        HEADER + ROW.replace(",W1ABC,", ",N3GHI,") + OTHER_ROW
    )


def test_refused_rows_and_files_are_kept_when_saving(log_dir):
    refused = ROW.replace(",1953,", ",53,")
    write_log(log_dir, "20260925.csv", HEADER + refused + ROW)
    write_log(log_dir, "20260926.csv", "not a header\n")
    book = loaded(log_dir)
    book.replace(SAVED, SAVED | {"CALL": "N3GHI"})
    book.append(SAVED | {"DATE": date(2026, 9, 26)})
    assert (log_dir / "20260925.csv").read_text() == (
        HEADER + refused + ROW.replace(",W1ABC,", ",N3GHI,")
    )
    assert (log_dir / "20260926.csv").read_text() == (
        "not a header\n" + ROW.replace("20260925", "20260926")
    )


def test_non_utf8_file_isnt_saved_to(log_dir):
    original = (HEADER + ROW).encode() + b"caf\xe9\n"
    log_dir.mkdir(parents=True)
    (log_dir / "20260925.csv").write_bytes(original)
    with pytest.raises(ValueError, match="isn't plain text"):
        append_entry(log_dir, ENTRY, "W1TST")
    assert (log_dir / "20260925.csv").read_bytes() == original


def fail_to_write(monkeypatch, name):
    """Make writing the file called `name` fail, as if it were locked."""
    real_replace = os.replace

    def replace(source, target):
        if Path(target).name == name:
            raise PermissionError(13, "Permission denied")
        real_replace(source, target)

    monkeypatch.setattr("pota_logger.logbook.os.replace", replace)


def test_failed_write_changes_nothing_and_can_be_tried_again(log_dir, monkeypatch):
    write_log(log_dir, "20260925.csv", HEADER + ROW)
    book = loaded(log_dir)
    fail_to_write(monkeypatch, "20260925.csv")
    with pytest.raises(LogWriteError) as caught:
        book.append(SAVED | {"CALL": "N3GHI"})
    assert caught.value.path == log_dir / "20260925.csv"
    assert caught.value.error.strerror == "Permission denied"
    assert (log_dir / "20260925.csv").read_text() == HEADER + ROW
    assert book.files[log_dir / "20260925.csv"] == ("", [HEADER, ROW])
    # No temporary file left behind.
    assert sorted(path.name for path in log_dir.iterdir()) == ["20260925.csv"]
    monkeypatch.undo()
    book.write(caught.value.writes)
    assert (log_dir / "20260925.csv").read_text() == (
        HEADER + ROW + ROW.replace(",W1ABC,", ",N3GHI,")
    )


def test_failed_move_tries_again_only_whats_left(log_dir, monkeypatch):
    # Added to the new date's file, then the old file can't be written:
    # trying again doesn't add it twice.
    write_log(log_dir, "20260925.csv", HEADER + ROW + OTHER_ROW)
    book = loaded(log_dir)
    fail_to_write(monkeypatch, "20260925.csv")
    with pytest.raises(LogWriteError) as caught:
        book.replace(SAVED, SAVED | {"DATE": date(2026, 9, 26)})
    monkeypatch.undo()
    book.write(caught.value.writes)
    assert (log_dir / "20260925.csv").read_text() == HEADER + OTHER_ROW
    assert (log_dir / "20260926.csv").read_text() == (
        HEADER + ROW.replace("20260925", "20260926")
    )


# Deleting a saved entry


def test_delete_removes_only_its_row(log_dir):
    original = "\ufeff" + HEADER + OTHER_ROW + ROW.replace("\n", "\r\n") + OTHER_ROW
    log_dir.mkdir(parents=True)
    (log_dir / "20260925.csv").write_bytes(original.encode())
    loaded(log_dir).delete(SAVED)
    assert (log_dir / "20260925.csv").read_bytes().decode() == (
        "\ufeff" + HEADER + OTHER_ROW + OTHER_ROW
    )


def test_delete_of_a_missing_row_changes_nothing(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + OTHER_ROW)
    with pytest.raises(ValueError, match="doesn't hold this entry"):
        loaded(log_dir).delete(SAVED)
    assert (log_dir / "20260925.csv").read_text() == HEADER + OTHER_ROW


# Refused rows, kept to fix in the app


def test_refused_row_that_splits_into_columns_is_kept_as_text(log_dir):
    refused = ROW.replace(",1953,", ",53,")
    write_log(log_dir, "20260925.csv", HEADER + refused + ROW.replace(",", ";"))
    book = Logbook(log_dir)
    entries, problems = book.load("W1TST")
    assert entries == []
    path = log_dir / "20260925.csv"
    assert book.refused == [
        Refused(
            dict(zip(HEADER.rstrip().split(","), refused.rstrip().split(","))),
            path,
            2,
            [Problem("TIME", "TIME '53' should be HHMM, like 2123")],
        )
    ]
    # Too broken to split: skipped, to fix by hand.
    assert problems == [f"{path} row 3: has 1 values, should have 13"]


def test_refused_row_can_be_fixed(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW.replace("US-1234", "1234") + OTHER_ROW)
    book = Logbook(log_dir)
    book.load("W1TST")
    row = book.refused[0][0]
    assert book.is_refused(row)
    book.replace(row, SAVED)
    assert (log_dir / "20260925.csv").read_text() == HEADER + ROW + OTHER_ROW


def test_refused_row_in_the_wrong_dates_file_moves_when_fixed(log_dir):
    # DATE 20260924 in 20260925.csv: fixed as is, it goes to its DATE's file.
    write_log(log_dir, "20260925.csv", HEADER + ROW.replace("20260925", "20260924") + OTHER_ROW)
    book = Logbook(log_dir)
    book.load("W1TST")
    book.replace(book.refused[0][0], SAVED | {"DATE": date(2026, 9, 24)})
    assert (log_dir / "20260925.csv").read_text() == HEADER + OTHER_ROW
    assert (log_dir / "20260924.csv").read_text() == (
        HEADER + ROW.replace("20260925", "20260924")
    )


def test_refused_row_can_be_deleted(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW.replace(",1953,", ",53,") + OTHER_ROW)
    book = Logbook(log_dir)
    book.load("W1TST")
    book.delete(book.refused[0][0])
    assert (log_dir / "20260925.csv").read_text() == HEADER + OTHER_ROW


def test_refused_texts_show_what_reads_as_typed_and_the_rest_as_is():
    row = dict(
        zip(
            HEADER.rstrip().split(","),
            "7030000,cw,K1BBB,1234,,599,579,.5,20260925,53,Loud,W1TST".split(","),
        )
    )
    assert refused_texts(row) == {
        "FREQ": "7.030.000",
        "MODE": "cw",
        "CALL": "K1BBB",
        "PARK": "1234",
        "ST": "",
        "SNT": "599",
        "RCD": "579",
        "PWR": "0.5",
        "DATE": "260925",
        # Could be 00:53 or 05:03, so it isn't read.
        "TIME": "53",
        "COMMENT": "Loud",
    }
    unreadable = row | {"FREQ": "14.285", "PWR": "lots", "DATE": "9/25/2026"}
    texts = refused_texts(unreadable)
    assert (texts["FREQ"], texts["PWR"], texts["DATE"]) == ("14.285", "lots", "9/25/2026")


def test_every_problem_in_a_row_is_found(log_dir):
    row = f"7030000,usb,W1ABC,1234,NJ,599,59,lots,20260924,53,,w1tst,{ID}\n"
    write_log(log_dir, "20260925.csv", HEADER + row)
    book = Logbook(log_dir)
    book.load("W1TST")
    assert book.refused[0].problems == [
        # usb fixed on load as USB, so SNT is checked against it.
        Problem("SNT", "SNT '599' needs MODE CW for a 3-digit report"),
        Problem("PWR", "PWR 'lots' should be watts, like 60 or 0.5"),
        Problem("TIME", "TIME '53' should be HHMM, like 2123"),
        Problem(
            "PARK", "PARK '1234' should be 'US-1234' in a log file", "Saving makes it US-1234."
        ),
        Problem(
            "DATE",
            "DATE '20260924' should match the file name, 20260925.csv",
            "Saving moves it to 20260924.csv.",
        ),
    ]


def test_unreadable_station_callsign_is_to_fix_by_hand(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW.replace(",W1TST", ",123"))
    book = Logbook(log_dir)
    book.load("W1TST")
    assert book.refused[0].problems == [
        Problem(
            "STATION_CALLSIGN",
            "STATION_CALLSIGN '123' doesn't look like a callsign, like W1ABC",
            "Manually correct CSV log file.",
        )
    ]


def test_other_station_callsign_is_to_fix_by_hand(log_dir):
    # Its case fixed on load, but another call.
    write_log(log_dir, "20260925.csv", HEADER + ROW.replace(",W1TST", ",w1xyz"))
    book = Logbook(log_dir)
    book.load("W1TST")
    assert book.refused[0].problems == [
        Problem(
            "STATION_CALLSIGN",
            "STATION_CALLSIGN 'W1XYZ' doesn't match the station callsign, W1TST",
            "Manually correct CSV log file.",
        )
    ]


def test_reports_arent_checked_against_a_mode_at_fault(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW.replace(",USB,", ",FT8,"))
    book = Logbook(log_dir)
    book.load("W1TST")
    assert [problem.field for problem in book.refused[0].problems] == ["MODE"]


@pytest.mark.parametrize(
    ("row", "problem"),
    [
        # The form reads 14.250 as MHz.
        (
            ROW.replace("14285500", "14.250"),
            Problem(
                "FREQ", "FREQ '14.250' should be Hz, like 14074500", "Saving makes it 14250000."
            ),
        ),
        # The form reads 1234 as a US park.
        (
            ROW.replace("US-1234", "1234"),
            Problem(
                "PARK", "PARK '1234' should be 'US-1234' in a log file", "Saving makes it US-1234."
            ),
        ),
    ],
)
def test_problem_the_form_would_take_as_shown_notes_how_saving_fixes_it(log_dir, row, problem):
    write_log(log_dir, "20260925.csv", HEADER + row)
    book = Logbook(log_dir)
    book.load("W1TST")
    assert book.refused[0].problems == [problem]


def test_problem_the_form_wouldnt_take_has_no_note(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW.replace(",1953,", ",53,"))
    book = Logbook(log_dir)
    book.load("W1TST")
    assert book.refused[0].problems == [Problem("TIME", "TIME '53' should be HHMM, like 2123")]


# Record IDs

V1_ID = "1b4e28ba-2fa1-11d2-883f-0016d3cca427"

@pytest.mark.parametrize(
    ("text", "message"),
    [
        # Version 1, not 4.
        (V1_ID, f"UUIDv4 '{V1_ID}' should be a UUID as the app writes it, like {ID}"),
        ("abc", f"UUIDv4 'abc' should be a UUID as the app writes it, like {ID}"),
    ],
)
def test_bad_id_is_refused_and_saving_gives_a_new_one(log_dir, text, message):
    write_log(log_dir, "20260925.csv", HEADER + ROW.replace(ID, text))
    book = Logbook(log_dir)
    book.load("W1TST")
    assert book.refused[0].problems == [Problem("UUIDv4", message, "Saving gives it a new one.")]


def test_blank_id_is_filled_in_on_load(log_dir, monkeypatch):
    monkeypatch.setattr("pota_logger.logbook.new_id", lambda: OTHER_ID)
    write_log(log_dir, "20260925.csv", HEADER + ROW + ROW.replace(ID, "").replace("W1ABC", "K2DEF"))
    entries, problems = load_entries(log_dir)
    assert [entry["UUIDv4"] for entry in entries] == [ID, OTHER_ID]
    assert problems == []
    assert (log_dir / "20260925.csv").read_text() == (
        HEADER + ROW + ROW.replace(ID, OTHER_ID).replace("W1ABC", "K2DEF")
    )


def test_filling_in_an_id_leaves_the_rest_of_the_file_as_it_was(log_dir, monkeypatch):
    # A byte-order mark, \r\n endings, quoting the app wouldn't write, a
    # blank ID written as "", and refused rows, which get one too: one with
    # a COMMENT spanning two lines.
    monkeypatch.setattr("pota_logger.logbook.new_id", lambda: OTHER_ID)
    rows = (
        '"14285500",USB,K2DEF,US-1234,NJ,59,57,60,20260925,1953,"Two\r\nlines",W1TST,\r\n'
        '14285500,USB,N3GHI,US-1234,NJ,59,57,60,20260925,1953,,W1TST,""\r\n'
        "14285500,USB,K4JKL,US-1234,NJ,59,57,60,20260925,53,,W1TST,\r\n"
        "14285500,USB,K5MNO,US-1234,NJ,59,57,60,20260925,1953,,W1TST,"
    )
    original = "﻿" + HEADER.replace("\n", "\r\n") + rows
    log_dir.mkdir(parents=True)
    (log_dir / "20260925.csv").write_bytes(original.encode())
    book = Logbook(log_dir)
    entries, _ = book.load("W1TST")
    assert [entry["CALL"] for entry in entries] == ["N3GHI", "K5MNO"]
    assert [(found.row["CALL"], found.row["UUIDv4"]) for found in book.refused] == [
        ("K2DEF", OTHER_ID),
        ("K4JKL", OTHER_ID),
    ]
    filled = rows.replace(",\r\n", f",{OTHER_ID}\r\n").replace(',""\r\n', f",{OTHER_ID}\r\n")
    assert (log_dir / "20260925.csv").read_bytes().decode() == (
        "﻿" + HEADER.replace("\n", "\r\n") + filled + OTHER_ID
    )


def test_file_with_no_blank_id_isnt_rewritten(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW)
    before = (log_dir / "20260925.csv").stat().st_mtime_ns
    os.utime(log_dir / "20260925.csv", ns=(before - 10**9, before - 10**9))
    loaded(log_dir)
    assert (log_dir / "20260925.csv").stat().st_mtime_ns == before - 10**9


def test_filled_id_that_cant_be_written_is_saved_with_the_next_change(log_dir, monkeypatch):
    monkeypatch.setattr("pota_logger.logbook.new_id", lambda: OTHER_ID)
    write_log(log_dir, "20260925.csv", HEADER + ROW.replace(ID, ""))
    fail_to_write(monkeypatch, "20260925.csv")
    book = Logbook(log_dir)
    entries, problems = book.load("W1TST")
    assert len(entries) == 1
    assert problems == []
    [(path, error)] = book.unsaved
    assert path == log_dir / "20260925.csv"
    assert error.strerror == "Permission denied"
    assert (log_dir / "20260925.csv").read_text() == HEADER + ROW.replace(ID, "")
    monkeypatch.undo()
    book.append(SAVED | {"CALL": "N3GHI"})
    assert (log_dir / "20260925.csv").read_text() == (
        HEADER + ROW.replace(ID, OTHER_ID) + ROW.replace(",W1ABC,", ",N3GHI,")
    )


def test_move_saved_again_after_a_failed_write_adds_it_once(log_dir, monkeypatch):
    # Added to the new date's file, then the old file can't be written and
    # the operator gives up; saving the edit again starts over, but the
    # new date's file already holds the row.
    write_log(log_dir, "20260925.csv", HEADER + ROW + OTHER_ROW)
    book = loaded(log_dir)
    moved = SAVED | {"DATE": date(2026, 9, 26)}
    fail_to_write(monkeypatch, "20260925.csv")
    with pytest.raises(LogWriteError):
        book.replace(SAVED, moved)
    monkeypatch.undo()
    book.replace(SAVED, moved)
    assert (log_dir / "20260925.csv").read_text() == HEADER + OTHER_ROW
    assert (log_dir / "20260926.csv").read_text() == (
        HEADER + ROW.replace("20260925", "20260926")
    )


def test_move_changed_after_a_failed_write_keeps_both_versions(log_dir, monkeypatch):
    # Changed again before saving: both versions are kept, sharing the ID,
    # for the operator to choose between, rather than one dropped unseen.
    write_log(log_dir, "20260925.csv", HEADER + ROW + OTHER_ROW)
    book = loaded(log_dir)
    moved = SAVED | {"DATE": date(2026, 9, 26)}
    fail_to_write(monkeypatch, "20260925.csv")
    with pytest.raises(LogWriteError):
        book.replace(SAVED, moved)
    monkeypatch.undo()
    book.replace(SAVED, moved | {"COMMENT": "Loud"})
    moved_row = ROW.replace("20260925", "20260926")
    assert (log_dir / "20260926.csv").read_text() == (
        HEADER + moved_row + moved_row.replace(",,", ",Loud,")
    )
