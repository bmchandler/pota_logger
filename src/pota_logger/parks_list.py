import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

from pota_logger.adif import PROGRAM_ID

# POTA's list of every park, rebuilt by POTA about nightly.
PARKS_URL = "https://pota.app/all_parks_ext.csv"
# The copy, and what the server said about it, in the data folder's
# `pota/` (beside the log files and settings).
PARKS_FOLDER = "pota"
PARKS_FILE = "all_parks_ext.csv"
PARKS_INFO_FILE = "all_parks_ext.json"

# Long enough for the 9 MB list on a slow line.
TIMEOUT_SECONDS = 60


class ParksDownloadError(Exception):
    """A download that failed, with a message for the operator. Any copy
    already saved is left as it was.
    """


@dataclass
class ParksCopy:
    """What the server said about the saved copy: its `ETag` (the file's
    MD5, quoted, as S3 gives it) and `Last-Modified` (POTA's date for it).
    """

    etag: str
    last_modified: str


def parks_folder(data_dir: Path) -> Path:
    return data_dir / PARKS_FOLDER


def md5_etag(content: bytes) -> str:
    """The `ETag` S3 gives a file uploaded whole: its MD5, quoted."""
    return f'"{hashlib.md5(content).hexdigest()}"'


def saved_copy(folder: Path) -> ParksCopy | None:
    """The saved copy's info, or None when there's no copy, or it doesn't
    match its `ETag` (damaged or hand-edited, so it's to be downloaded
    afresh), or its info is missing or unreadable.
    """
    try:
        info = json.loads((folder / PARKS_INFO_FILE).read_text("utf-8"))
        copy = ParksCopy(str(info["etag"]), str(info["last_modified"]))
        content = (folder / PARKS_FILE).read_bytes()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if md5_etag(content) != copy.etag:
        return None
    return copy


def write_file(path: Path, content: bytes) -> None:
    """Write through a temporary file swapped in at the end, so a crash
    midway can't leave it half-written.
    """
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def download_parks(
    folder: Path, url: str = PARKS_URL, force: bool = False
) -> ParksCopy | None:
    """Download POTA's parks list into `folder` (made if missing), and
    return the new copy's info, or None if the saved copy is still
    current. Unless `force`, a sound saved copy is checked with
    `If-None-Match`, so an unchanged list costs POTA only a small "not
    modified" reply. A download whose content doesn't match its `ETag` is
    refused, keeping the saved copy.

    Raises ParksDownloadError, with a message for the operator.
    """
    headers = {"User-Agent": f"{PROGRAM_ID}/{version(PROGRAM_ID)}"}
    copy = None if force else saved_copy(folder)
    if copy:
        headers["If-None-Match"] = copy.etag
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            content = response.read()
            etag = response.headers.get("ETag", "")
            last_modified = response.headers.get("Last-Modified", "")
    except urllib.error.HTTPError as error:
        if error.code == 304 and copy:
            return None
        raise ParksDownloadError(
            f"Parks list download failed: the server replied {error.code}."
        ) from None
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise ParksDownloadError(
            f"Parks list download failed: {reason}."
        ) from None
    if md5_etag(content) != etag:
        raise ParksDownloadError(
            "Parks list download failed: the file arrived damaged."
        )
    new_copy = ParksCopy(etag, last_modified)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        # The list first: if its info then fails to save, the copy reads
        # as unsound and is downloaded afresh next time.
        write_file(folder / PARKS_FILE, content)
        info = {"etag": etag, "last_modified": last_modified}
        write_file(folder / PARKS_INFO_FILE, json.dumps(info).encode("utf-8"))
    except OSError as error:
        raise ParksDownloadError(
            f"Parks list couldn't be saved: {error.strerror or error}."
        ) from None
    return new_copy
