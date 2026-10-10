import os
from pathlib import Path

import pota_logger
from pota_logger.data_folder import (
    PROJECT_ROOT,
    README_TEXT,
    data_dir,
    from_source,
    user_data_home,
    write_readme,
)
from pota_logger.logbook import COLUMNS


def test_a_clone_keeps_its_data_in_the_projects_data_folder(tmp_path):
    (tmp_path / "pyproject.toml").write_text("")
    assert from_source(tmp_path)
    assert data_dir(tmp_path, {"XDG_DATA_HOME": "/xdg"}) == tmp_path / "data"


def test_this_checkout_runs_from_source():
    assert from_source()
    assert data_dir() == PROJECT_ROOT / "data"


def test_an_install_keeps_its_data_in_the_users_data_folder(tmp_path):
    # Installed, two folders up from the package is lib/, with no pyproject.toml.
    assert not from_source(tmp_path)
    assert data_dir(tmp_path, {}) == Path.home() / ".local/share/pota-logger/data"
    assert data_dir(tmp_path, {"XDG_DATA_HOME": "/xdg"}) == Path("/xdg/pota-logger/data")


def test_xdg_data_home_only_when_absolute():
    default = Path.home() / ".local" / "share"
    assert user_data_home({}) == default
    assert user_data_home({"XDG_DATA_HOME": ""}) == default
    # The XDG spec says to ignore a relative path.
    assert user_data_home({"XDG_DATA_HOME": "relative/share"}) == default
    assert user_data_home({"XDG_DATA_HOME": "/home/x/share"}) == Path("/home/x/share")


def test_readme_written_when_missing(tmp_path):
    folder = tmp_path / "pota-logger"
    write_readme(folder)
    assert (folder / "README.txt").read_text() == README_TEXT


def test_readme_rewritten_only_when_out_of_date(tmp_path):
    path = tmp_path / "README.txt"
    path.write_text("Old text, or edited.\n")
    write_readme(tmp_path)
    assert path.read_text() == README_TEXT
    os.utime(path, (0, 0))
    write_readme(tmp_path)
    assert path.stat().st_mtime == 0


def test_readme_not_written_is_no_problem(tmp_path):
    # A file where the folder should be: nothing written, nothing raised.
    (tmp_path / "pota-logger").write_text("")
    write_readme(tmp_path / "pota-logger")


def test_readme_header_row_is_the_logs():
    assert f"  {','.join(COLUMNS)}" in README_TEXT.splitlines()


class FakeApp:
    ran = False

    def run(self):
        FakeApp.ran = True


def test_installed_app_writes_the_readme_beside_data(tmp_path, monkeypatch):
    monkeypatch.setattr(pota_logger, "from_source", lambda: False)
    monkeypatch.setattr(pota_logger, "DATA_DIR", tmp_path / "pota-logger" / "data")
    monkeypatch.setattr(pota_logger, "PotaLoggerApp", FakeApp)
    pota_logger.main()
    assert FakeApp.ran
    assert (tmp_path / "pota-logger" / "README.txt").read_text() == README_TEXT


def test_app_from_a_clone_writes_no_readme(tmp_path, monkeypatch):
    monkeypatch.setattr(pota_logger, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(pota_logger, "PotaLoggerApp", FakeApp)
    pota_logger.main()
    assert not (tmp_path / "README.txt").exists()
