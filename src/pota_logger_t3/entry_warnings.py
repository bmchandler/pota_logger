from datetime import UTC, datetime

from pota_logger_t3.dates import format_date, format_time
from pota_logger_t3.freq import band_name, format_freq, in_voice_range

CONFIRM_HINT = "Esc to correct, or confirm with Enter."


def future_time(values: dict) -> str | None:
    """Warn when DATE plus TIME is later than now, UTC."""
    when = datetime.combine(values["DATE"], values["TIME"], UTC)
    if when <= datetime.now(UTC):
        return None
    return (
        f"{format_date(values['DATE'])} {format_time(values['TIME'])} UTC is in the future.\n"
        f"{CONFIRM_HINT}"
    )


def voice_in_cw_range(values: dict) -> str | None:
    """Warn when a voice mode's FREQ is in its band's CW/data range."""
    if values["MODE"] == "CW" or in_voice_range(values["FREQ"]):
        return None
    freq = values["FREQ"]
    return (
        f"{values['MODE']} on {format_freq(freq)} is outside {band_name(freq)}'s voice range.\n"
        f"{CONFIRM_HINT}"
    )
