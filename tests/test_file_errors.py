from datetime import UTC, datetime

from pota_logger import file_errors

NOW = datetime(2026, 10, 5, 21, 3, 30, tzinfo=UTC)


def test_errors_written_one_per_line_under_a_header(tmp_path):
    path = file_errors.record(tmp_path, ["first problem", "second problem"], NOW)
    assert path == tmp_path / "file_errors.txt"
    assert path.read_text() == (
        "Written by pota-logger at start, 2026-10-05 21:03 UTC.\n"
        "Fix these by hand, then start the app again.\n"
        "\n"
        "first problem\n"
        "second problem\n"
    )


def test_rewritten_each_time(tmp_path):
    file_errors.record(tmp_path, ["old problem"], NOW)
    path = file_errors.record(tmp_path, ["new problem"], NOW)
    assert path.read_text().splitlines()[3:] == ["new problem"]


def test_removed_with_no_errors(tmp_path):
    file_errors.record(tmp_path, ["problem"], NOW)
    path = file_errors.record(tmp_path, [], NOW)
    assert not path.exists()


def test_nothing_to_remove_is_fine(tmp_path):
    assert not file_errors.record(tmp_path / "missing", [], NOW).exists()
