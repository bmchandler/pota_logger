import pytest

from pota_logger_t3.freq import format_freq, parse_freq


@pytest.mark.parametrize(
    "text, hz",
    [
        ("14", 14_000_000),
        ("14.1", 14_100_000),
        ("14.12", 14_120_000),
        ("14.123", 14_123_000),
        ("14.123.4", 14_123_400),
        ("14.123.45", 14_123_450),
        ("14.123.456", 14_123_456),
        ("28312456", 28_312_456),
        ("7074000", 7_074_000),
        ("146.52", 146_520_000),
        ("3.985", 3_985_000),
        (" 14.074 ", 14_074_000),
    ],
)
def test_parse_freq(text, hz):
    assert parse_freq(text) == hz


@pytest.mark.parametrize(
    "text",
    [
        "",
        "abc",
        "14,074",
        "14.074.5.1",
        "14.074.",
        "14.",
        ".074",
        "14.0745",  # more than 3 digits after a dot
        "14.074.5555",
        "14074",  # 4-6 bare digits are ambiguous
        "1407",
        "140745",
        "0",
        "0.000",
        "-14",
    ],
)
def test_parse_freq_rejects(text):
    with pytest.raises(ValueError):
        parse_freq(text)


@pytest.mark.parametrize(
    "hz, text",
    [
        (14_000_000, "14.000.000"),
        (14_123_456, "14.123.456"),
        (14_074_500, "14.074.500"),
        (7_000_010, "7.000.010"),
        (146_520_000, "146.520.000"),
    ],
)
def test_format_freq(hz, text):
    assert format_freq(hz) == text
