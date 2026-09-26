import pytest

from pota_logger_t3.modes import parse_mode


@pytest.mark.parametrize(
    "text, mode",
    [
        ("SSB", "SSB"),
        ("usb", "USB"),
        ("Lsb", "LSB"),
        ("cw", "CW"),
        (" USB ", "USB"),
    ],
)
def test_parse_mode(text, mode):
    assert parse_mode(text) == mode


@pytest.mark.parametrize(
    "text",
    ["", "S", "U", "L", "C", "US", "SS", "FM", "AM", "FT8", "CWW", "USBX"],
)
def test_parse_mode_rejects(text):
    with pytest.raises(ValueError, match="should be SSB, USB, LSB, or CW"):
        parse_mode(text)
