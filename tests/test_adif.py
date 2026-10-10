from datetime import date, datetime, time
from decimal import Decimal

import pytest

from pota_logger.fields.parks import Park

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
        (date(2026, 10, 9), date(2026, 10, 9), "pota_20261009195312_20261009_20261009.adi"),
        (date(2026, 9, 28), date(2026, 10, 2), "pota_20261009195312_20260928_20261002.adi"),
    ],
)
def test_export_file_name(start, end, name):
    assert export_file_name(start, end, CREATED) == name


PARKS = {
    "US-1234": Park("Some Park", True, "291", ("NJ",)),
    "US-0002": Park("Alagnak Wild River National Park", True, "6", ("AK",)),
    "FR-0081": Park("Guadeloupe Provincial Park", False, "", ()),
    "US-4566": Park("California National Historic Trail", True, "291", ("CA", "NV", "WY")),
}


def test_dxcc_from_the_parks_list():
    assert ("DXCC", "291") in adif_fields(ENTRY, PARKS)
    assert "<DXCC:3>291" in adif_record(ENTRY, PARKS)
    alaska = ENTRY | {"PARK": "US-0002", "ST": "AK"}
    assert ("DXCC", "6") in adif_fields(alaska, PARKS)


def test_dxcc_after_state():
    names = [name for name, _ in adif_fields(ENTRY, PARKS)]
    assert names[names.index("STATE") + 1] == "DXCC"


@pytest.mark.parametrize(
    "entry, parks",
    [
        (ENTRY, {}),
        (ENTRY | {"PARK": "US-9999"}, PARKS),
        (ENTRY | {"PARK": "FR-0081", "ST": ""}, PARKS),
    ],
)
def test_no_dxcc_without_the_parks_entity(entry, parks):
    assert "DXCC" not in [name for name, _ in adif_fields(entry, parks)]


def test_file_records_take_dxcc():
    text = adif_file([ENTRY], datetime(2026, 10, 10, 1, 2, 3), PARKS)
    assert "<DXCC:3>291" in text.splitlines()[-1]



def test_park_in_several_states_takes_st_as_its_location():
    exported = dict(adif_fields(ENTRY | {"PARK": "US-4566", "ST": "WY"}, PARKS))
    assert exported["POTA_REF"] == "US-4566@US-WY"
    # The older pair stays the plain reference.
    assert exported["SIG_INFO"] == "US-4566"


@pytest.mark.parametrize(
    "entry, parks",
    [
        # A park in one state, no ST or one not the park's, or no list.
        (ENTRY, PARKS),
        (ENTRY | {"PARK": "US-4566", "ST": ""}, PARKS),
        (ENTRY | {"PARK": "US-4566", "ST": "NJ"}, PARKS),
        (ENTRY | {"PARK": "US-4566", "ST": "WY"}, {}),
    ],
)
def test_pota_ref_without_location(entry, parks):
    assert dict(adif_fields(entry, parks))["POTA_REF"] == entry["PARK"]
