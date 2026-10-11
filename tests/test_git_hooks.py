import os
import subprocess

from pota_logger.git_hooks import HEADER, add_hook_line, hook_line


def test_first_guard_writes_the_file(tmp_path):
    path = tmp_path / "pre-commit"
    assert add_hook_line(path, "guard-a check", "guard a")
    assert path.read_text() == HEADER + "guard-a check || exit $?  # guard a\n"
    assert os.access(path, os.X_OK)


def test_each_guard_keeps_to_its_own_line(tmp_path):
    path = tmp_path / "pre-commit"
    add_hook_line(path, "guard-a check", "guard a")
    add_hook_line(path, "guard-b check", "guard b")
    add_hook_line(path, "guard-a check --new", "guard a")
    assert path.read_text() == HEADER + "\n".join(
        [hook_line("guard-a check --new", "guard a"), hook_line("guard-b check", "guard b")]
    ) + "\n"


def test_another_tools_hook_left_alone(tmp_path):
    path = tmp_path / "pre-commit"
    path.write_text("#!/bin/sh\necho mine\n")
    assert not add_hook_line(path, "guard-a check", "guard a")
    assert path.read_text() == "#!/bin/sh\necho mine\n"


def test_a_guards_file_from_before_sharing_is_replaced(tmp_path):
    path = tmp_path / "pre-commit"
    path.write_text("#!/bin/sh\n# guard a\nexec guard-a check\n")
    assert add_hook_line(path, "guard-a check", "guard a")
    assert path.read_text() == HEADER + "guard-a check || exit $?  # guard a\n"
    # Another guard doesn't take it for its own.
    path.write_text("#!/bin/sh\n# guard a\nexec guard-a check\n")
    assert not add_hook_line(path, "guard-b check", "guard b")


def run_hook(path, *, a_exit, b_exit):
    """Run the hook file with each guard's command a shell exit."""
    add_hook_line(path, f"(exit {a_exit})", "guard a")
    add_hook_line(path, f"(exit {b_exit})", "guard b")
    return subprocess.run([path]).returncode


def test_the_hook_stops_at_the_first_guard_that_refuses(tmp_path):
    path = tmp_path / "pre-commit"
    assert run_hook(path, a_exit=0, b_exit=0) == 0
    assert run_hook(path, a_exit=1, b_exit=0) == 1
    assert run_hook(path, a_exit=0, b_exit=3) == 3
