from pota_logger.freq import band_name
from pota_logger.logbook import stored_text

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
