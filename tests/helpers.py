"""What tests in more than one folder share."""

import os
from pathlib import Path


def fail_to_write(monkeypatch, name=None, error=PermissionError(13, "Permission denied")):
    """Make writing a log file fail with `error`, by default for permissions:
    only the file called `name`, as if it were locked, or every file."""
    real_replace = os.replace

    def replace(source, target):
        if name is None or Path(target).name == name:
            raise error
        real_replace(source, target)

    monkeypatch.setattr("pota_logger.logbook.os.replace", replace)
