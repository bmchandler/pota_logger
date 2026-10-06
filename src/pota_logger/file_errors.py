"""file_errors.txt, beside the log files: what in them needs fixing by
hand, written at start when there's anything, and removed when there isn't,
so it never outlives the errors it lists.
"""

from datetime import datetime
from pathlib import Path

NAME = "file_errors.txt"

HEADER = (
    "Written by pota-logger at start, {time}.\n"
    "Fix these by hand, then start the app again.\n"
    "\n"
)


def record(log_dir: Path, errors: list[str], now: datetime) -> Path:
    """Write `errors`, one per line under HEADER, to file_errors.txt in
    `log_dir`, or remove it if there are none; its path either way. Raises
    OSError if it can't be written or removed.
    """
    path = log_dir / NAME
    if not errors:
        path.unlink(missing_ok=True)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    time = now.strftime("%Y-%m-%d %H:%M UTC")
    path.write_text(HEADER.format(time=time) + "".join(f"{error}\n" for error in errors))
    return path
