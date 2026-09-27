import pytest

from pota_logger_t3.callsigns import is_usual_callsign, parse_callsign


@pytest.mark.parametrize(
    "text, callsign",
    [
        ("W1ABC", "W1ABC"),
        ("w1abc", "W1ABC"),
        (" w1abc ", "W1ABC"),
        ("K1A", "K1A"),
        ("2E0ABC", "2E0ABC"),
        ("3D2XYZ", "3D2XYZ"),
        ("9A1AA", "9A1AA"),
        ("W100AW", "W100AW"),
        ("GB250RSGB", "GB250RSGB"),
        ("W1ABC/P", "W1ABC/P"),
        ("W1ABC/QRP", "W1ABC/QRP"),
        ("W1ABC/4", "W1ABC/4"),
        ("VE3/W1ABC", "VE3/W1ABC"),
        ("VP2E/W1ABC", "VP2E/W1ABC"),
        ("VE3/w1abc/P", "VE3/W1ABC/P"),
    ],
)
def test_parse_callsign(text, callsign):
    assert parse_callsign(text) == callsign


@pytest.mark.parametrize("text", ["W1ABC.", "W1 ABC", "W1-ABC", "W1ABC\\P"])
def test_parse_callsign_rejects_characters(text):
    with pytest.raises(ValueError, match="only use letters, digits, and /"):
        parse_callsign(text)


def test_parse_callsign_rejects_too_many_slashes():
    with pytest.raises(ValueError, match="more than 2 slashes"):
        parse_callsign("VE3/W1ABC/P/M")


@pytest.mark.parametrize("text", ["W1ABC/", "/W1ABC", "VE3//W1ABC"])
def test_parse_callsign_rejects_empty_parts(text):
    with pytest.raises(ValueError, match="empty part"):
        parse_callsign(text)


@pytest.mark.parametrize("text", ["WABC", "W1", "123", "VE3/P", "ABC/4"])
def test_parse_callsign_rejects_non_calls(text):
    with pytest.raises(ValueError, match="doesn't look like a callsign"):
        parse_callsign(text)


@pytest.mark.parametrize(
    "call",
    [
        "W1ABC",
        "K1A",
        "KD2XYZ",
        "KH6ABC",
        "IK2ABC",
        "G4ABC",
        "M0ABC",
        "VE3XYZ",
        "JA1ABC",
        "DL1ABC",
        "HB9ABC",
        "9A1AA",
        "3D2XYZ",
        "2E0ABC",
        "S51ABC",
        "4U1ITU",
        "VP2EAB",
        "W1ABC/P",
        "VE3/W1ABC/P",
    ],
)
def test_usual_callsigns(call):
    assert is_usual_callsign(call)


@pytest.mark.parametrize(
    "call", ["W11BC", "W1ABCDE", "W100AW", "GB250RSGB", "3DA0ABC", "VE3/W11BC", "W11BC/P"]
)
def test_unusual_callsigns(call):
    assert not is_usual_callsign(call)
