from datetime import date, datetime, time
from decimal import Decimal

import pytest

from pota_logger.adif import (
    ADIF_VERSION,
    adif_field,
    adif_fields,
    adif_file,
    adif_freq,
    adif_header,
    adif_record,
    export_file_name,
)

# An entry as the log holds it, parsed.
ENTRY = {
    "FREQ": 14285500,
    "MODE": "SSB",
    "CALL": "W1ABC",
    "PARK": "US-1234",
    "ST": "NJ",
    "SNT": "59",
    "RCD": "57",
    "PWR": Decimal("60"),
    "DATE": date(2026, 9, 25),
    "TIME": time(19, 53),
    "COMMENT": "POTA US-1234 NJ",
    "STATION_CALLSIGN": "W1TST",
    "UUIDv4": "1b4e28ba-2fa1-4d2b-883f-0016d3cca427",
}


def test_field_has_its_length():
    assert adif_field("CALL", "W1ABC") == "<CALL:5>W1ABC"


def test_field_length_counts_brackets_in_the_value():
    # The length says where the value ends, so a COMMENT may hold < and >.
    assert adif_field("COMMENT", "<EOR> 5/9") == "<COMMENT:9><EOR> 5/9"


@pytest.mark.parametrize(
    "hz, mhz",
    [
        (14285500, "14.285500"),
        (14074123, "14.074123"),
        (7030000, "7.030000"),
        (29700000, "29.700000"),
        (3500001, "3.500001"),
    ],
)
def test_freq_in_mhz_to_the_hz(hz, mhz):
    assert adif_freq(hz) == mhz


def test_record():
    assert adif_record(ENTRY) == (
        "<QSO_DATE:8>20260925 <TIME_ON:4>1953 <CALL:5>W1ABC <BAND:3>20m"
        " <FREQ:9>14.285500 <MODE:3>SSB <RST_SENT:2>59 <RST_RCVD:2>57"
        " <TX_PWR:2>60 <STATE:2>NJ <POTA_REF:7>US-1234 <SIG:4>POTA"
        " <SIG_INFO:7>US-1234 <COMMENT:15>POTA US-1234 NJ"
        " <STATION_CALLSIGN:5>W1TST <EOR>"
    )


def fields(entry) -> dict:
    return dict(adif_fields(entry))


@pytest.mark.parametrize("mode", ["USB", "LSB"])
def test_usb_and_lsb_are_ssb_submodes(mode):
    exported = fields(ENTRY | {"MODE": mode})
    assert exported["MODE"] == "SSB"
    assert exported["SUBMODE"] == mode


@pytest.mark.parametrize("mode", ["SSB", "CW"])
def test_ssb_and_cw_have_no_submode(mode):
    exported = fields(ENTRY | {"MODE": mode, "SNT": "599", "RCD": "579"})
    assert exported["MODE"] == mode
    assert "SUBMODE" not in exported


@pytest.mark.parametrize(
    "hz, band",
    [(3_573_000, "80m"), (7_030_000, "40m"), (10_136_000, "30m"), (28_400_000, "10m")],
)
def test_band_from_freq(hz, band):
    assert fields(ENTRY | {"FREQ": hz})["BAND"] == band


def test_blank_st_leaves_state_out():
    assert "STATE" not in fields(ENTRY | {"ST": ""})


def test_blank_comment_is_left_out():
    assert "COMMENT" not in fields(ENTRY | {"COMMENT": ""})


def test_park_with_location():
    exported = fields(ENTRY | {"PARK": "US-4566@US-WY"})
    assert exported["POTA_REF"] == "US-4566@US-WY"
    assert exported["SIG_INFO"] == "US-4566@US-WY"


@pytest.mark.parametrize("watts, shown", [("2.5", "2.5"), ("0.5", "0.5"), ("1500", "1500")])
def test_power_in_watts(watts, shown):
    assert fields(ENTRY | {"PWR": Decimal(watts)})["TX_PWR"] == shown


def test_time_keeps_leading_zeros():
    exported = fields(ENTRY | {"DATE": date(2026, 1, 2), "TIME": time(0, 5)})
    assert exported["QSO_DATE"] == "20260102"
    assert exported["TIME_ON"] == "0005"


def test_record_id_isnt_exported():
    assert ENTRY["UUIDv4"] not in adif_record(ENTRY)


CREATED = datetime(2026, 10, 9, 19, 53, 12)


def test_header():
    header = adif_header(CREATED)
    lines = header.split("\n")
    # The first line is text, so it mustn't start with <.
    assert lines[0] == "POTA Logger ADIF export"
    assert lines[1] == f"<ADIF_VER:5>{ADIF_VERSION}"
    assert lines[2] == "<PROGRAMID:11>pota-logger"
    assert lines[3].startswith("<PROGRAMVERSION:")
    assert lines[4] == "<CREATED_TIMESTAMP:15>20261009 195312"
    assert lines[5] == "<EOH>"


def test_file_has_a_record_per_entry_in_order():
    second = ENTRY | {"CALL": "W1XYZ", "TIME": time(20, 1)}
    text = adif_file([ENTRY, second], CREATED)
    assert text == adif_header(CREATED) + "\n" + adif_record(ENTRY) + "\n" + adif_record(second) + "\n"


def test_file_is_plain_ascii():
    adif_file([ENTRY], CREATED).encode("ascii")


@pytest.mark.parametrize(
    "start, end, name",
    [
        (date(2026, 10, 9), date(2026, 10, 9), "pota_20261009_20261009_195312.adi"),
        (date(2026, 9, 28), date(2026, 10, 2), "pota_20260928_20261002_195312.adi"),
    ],
)
def test_export_file_name(start, end, name):
    assert export_file_name(start, end, CREATED) == name
