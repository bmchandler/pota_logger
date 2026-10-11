import json

from pota_logger.app_version import app_version, installed_commit, is_dev, package_version, reported_version

COMMIT = "5f820a5879b3b82340c9db72f700eca907405a4f"


def direct_url(**info) -> str:
    """A `direct_url.json` as uv writes it for an install from git."""
    return json.dumps({"url": "https://example.com/pota_logger.git", "vcs_info": info})


def test_dev_versions_are_the_dev_branchs():
    assert is_dev("2026.10.12+dev")
    assert not is_dev("2026.10.12")
    assert not is_dev("2026.10.12.1")


def test_commit_read_from_a_git_install():
    assert installed_commit(direct_url(vcs="git", commit_id=COMMIT, requested_revision="dev")) == COMMIT


def test_no_commit_without_a_git_install():
    assert installed_commit(None) is None
    # A clone run (`uv run`) is an editable install of a folder.
    assert installed_commit(json.dumps({"url": "file:///x", "dir_info": {"editable": True}})) is None
    assert installed_commit(direct_url(vcs="git")) is None
    assert installed_commit(direct_url(vcs="git", commit_id="dev")) is None
    assert installed_commit("not json") is None
    assert installed_commit("[]") is None


def test_a_dev_build_from_git_reports_its_short_commit():
    assert reported_version("2026.10.12+dev", direct_url(vcs="git", commit_id=COMMIT)) == (
        "2026.10.12+dev.5f820a58"
    )


def test_a_dev_build_without_a_commit_reports_its_version():
    assert reported_version("2026.10.12+dev", None) == "2026.10.12+dev"


def test_a_release_reports_its_date_even_installed_from_git():
    assert reported_version("2026.10.12", direct_url(vcs="git", commit_id=COMMIT)) == "2026.10.12"


def test_this_clone_reports_its_version_as_written():
    # An editable install, with no commit recorded.
    assert app_version() == package_version()
