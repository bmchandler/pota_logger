import subprocess

import pytest

from pota_logger_t3.callsign_guard import (
    HOOK_MARKER,
    added_lines,
    callsign_pattern,
    install,
    load_callsign,
    message_findings,
    staged_findings,
)
from pota_logger_t3.settings import Settings, save_settings

CALL = "W1TST"


@pytest.mark.parametrize(
    "text",
    ["W1TST", "w1tst", "de W1TST k", "VE3/W1TST", "W1TST/P", '"W1TST"', "call=W1TST,"],
)
def test_pattern_matches_callsign_on_its_own(text):
    assert callsign_pattern(CALL).search(text)


@pytest.mark.parametrize("text", ["XW1TST", "W1TST5", "W1TSTX", "W1TS", "W1 TST"])
def test_pattern_ignores_callsign_inside_other_text(text):
    assert not callsign_pattern(CALL).search(text)


def test_added_lines_tracks_files_and_line_numbers():
    diff = """\
diff --git a/a.txt b/a.txt
--- a/a.txt
+++ b/a.txt
@@ -3,0 +4,2 @@
+first
+second
diff --git a/b.txt b/b.txt
--- /dev/null
+++ b/b.txt
@@ -0,0 +1 @@
+only
"""
    assert added_lines(diff) == [("a.txt", 4, "first"), ("a.txt", 5, "second"), ("b.txt", 1, "only")]


def test_message_findings_skip_comments():
    message = f"Add thing\n\nWorked with {CALL}.\n# {CALL} in a comment\n"
    assert message_findings(CALL, message) == ["commit message line 3"]


def test_message_without_callsign_is_clean():
    assert message_findings(CALL, "Add thing\n\nNothing to see.\n") == []


def test_load_callsign_missing_settings_warns(tmp_path, capsys):
    assert load_callsign(tmp_path / "settings.toml") is None
    assert "not checking" in capsys.readouterr().err


def test_load_callsign_reads_settings(settings_path):
    save_settings(Settings(station_callsign=CALL), settings_path)
    assert load_callsign(settings_path) == CALL


@pytest.fixture
def repo(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.name", "test")
    git("config", "user.email", "test@example.invalid")
    (tmp_path / "old.txt").write_text(f"{CALL}\n")
    git("add", "old.txt")
    git("commit", "-q", "-m", "old", "--no-verify")
    return tmp_path, git


def test_staged_findings_reports_added_lines_only(repo):
    path, git = repo
    # Removing an existing mention is fine; adding one is not.
    (path / "old.txt").write_text("clean\n")
    (path / "new.txt").write_text(f"line one\nworked {CALL.lower()}\n")
    git("add", "old.txt", "new.txt")
    assert staged_findings(CALL, path) == ["new.txt:2"]


def test_staged_findings_checks_file_names(repo):
    path, git = repo
    (path / f"{CALL}_notes.txt").write_text("clean\n")
    git("add", ".")
    assert staged_findings(CALL, path) == [f"{CALL}_notes.txt (file name)"]


def test_install_writes_hooks_without_callsign(repo):
    path, _ = repo
    assert install(path) == 0
    for hook in ("pre-commit", "commit-msg"):
        text = (path / ".git" / "hooks" / hook).read_text()
        assert HOOK_MARKER in text
        assert "callsign_guard" in text
        assert (path / ".git" / "hooks" / hook).stat().st_mode & 0o111


def test_install_leaves_other_hooks_alone(repo):
    path, _ = repo
    (path / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\necho mine\n")
    assert install(path) == 1
    assert "mine" in (path / ".git" / "hooks" / "pre-commit").read_text()


def test_install_is_repeatable(repo):
    path, _ = repo
    assert install(path) == 0
    assert install(path) == 0
