from datetime import date, time
from decimal import Decimal

import pytest

from pota_logger_t3.logbook import append_entry, load_entries

HEADER = "FREQ,MODE,CALL,PARK,ST,SNT,RCD,PWR,DATE,TIME,COMMENT,STATION_CALLSIGN\n"

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
}
ROW = "14285500,USB,W1ABC,US-1234,NJ,59,57,60,20260925,1953,,W1TST\n"


@pytest.fixture
def log_dir(tmp_path):
    return tmp_path / "data"


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
    append_entry(log_dir, ENTRY, "W1TST")
    assert (log_dir / "20260925.csv").read_text() == HEADER + ROW + ROW


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
    write_log(log_dir, "20260926.csv", HEADER + ROW.replace("W1ABC", "K2DEF"))
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
        (ROW.replace("14285500", "14.2855"), "FREQ '14.2855' should be Hz, like 14074500"),
        (ROW.replace(",60,", ",60W,"), "PWR '60W' should be watts, like 60 or 0.5"),
        (ROW.replace(",W1TST", ""), "has 11 values, should have 12"),
        # Each field's entry rules, as in the operator's hand-edit tests.
        (ROW.replace("14285500", "13285500"), "FREQ '13285500' isn't in a US amateur band (80m to 10m)"),
        (ROW.replace(",USB,", ",ABC,"), "MODE 'ABC' should be SSB, USB, LSB, or CW"),
        (ROW.replace(",W1ABC,", ",W1/,"), "CALL 'W1/' has an empty part next to a /"),
        (ROW.replace("US-1234", "1234X"), "PARK '1234X' isn't a POTA park; use a form like 1234, JP-1234, or US-4566@US-WY"),
        (ROW.replace(",NJ,", ",NNN,"), "ST 'NNN' isn't a US state; use a code like NJ, NA, or blank"),
        (ROW.replace(",NJ,", ",NN,"), "ST 'NN' isn't a US state; use a code like NJ, NA, or blank"),
        (ROW.replace(",59,57,", ",99,57,"), "SNT '99' isn't a real report: readability is 1-5"),
        (ROW.replace(",59,57,", ",59,99,"), "RCD '99' isn't a real report: readability is 1-5"),
        (ROW.replace(",59,57,", ",599,57,"), "SNT '599' needs MODE CW for a 3-digit report"),
        (ROW.replace(",60,", ",9999,"), "PWR '9999' should be between .1 and 1500 watts"),
        (
            ROW.replace("14285500,USB", "14150500,SSB"),
            "SSB on 14.150.500 is within 3 kHz of 20m's voice edge; log USB or LSB",
        ),
        (ROW.replace(",W1ABC,", ",,"), "Missing: CALL"),
        (ROW.replace(",,W1TST", ",Café,W1TST"), "COMMENT 'Café' has non-ASCII characters: 'é'."),
        (ROW.replace(",W1TST", ",W1"), "STATION_CALLSIGN 'W1' doesn't look like a callsign, like W1ABC"),
    ],
)
def test_bad_row_is_skipped_and_named(log_dir, row, message):
    write_log(log_dir, "20260925.csv", HEADER + row + ROW.replace("W1ABC", "K2DEF"))
    entries, problems = load_entries(log_dir)
    assert [entry["CALL"] for entry in entries] == ["K2DEF"]
    assert problems == [f"{log_dir / '20260925.csv'} row 2: {message}"]


def test_blank_optional_values_load(log_dir):
    write_log(log_dir, "20260925.csv", HEADER + ROW.replace(",NJ,", ",,").replace(",W1TST", ","))
    entries, problems = load_entries(log_dir)
    assert entries == [ENTRY | {"ST": "", "STATION_CALLSIGN": ""}]
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
