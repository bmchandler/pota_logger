from datetime import UTC, datetime

from pota_logger_t3.dates import format_date, format_time


def future_time(values: dict) -> str | None:
    """Warn when DATE plus TIME is later than now, UTC."""
    when = datetime.combine(values["DATE"], values["TIME"], UTC)
    if when <= datetime.now(UTC):
        return None
    return (
        f"{format_date(values['DATE'])} {format_time(values['TIME'])} UTC is in the future.\n"
        "Esc to correct, or confirm with Enter."
    )
