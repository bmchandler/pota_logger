from datetime import date, datetime
from importlib.metadata import version

from pota_logger.freq import band_name
from pota_logger.logbook import stored_text

# The ADIF version the export follows, and the app as ADIF names it.
ADIF_VERSION = "3.1.6"
PROGRAM_ID = "pota-logger"

# MODE values that ADIF lists as submodes of SSB.
SSB_SUBMODES = {"USB", "LSB"}


def adif_field(name: str, value: str) -> str:
    """One ADIF field, `<NAME:length>value`. Every value is plain ASCII
    (the entry rules refuse anything else), so its length in characters
    is its length in bytes.
    """
    return f"<{name}:{len(value)}>{value}"


def adif_freq(hz: int) -> str:
    """FREQ in MHz, as ADIF takes it, to the Hz: 14074500 -> 14.074500."""
    return f"{hz // 1_000_000}.{hz % 1_000_000:06d}"


def adif_fields(entry: dict) -> list[tuple[str, str]]:
    """An entry's ADIF fields as (name, value), leaving out blank ones (ST
    and COMMENT). PARK goes in `POTA_REF` and in `SIG`/`SIG_INFO`, as
    QRZ.com reads the older pair. The record ID isn't exported.
    """
    mode = entry["MODE"]
    fields = [
        ("QSO_DATE", stored_text("DATE", entry["DATE"])),
        ("TIME_ON", stored_text("TIME", entry["TIME"])),
        ("CALL", entry["CALL"]),
        ("BAND", band_name(entry["FREQ"])),
        ("FREQ", adif_freq(entry["FREQ"])),
        ("MODE", "SSB" if mode in SSB_SUBMODES else mode),
        ("SUBMODE", mode if mode in SSB_SUBMODES else ""),
        ("RST_SENT", entry["SNT"]),
        ("RST_RCVD", entry["RCD"]),
        ("TX_PWR", stored_text("PWR", entry["PWR"])),
        ("STATE", entry["ST"]),
        ("POTA_REF", entry["PARK"]),
        ("SIG", "POTA"),
        ("SIG_INFO", entry["PARK"]),
        ("COMMENT", entry["COMMENT"]),
        ("STATION_CALLSIGN", entry["STATION_CALLSIGN"]),
    ]
    return [(name, value) for name, value in fields if value]


def adif_record(entry: dict) -> str:
    """An entry as one ADIF record, ending with `<EOR>`: what a file
    export writes per entry, and what QRZ.com's API takes per QSO.
    """
    fields = " ".join(adif_field(name, value) for name, value in adif_fields(entry))
    return f"{fields} <EOR>"


def adif_header(created: datetime) -> str:
    """The ADIF file header, ending `<EOH>`. Its first line is plain text
    (ADIF takes any that doesn't start with `<`). `created` is UTC.
    """
    fields = [
        ("ADIF_VER", ADIF_VERSION),
        ("PROGRAMID", PROGRAM_ID),
        ("PROGRAMVERSION", version(PROGRAM_ID)),
        ("CREATED_TIMESTAMP", f"{created:%Y%m%d %H%M%S}"),
    ]
    lines = ["POTA Logger ADIF export"] + [adif_field(name, value) for name, value in fields]
    return "\n".join(lines) + "\n<EOH>"


def adif_file(entries: list[dict], created: datetime) -> str:
    """An ADIF file's text: the header, then each entry's record on its
    own line, in the order given.
    """
    return "\n".join([adif_header(created)] + [adif_record(entry) for entry in entries]) + "\n"


def export_file_name(start: date, end: date, created: datetime) -> str:
    """`pota_<from>_<to>_<HHMMSS>.adi`: the range's UTC dates and the
    export's UTC time, so an export never overwrites another.
    """
    return f"pota_{start:%Y%m%d}_{end:%Y%m%d}_{created:%H%M%S}.adi"
