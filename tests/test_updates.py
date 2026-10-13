import json
import subprocess

import pytest

from pota_logger import updates
from pota_logger.updates import (
    InstallSource,
    check_for_release,
    install_source,
    newer_release,
    quiet_git_env,
    release_version,
    upgrade,
    version_key,
)

URL = "https://example.com/pota_logger"
COMMIT = "5f820a5879b3b82340c9db72f700eca907405a4f"


def direct_url(**vcs_info) -> str:
    """A `direct_url.json` as uv writes it for an install from git."""
    return json.dumps({"url": URL, "vcs_info": {"vcs": "git", "commit_id": COMMIT, **vcs_info}})


def ls_remote(*refs: str) -> str:
    return "".join(f"{COMMIT}\t{ref}\n" for ref in refs)


HEADS = ("refs/heads/dev", "refs/heads/main")
TAGS = ("refs/tags/2026.10.11", "refs/tags/2026.10.12.2", "refs/tags/2026.9.30", "refs/tags/MVP")
MAIN = InstallSource(URL, None)


def test_install_from_git_follows_the_default_branch_or_the_one_asked_for():
    assert install_source(direct_url()) == InstallSource(URL, None)
    assert install_source(direct_url(requested_revision="dev")) == InstallSource(URL, "dev")
    assert install_source(direct_url(requested_revision="")) == InstallSource(URL, None)


@pytest.mark.parametrize(
    "text",
    [
        None,
        "not json",
        "[]",
        # A clone run (`uv run`) is an editable install of a folder.
        json.dumps({"url": "file:///x", "dir_info": {"editable": True}}),
        json.dumps({"url": URL, "vcs_info": {"vcs": "hg"}}),
        json.dumps({"vcs_info": {"vcs": "git"}}),
        json.dumps({"url": URL, "vcs_info": []}),
    ],
)
def test_no_source_without_an_install_from_git(text):
    assert install_source(text) is None


def test_versions_compare_by_number():
    assert version_key("2026.9.30") < version_key("2026.10.1")
    assert version_key("2026.10.12") < version_key("2026.10.12.1") < version_key("2026.10.13")


def test_a_dev_version_follows_its_release():
    assert release_version("2026.10.12.2+dev") == "2026.10.12.2"
    assert release_version("2026.10.12") == "2026.10.12"


def test_newest_release_tag_if_newer():
    output = ls_remote(*HEADS, *TAGS)
    assert newer_release(output, MAIN, "2026.10.11") == "2026.10.12.2"
    assert newer_release(output, MAIN, "2026.10.12.2") is None
    assert newer_release(output, MAIN, "2026.10.13") is None


def test_a_dev_build_is_compared_by_the_release_it_follows():
    output = ls_remote(*HEADS, *TAGS)
    dev = InstallSource(URL, "dev")
    assert newer_release(output, dev, "2026.10.11+dev") == "2026.10.12.2"
    assert newer_release(output, dev, "2026.10.12.2+dev") is None


@pytest.mark.parametrize("revision", ["2026.10.11", COMMIT, COMMIT[:8]])
def test_an_install_from_a_tag_or_commit_isnt_checked(revision):
    # `uv tool upgrade` doesn't move it.
    output = ls_remote(*HEADS, *TAGS)
    assert newer_release(output, InstallSource(URL, revision), "2026.10.11") is None


def test_only_release_tags_count():
    assert newer_release(ls_remote(*HEADS, "refs/tags/MVP", "refs/tags/v2"), MAIN, "2026.10.11") is None


def test_a_version_not_a_release_isnt_compared():
    assert newer_release(ls_remote(*HEADS, *TAGS), MAIN, "0.1.0.dev1") is None


def test_check_lists_the_repositorys_tags(releases):
    url = releases("MVP", "2026.10.11", "2026.10.12")
    assert check_for_release(InstallSource(url, None), "2026.10.11") == "2026.10.12"
    assert check_for_release(InstallSource(url, "dev"), "2026.10.11+dev") == "2026.10.12"
    assert check_for_release(InstallSource(url, None), "2026.10.12") is None


def test_check_that_cant_reach_the_repository_is_no_news(tmp_path):
    missing = (tmp_path / "missing").as_uri()
    assert check_for_release(InstallSource(missing, None), "2026.10.11") is None


def test_check_without_git_is_no_news(releases, monkeypatch):
    url = releases("2026.10.12")
    monkeypatch.setattr(updates.shutil, "which", lambda name: None)
    assert check_for_release(InstallSource(url, None), "2026.10.11") is None


def test_check_that_takes_too_long_is_no_news(monkeypatch):
    def run(command, **kwargs):
        assert kwargs["timeout"] == updates.CHECK_TIMEOUT_SECONDS
        # Away from the terminal, and given nothing to read from it.
        assert kwargs["start_new_session"]
        assert kwargs["stdin"] == subprocess.DEVNULL
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(updates.subprocess, "run", run)
    assert check_for_release(MAIN, "2026.10.11") is None


def test_git_never_asks_and_gives_up_when_stalled():
    env = quiet_git_env({"PATH": "/bin"})
    assert env["PATH"] == "/bin"
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_HTTP_LOW_SPEED_LIMIT"] == "1000"
    assert env["GIT_HTTP_LOW_SPEED_TIME"] == "10"
    assert env["GIT_SSH_COMMAND"] == "ssh -o BatchMode=yes -o ConnectTimeout=10"


def test_the_operators_own_ssh_command_is_kept():
    assert quiet_git_env({"GIT_SSH_COMMAND": "ssh -i key"})["GIT_SSH_COMMAND"] == "ssh -i key"


def test_upgrade_runs_uv(monkeypatch):
    commands = []
    monkeypatch.setattr(updates.subprocess, "run", lambda command, **kwargs: commands.append(command))
    upgrade()
    assert commands == [["uv", "tool", "upgrade", "pota-logger"]]


@pytest.mark.parametrize("error", [KeyboardInterrupt, FileNotFoundError])
def test_upgrade_stopped_or_failed_ends_quietly(monkeypatch, error):
    def run(command, **kwargs):
        raise error

    monkeypatch.setattr(updates.subprocess, "run", run)
    upgrade()
