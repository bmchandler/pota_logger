import importlib.util
import subprocess
import tomllib
from datetime import date
from pathlib import Path

import pytest

# The script sits in the project root, outside the package.
spec = importlib.util.spec_from_file_location(
    "tag_new_version", Path(__file__).parent.parent / "tag_new_version.py"
)
tnv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tnv)


@pytest.mark.parametrize("text", ["2026.10.10", "2026.1.5", "2026.10.10.1", "2026.12.31.12"])
def test_versions_read(text):
    assert ".".join(map(str, tnv.parse_version(text))) == text


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("2026.01.05", "no leading zeros"),
        ("2026.1.05", "no leading zeros"),
        ("2026.10.10.0", "no leading zeros"),
        ("v2026.10.10", "no leading zeros"),
        ("0.2.0", "no leading zeros"),
        ("2026.10", "no leading zeros"),
        ("MVP", "no leading zeros"),
        ("2026.2.30", "isn't a real date"),
        ("2026.13.1", "isn't a real date"),
    ],
)
def test_versions_refused(text, message):
    with pytest.raises(ValueError, match=message):
        tnv.parse_version(text)


def test_next_version_is_today():
    assert tnv.next_version(date(2026, 1, 5), ["2025.12.31"]) == "2026.1.5"


def test_next_version_counts_releases_the_same_day():
    assert tnv.next_version(date(2026, 10, 10), ["2026.10.10"]) == "2026.10.10.1"
    assert tnv.next_version(date(2026, 10, 10), ["2026.10.10", "2026.10.10.1"]) == "2026.10.10.2"


def test_given_version_already_tagged_or_older_is_refused():
    tags = ["2026.10.10", "2026.10.12"]
    tnv.check_version("2026.10.12.1", tags)
    with pytest.raises(ValueError, match="already tagged"):
        tnv.check_version("2026.10.12", tags)
    with pytest.raises(ValueError, match="older than the newest tag, 2026.10.12"):
        tnv.check_version("2026.10.11", tags)


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A git repo on main with a small uv project, no dependencies."""
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.com")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n'
        'requires-python = ">=3.13"\ndependencies = []\n'
    )
    (tmp_path / ".gitignore").write_text(".venv/\n")
    subprocess.run(["uv", "lock", "-q"], cwd=tmp_path, check=True)
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "Initial Commit")
    git(tmp_path, "tag", "MVP")
    return tmp_path


def test_clean_main_has_no_problems(repo):
    assert tnv.repo_problems(repo) == []
    assert tnv.version_tags(repo) == []


def test_changes_or_another_branch_refused(repo):
    (repo / "notes.txt").write_text("x")
    git(repo, "switch", "-q", "-c", "other")
    assert tnv.repo_problems(repo) == [
        "On branch other, not main.",
        "The tree has changes; commit or stash them first.",
    ]


def test_release_commits_the_version_and_tags_that_commit(repo):
    tnv.release("2026.10.10", repo)
    with open(repo / "pyproject.toml", "rb") as file:
        assert tomllib.load(file)["project"]["version"] == "2026.10.10"
    assert 'version = "2026.10.10"' in (repo / "uv.lock").read_text()
    assert git(repo, "log", "-1", "--format=%s") == "Version 2026.10.10"
    assert git(repo, "show", "--name-only", "--format=", "HEAD").split() == [
        "pyproject.toml",
        "uv.lock",
    ]
    assert git(repo, "rev-parse", "2026.10.10") == git(repo, "rev-parse", "HEAD")
    assert tnv.repo_problems(repo) == []
    assert tnv.version_tags(repo) == ["2026.10.10"]
