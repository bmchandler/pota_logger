import subprocess

import pytest

import branch_guard
from pota_logger.callsign_guard import install as install_callsign_guard
from pota_logger.git_hooks import HEADER

ZERO = "0" * 40


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A repo with a release tagged on main, and dev a commit ahead."""
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "commit", "-q", "--allow-empty", "-m", "Version 2026.10.10")
    git(tmp_path, "tag", "2026.10.10")
    git(tmp_path, "tag", "MVP")
    git(tmp_path, "switch", "-q", "-c", "dev")
    git(tmp_path, "commit", "-q", "--allow-empty", "-m", "Work")
    return tmp_path


def test_commits_on_dev_allowed(repo):
    assert branch_guard.commit_problems(repo) == []


def test_commits_on_main_refused(repo):
    git(repo, "switch", "-q", "main")
    assert branch_guard.commit_problems(repo) == [
        "On main, which only moves to a release: commit on dev instead."
    ]


def update(repo, local_ref, rev, remote_ref):
    commit = git(repo, "rev-parse", rev) if rev else ZERO
    return f"{local_ref} {commit} {remote_ref} {ZERO}\n"


def test_pushing_main_to_a_release_allowed(repo):
    updates = update(repo, "refs/heads/main", "main", "refs/heads/main")
    updates += update(repo, "refs/heads/dev", "dev", "refs/heads/dev")
    updates += update(repo, "refs/tags/2026.10.10", "2026.10.10", "refs/tags/2026.10.10")
    assert branch_guard.push_problems(updates, repo) == []


def test_pushing_main_to_anything_but_a_release_refused(repo):
    dev = git(repo, "rev-parse", "dev")
    assert branch_guard.push_problems(update(repo, "refs/heads/dev", "dev", "refs/heads/main"), repo) == [
        f"refs/heads/dev ({dev[:8]}) to main: no release tag points at it."
    ]
    # A tag that isn't a release's doesn't count.
    git(repo, "tag", "-f", "MVP", "dev")
    assert len(branch_guard.push_problems(update(repo, "refs/heads/dev", "dev", "refs/heads/main"), repo)) == 1


def test_deleting_main_refused(repo):
    assert branch_guard.push_problems(update(repo, "(delete)", None, "refs/heads/main"), repo) == [
        "That would delete main on the remote."
    ]


def test_hooks_installed_beside_the_callsign_guards(repo):
    assert install_callsign_guard(repo) == 0
    assert branch_guard.install(repo) == 0
    hooks = repo / ".git" / "hooks"
    pre_commit = (hooks / "pre-commit").read_text()
    assert pre_commit.startswith(HEADER)
    assert "pota_logger.callsign_guard pre-commit" in pre_commit
    assert "test ! -f branch_guard.py || uv run --quiet branch_guard.py pre-commit" in pre_commit
    assert "branch_guard.py pre-push" in (hooks / "pre-push").read_text()
    assert "branch_guard" not in (hooks / "commit-msg").read_text()
    # Installing again changes nothing.
    assert branch_guard.install(repo) == 0
    assert install_callsign_guard(repo) == 0
    assert (hooks / "pre-commit").read_text() == pre_commit
