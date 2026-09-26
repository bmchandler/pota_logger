import pytest

from pota_logger_t3.freq import US_BANDS, format_freq, in_us_band, parse_freq


@pytest.mark.parametrize(
    "text, hz",
    [
        # Dotted, zero-filled.
        ("14", 14_000_000),
        ("14.", 14_000_000),
        ("14.1", 14_100_000),
        ("14.12", 14_120_000),
        ("14.123", 14_123_000),
        ("14.123.4", 14_123_400),
        ("14.123.45", 14_123_450),
        ("14.123.456", 14_123_456),
        ("14.074.", 14_074_000),
        ("14.0745", 14_074_500),
        ("14.07450", 14_074_500),
        ("14.074500", 14_074_500),
        ("14.074123", 14_074_123),
        (" 14.074 ", 14_074_000),
        ("3.985", 3_985_000),
        ("1.81", 1_810_000),
        ("18.1", 18_100_000),
        ("5.3305", 5_330_500),
        ("0.1357", 135_700),
        ("0.475", 475_000),
        ("29.7", 29_700_000),
        # Bare digits: the MHz part is whichever split lands in a band.
        ("141501", 14_150_100),
        ("14074", 14_074_000),
        ("14074123", 14_074_123),
        ("28312456", 28_312_456),
        ("7074000", 7_074_000),
        ("7185", 7_185_000),
        ("3985", 3_985_000),
        ("101", 10_100_000),
        ("297", 29_700_000),
        ("21300", 21_300_000),
        ("1357", 135_700),
        ("475", 475_000),
    ],
)
def test_parse_freq(text, hz):
    assert parse_freq(text) == hz


@pytest.mark.parametrize(
    "text",
    [
        # Not a frequency.
        "",
        "abc",
        "14,074",
        "-14",
        ".074",
        "14.074.5.1",
        "14.07.45",  # second dot not after 3 kHz digits
        "14.0745.6",
        "14..074",
        "14.0745678",  # more than 6 fractional digits
        "14.074.5555",
        # Outside US bands.
        "0",
        "0.000",
        "15",
        "14.351",
        "29.701",
        "0.1356",
        "146.52",
        "146520",
    ],
)
def test_parse_freq_rejects(text):
    with pytest.raises(ValueError):
        parse_freq(text)


def test_out_of_band_message():
    with pytest.raises(ValueError, match="isn't in a US amateur band"):
        parse_freq("15")


@pytest.mark.parametrize("text", ["18100", "1810", "181"])
def test_bare_digits_in_two_bands_are_ambiguous(text):
    # 1.810.000 (160m) and 18.100.000 (17m) are both valid.
    with pytest.raises(ValueError, match=r"1\.810\.000 or 18\.100\.000; add a dot"):
        parse_freq(text)


def test_band_edges_are_inclusive():
    for low, high in US_BANDS:
        assert in_us_band(low) and in_us_band(high)
        assert not in_us_band(low - 1) and not in_us_band(high + 1)


@pytest.mark.parametrize(
    "hz, text",
    [
        (14_000_000, "14.000.000"),
        (14_123_456, "14.123.456"),
        (14_074_500, "14.074.500"),
        (7_000_010, "7.000.010"),
        (135_700, "0.135.700"),
    ],
)
def test_format_freq(hz, text):
    assert format_freq(hz) == text
