import pytest

from pota_logger.reports import parse_report


@pytest.mark.parametrize(
    "text, mode, report",
    [
        ("59", "SSB", "59"),
        (" 57 ", "USB", "57"),
        ("11", "LSB", "11"),
        ("599", "CW", "599"),
        ("111", "CW", "111"),
        ("579", "CW", "579"),
    ],
)
def test_parse_report(text, mode, report):
    assert parse_report("SNT", text, mode) == report


@pytest.mark.parametrize("text", ["", "5", "5x", "5 9", "5999", "-59", "5.9"])
def test_parse_report_rejects_shape(text):
    with pytest.raises(ValueError, match="should be 2 digits like 59, or 3 like 599 on CW"):
        parse_report("SNT", text, "CW")


def test_parse_report_rejects_two_digits_on_cw():
    with pytest.raises(ValueError, match="SNT '59' needs 3 digits on CW, like 599"):
        parse_report("SNT", "59", "CW")


def test_parse_report_rejects_three_digits_off_cw():
    with pytest.raises(ValueError, match="RCD '599' needs MODE CW for a 3-digit report"):
        parse_report("RCD", "599", "SSB")


@pytest.mark.parametrize(
    "text, part",
    [
        ("69", "readability is 1-5"),
        ("09", "readability is 1-5"),
        ("50", "strength is 1-9"),
        ("699", "readability is 1-5"),
        ("509", "strength is 1-9"),
        ("590", "tone is 1-9"),
    ],
)
def test_parse_report_rejects_out_of_range(text, part):
    mode = "CW" if len(text) == 3 else "SSB"
    with pytest.raises(ValueError, match=f"isn't a real report: {part}"):
        parse_report("SNT", text, mode)
