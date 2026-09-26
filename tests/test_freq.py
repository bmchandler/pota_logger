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
        ("14074", 14_074_000),
        ("14074123", 14_074_123),
        ("7185", 7_185_000),
        ("146520", 146_520_000),
        ("146.52", 146_520_000),
        ("3.985", 3_985_000),
        (" 14.074 ", 14_074_000),
        # Fraction without a second dot, zero-filled to 6 digits.
        ("14.0745", 14_074_500),
        ("14.07450", 14_074_500),
        ("14.074500", 14_074_500),
        ("14.074123", 14_074_123),
        # Trailing dots just mean "nothing more".
        ("14.", 14_000_000),
        ("14.074.", 14_074_000),
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
        ".074",
        "14.07.45",  # second dot not after 3 kHz digits
        "14.0745.6",
        "14..074",
        "14.0745678",  # more than 6 fractional digits
        "14.074.5555",
        "0",
        "0000",
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
