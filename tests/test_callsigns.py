import pytest

from pota_logger_t3.callsigns import parse_callsign


@pytest.mark.parametrize(
    "text, callsign",
    [
        ("W1ABC", "W1ABC"),
        ("w1abc", "W1ABC"),
        (" w1abc ", "W1ABC"),
        ("VE3/w1abc/P", "VE3/W1ABC/P"),
    ],
)
def test_parse_callsign(text, callsign):
    assert parse_callsign(text) == callsign
