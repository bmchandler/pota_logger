import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pota_logger.app import PotaLoggerApp
from pota_logger.parks_list import md5_etag
from pota_logger.settings import Settings, save_settings


@pytest.fixture
def settings_path(tmp_path):
    """Settings file in a temp dir, so tests never touch the real data/.
    Not written yet, so an app started on it has no station callsign.
    """
    return tmp_path / "data" / "settings.toml"


@pytest.fixture
def app(settings_path):
    """The app with station callsign W1TST set, as entries need one."""
    save_settings(Settings(station_callsign="W1TST"), settings_path)
    return PotaLoggerApp(settings_path=settings_path)


# A short POTA parks list, as the fake server serves it.
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
def releases(tmp_path):
    """Make a local git repository with `main` and `dev` and the tags
    given, standing in for the app's own, so the check for a newer
    release never reaches the network; gives its URL.
    """

    def make(*tags: str) -> str:
        repo = tmp_path / "repo"
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")

        def git(*args: str) -> None:
            subprocess.run(["git", "-C", str(repo), *args], env=env, check=True, capture_output=True)

        repo.mkdir()
        git("init", "-b", "main")
        git("-c", "user.name=Test", "-c", "user.email=test@example.com",
            "commit", "--allow-empty", "-m", "Initial Commit")
        git("branch", "dev")
        for tag in tags:
            git("tag", tag)
        return repo.as_uri()

    return make
