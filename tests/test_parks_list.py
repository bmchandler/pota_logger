import json
from datetime import date

import pytest
from conftest import LAST_MODIFIED, LIST, NEWER_LIST

from pota_logger.parks import Park
from pota_logger.parks_list import (
    PARKS_FILE,
    PARKS_INFO_FILE,
    ParksCopy,
    ParksDownloadError,
    copy_date,
    download_parks,
    md5_etag,
    load_parks,
    parks_folder,
    saved_copy,
)

@pytest.fixture
def folder(tmp_path):
    return parks_folder(tmp_path / "data")


def test_parks_folder_is_beside_the_logs(tmp_path):
    assert parks_folder(tmp_path) == tmp_path / "pota"


def test_copy_date_is_potas_date():
    assert copy_date(ParksCopy('"x"', LAST_MODIFIED)) == date(2026, 10, 9)


@pytest.mark.parametrize("last_modified", ["", "yesterday"])
def test_copy_date_unknown(last_modified):
    assert copy_date(ParksCopy('"x"', last_modified)) is None


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
        download_parks(folder, pota.url)
    assert (folder / PARKS_FILE).read_bytes() == LIST
    assert saved_copy(folder).etag == md5_etag(LIST)


def test_server_error_keeps_the_saved_copy(pota, folder):
    download_parks(folder, pota.url)
    pota.status = 503
    with pytest.raises(ParksDownloadError, match="server replied 503"):
        download_parks(folder, pota.url)
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


def test_parks_by_reference(pota, folder):
    pota.content, pota.etag = NEWER_LIST, md5_etag(NEWER_LIST)
    download_parks(folder, pota.url)
    assert load_parks(folder) == {
        "US-0001": Park("Acadia National Park", True, "291", ("ME",)),
        "US-0002": Park("Alagnak Wild River National Park", True, "6", ("AK",)),
    }


@pytest.mark.parametrize(
    "row, park",
    [
        # Trimmed of spaces around it.
        ('" Acadia ","1","291","US-ME"', Park("Acadia", True, "291", ("ME",))),
        ('"Old Park","0","291","US-ME"', Park("Old Park", False, "291", ("ME",))),
        # No entity, given either way.
        ('"Gone","0","","US-ME"', Park("Gone", False, "", ("ME",))),
        ('"Gone","0","0","US-ME"', Park("Gone", False, "", ("ME",))),
        # Several states, without US-.
        (
            '"Trail","1","291","US-DC,US-MD,US-WV"',
            Park("Trail", True, "291", ("DC", "MD", "WV")),
        ),
        # Outside the US, or a US location that isn't a state.
        ('"Rishiri","1","339","JA-01"', Park("Rishiri", True, "339", ())),
        ('"Kure","1","138","US-KI"', Park("Kure", True, "138", ())),
        ('"Blank","1","291",""', Park("Blank", True, "291", ())),
    ],
)
def test_park_as_listed(pota, folder, row, park):
    content = (
        b'"reference","name","active","entityId","locationDesc"\n'
        + f'"US-0001",{row}\n'.encode()
    )
    pota.content, pota.etag = content, md5_etag(content)
    download_parks(folder, pota.url)
    assert load_parks(folder) == {"US-0001": park}


def test_no_parks_without_a_sound_copy(pota, folder):
    assert load_parks(folder) == {}
    download_parks(folder, pota.url)
    (folder / PARKS_FILE).write_bytes(LIST + b"extra\n")
    assert load_parks(folder) == {}


@pytest.mark.parametrize(
    "content",
    [
        b'"ref","title"\n"US-0001","Acadia"\n',
        b'"reference","name","active","entityId","locationDesc"\n"US-0001","Acadia"\n',
    ],
)
def test_no_parks_from_a_list_not_shaped_like_potas(pota, folder, content):
    pota.content, pota.etag = content, md5_etag(content)
    download_parks(folder, pota.url)
    assert load_parks(folder) == {}
