import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pota_logger.parks_list import (
    PARKS_FILE,
    PARKS_INFO_FILE,
    ParksCopy,
    ParksDownloadError,
    download_parks,
    md5_etag,
    parks_folder,
    saved_copy,
)

LIST = (
    b'"reference","name","active","entityId","locationDesc","latitude",'
    b'"longitude","grid"\n'
    b'"US-0001","Acadia National Park","1","291","US-ME","44.31",'
    b'"-68.2034","FN54vh"\n'
)
NEWER_LIST = LIST + (
    b'"US-0002","Alagnak Wild River National Park","1","6","US-AK",'
    b'"59.0908","-156.463","BO19sc"\n'
)
LAST_MODIFIED = "Fri, 09 Oct 2026 07:15:20 GMT"


class FakePota:
    """What the fake server serves, and the requests it got."""

    def __init__(self) -> None:
        self.content = LIST
        self.etag = md5_etag(LIST)
        self.status = 200
        self.requests: list[dict[str, str]] = []


@pytest.fixture
def pota():
    """A local server standing in for pota.app, so tests never reach it."""
    fake = FakePota()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            fake.requests.append(dict(self.headers))
            if fake.status != 200:
                self.send_response(fake.status)
                self.end_headers()
            elif self.headers.get("If-None-Match") == fake.etag:
                self.send_response(304)
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header("ETag", fake.etag)
                self.send_header("Last-Modified", LAST_MODIFIED)
                self.send_header("Content-Length", str(len(fake.content)))
                self.end_headers()
                self.wfile.write(fake.content)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    # A short poll, as shutdown waits for it (0.5 second by default).
    thread = threading.Thread(
        target=server.serve_forever, args=(0.01,), daemon=True
    )
    thread.start()
    fake.url = f"http://127.0.0.1:{server.server_port}/all_parks_ext.csv"
    yield fake
    server.shutdown()
    server.server_close()


@pytest.fixture
def folder(tmp_path):
    return parks_folder(tmp_path / "data")


def test_parks_folder_is_beside_the_logs(tmp_path):
    assert parks_folder(tmp_path) == tmp_path / "pota"


def test_md5_etag_is_quoted_md5():
    assert md5_etag(b"") == '"d41d8cd98f00b204e9800998ecf8427e"'


def test_first_download_saves_list_and_info(pota, folder):
    copy = download_parks(folder, pota.url)
    assert copy == ParksCopy(md5_etag(LIST), LAST_MODIFIED)
    assert (folder / PARKS_FILE).read_bytes() == LIST
    assert json.loads((folder / PARKS_INFO_FILE).read_text()) == {
        "etag": md5_etag(LIST),
        "last_modified": LAST_MODIFIED,
    }
    assert saved_copy(folder) == copy
    assert "If-None-Match" not in pota.requests[0]


def test_user_agent_names_the_app(pota, folder):
    download_parks(folder, pota.url)
    assert pota.requests[0]["User-Agent"].startswith("pota-logger/")


def test_unchanged_list_is_not_downloaded_again(pota, folder):
    download_parks(folder, pota.url)
    assert download_parks(folder, pota.url) is None
    assert pota.requests[1]["If-None-Match"] == md5_etag(LIST)
    assert (folder / PARKS_FILE).read_bytes() == LIST


def test_changed_list_replaces_the_copy(pota, folder):
    download_parks(folder, pota.url)
    pota.content, pota.etag = NEWER_LIST, md5_etag(NEWER_LIST)
    copy = download_parks(folder, pota.url)
    assert copy.etag == md5_etag(NEWER_LIST)
    assert (folder / PARKS_FILE).read_bytes() == NEWER_LIST


def test_forced_download_skips_the_check(pota, folder):
    download_parks(folder, pota.url)
    assert download_parks(folder, pota.url, force=True) is not None
    assert "If-None-Match" not in pota.requests[1]


def test_hand_edited_copy_is_downloaded_afresh(pota, folder):
    download_parks(folder, pota.url)
    (folder / PARKS_FILE).write_bytes(LIST + b"extra\n")
    assert saved_copy(folder) is None
    assert download_parks(folder, pota.url) is not None
    assert "If-None-Match" not in pota.requests[1]
    assert (folder / PARKS_FILE).read_bytes() == LIST


@pytest.mark.parametrize(
    "info", ["", "not json", "{}", '{"etag": "x"}', "[]"]
)
def test_unreadable_info_means_no_sound_copy(pota, folder, info):
    download_parks(folder, pota.url)
    (folder / PARKS_INFO_FILE).write_text(info)
    assert saved_copy(folder) is None


def test_no_copy_without_list(pota, folder):
    download_parks(folder, pota.url)
    (folder / PARKS_FILE).unlink()
    assert saved_copy(folder) is None


def test_no_copy_in_missing_folder(folder):
    assert saved_copy(folder) is None


def test_damaged_download_keeps_the_saved_copy(pota, folder):
    download_parks(folder, pota.url)
    pota.content, pota.etag = NEWER_LIST, md5_etag(LIST + b"other")
    with pytest.raises(ParksDownloadError, match="arrived damaged"):
        download_parks(folder, pota.url, force=True)
    assert (folder / PARKS_FILE).read_bytes() == LIST
    assert saved_copy(folder).etag == md5_etag(LIST)


def test_server_error_keeps_the_saved_copy(pota, folder):
    download_parks(folder, pota.url)
    pota.status = 503
    with pytest.raises(ParksDownloadError, match="server replied 503"):
        download_parks(folder, pota.url, force=True)
    assert (folder / PARKS_FILE).read_bytes() == LIST


def test_not_modified_without_a_copy_is_an_error(pota, folder):
    pota.status = 304
    with pytest.raises(ParksDownloadError, match="server replied 304"):
        download_parks(folder, pota.url)


def test_unreachable_server(folder):
    url = "http://127.0.0.1:1/all_parks_ext.csv"
    with pytest.raises(ParksDownloadError, match="download failed"):
        download_parks(folder, url)
    assert not folder.exists()


def test_unsavable_copy(pota, tmp_path):
    blocker = tmp_path / "data"
    blocker.write_text("a file, not a folder")
    with pytest.raises(ParksDownloadError, match="couldn't be saved"):
        download_parks(parks_folder(blocker), pota.url)
