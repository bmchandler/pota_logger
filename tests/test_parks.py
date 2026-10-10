import pytest

from pota_logger.parks import Park, listed_park, park_states, parse_park


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
        ("US-4566@US-WY", "US-4566@US-WY"),
        ("us4566@us-wy", "US-4566@US-WY"),
        ("1234@US-WY", "US-1234@US-WY"),
        ("VE-5082@CA-AB", "VE-5082@CA-AB"),
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
        "US-1234@",
        "US-1234@WY",
        "US-1234@US-WYOMI",
        "US-1234,US-1235",
    ],
)
def test_parse_park_rejects(text):
    with pytest.raises(ValueError, match="isn't a POTA park; use a form like"):
        parse_park(text)


@pytest.mark.parametrize("text", ["123456", "US-123456", "4x123456", "US-123456@US-WY"])
def test_parse_park_rejects_too_many_digits(text):
    with pytest.raises(ValueError, match="isn't a POTA park; parks must be <= 5 digits"):
        parse_park(text)


PARKS = {
    "US-0001": Park("Acadia National Park", True, "291", ("ME",)),
    "US-4566": Park("California National Historic Trail", True, "291", ("CA", "NV", "WY")),
    "JA-0001": Park("Rishiri-Rebun-Sarobetsu National Park", True, "339", ()),
}


@pytest.mark.parametrize(
    "park, reference",
    [("US-0001", "US-0001"), ("US-4566@US-WY", "US-4566"), ("US-9999", None)],
)
def test_listed_park(park, reference):
    assert listed_park(PARKS, park) == PARKS.get(reference)


@pytest.mark.parametrize(
    "park, states",
    [
        ("US-0001", ("ME",)),
        ("US-4566", ("CA", "NV", "WY")),
        # A location naming a state is where the operator said.
        ("US-4566@US-WY", ("WY",)),
        ("US-0001@CA-ON", ("ME",)),
        ("JA-0001", ()),
        ("US-9999", ()),
        ("US-9999@US-WY", ()),
    ],
)
def test_park_states(park, states):
    assert park_states(PARKS, park) == states
