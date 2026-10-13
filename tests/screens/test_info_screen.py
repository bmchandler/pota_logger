from importlib.metadata import distribution

from pota_logger.app_version import PROGRAM_ID, app_version
from pota_logger.screens.info_screen import CREDIT, LICENSE, REPO_URL, info_message


def test_info_message_lists_the_app_its_maker_version_license_and_folders():
    description = distribution(PROGRAM_ID).metadata["Summary"]
    assert info_message("~/x/data", "~/x/exports").plain == (
        f"POTA Logger\n{description}\n{CREDIT}\n\n"
        f"Version {app_version()}\n{LICENSE}\n{REPO_URL}\n\n"
        "Data:    ~/x/data\nExports: ~/x/exports"
    )


def test_info_message_without_an_export_folder():
    assert info_message("~/x/data", "").plain.endswith("Exports: none set")
