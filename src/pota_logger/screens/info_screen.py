from importlib.metadata import distribution

from textual.content import Content

from pota_logger.app_version import PROGRAM_ID, app_version
from pota_logger.screens.warning_screen import WarningScreen

CREDIT = "Created by Brian M. Chandler, KL4E."
LICENSE = "MIT License"
REPO_URL = "https://github.com/bmchandler/pota_logger"
# As on the dupe block: a notice to acknowledge, not a choice.
CLOSE_BUTTON = "Roger Roger"


def info_message(data_folder: str, export_folder: str) -> Content:
    """What the Info modal shows: the app, who made it, its version and
    license, and where this install keeps its files.
    """
    description = distribution(PROGRAM_ID).metadata["Summary"]
    return Content.assemble(
        ("POTA Logger", "bold"),
        f"\n{description}\n{CREDIT}\n\n",
        f"Version {app_version()}\n{LICENSE}\n{REPO_URL}\n\n",
        f"Data:    {data_folder}\n",
        f"Exports: {export_folder or 'none set'}",
    )


class InfoScreen(WarningScreen):
    """About the app (`f1`). Esc, Enter, or its one button closes it."""

    DEFAULT_CSS = """
    InfoScreen > Vertical {
        width: 76;
        border: thick $primary;
    }
    """

    def __init__(self, data_folder: str, export_folder: str) -> None:
        super().__init__(
            info_message(data_folder, export_folder),
            confirm_label=CLOSE_BUTTON,
            back_button=False,
        )
