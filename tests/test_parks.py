import pytest

from pota_logger.parks import parse_park


@pytest.mark.parametrize(
    "text, park",
    [
        ("1234", "US-1234"),
        (" 1234 ", "US-1234"),
        ("12345", "US-12345"),
        ("464", "US-0464"),
        ("7", "US-0007"),
        ("US-464", "US-0464"),
        ("us464", "US-0464"),
        ("JP-1234", "JP-1234"),
        ("jp-1234", "JP-1234"),
        ("CA-5678", "CA-5678"),
        ("jp234", "JP-0234"),
        ("JP234", "JP-0234"),
        ("K-5033", "K-5033"),
        ("4X-0012", "4X-0012"),
        ("4x12", "4X-0012"),
        ("9M2-1234", "9M2-1234"),
        ("ABCD-1234", "ABCD-1234"),
    ],
)
def test_parse_park(text, park):
    assert parse_park(text) == park


@pytest.mark.parametrize(
    "text",
    [
        "",
        "US-",
        "-1234",
        "ABCDE-1234",
        "12-1234",
        "US 1234",
        "US--1234",
        "Café",
        "US-１２３４",
        "US-1234,US-1235",
    ],
)
def test_parse_park_rejects(text):
    with pytest.raises(ValueError, match="isn't a POTA park; use a form like"):
        parse_park(text)


@pytest.mark.parametrize("text", ["123456", "US-123456", "4x123456"])
def test_parse_park_rejects_too_many_digits(text):
    with pytest.raises(ValueError, match="isn't a POTA park; parks must be <= 5 digits"):
        parse_park(text)


@pytest.mark.parametrize(
    "text", ["US-4566@US-WY", "us4566@us-wy", "1234@US-WY", "VE-5082@CA-AB", "US-1234@", "@"]
)
def test_parse_park_refuses_the_location_form(text):
    # ADIF's location is the export's to add, from ST.
    with pytest.raises(ValueError) as refused:
        parse_park(text)
    assert str(refused.value) == f"PARK {text!r}: @ form not accepted for input; ADIF export only"
