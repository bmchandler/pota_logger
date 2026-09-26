import pytest

from pota_logger_t3.parks import format_park


@pytest.mark.parametrize(
    "text, park",
    [
        ("1234", "US-1234"),
        (" 1234 ", "US-1234"),
        ("JP-1234", "JP-1234"),
        ("CA-5678", "CA-5678"),
    ],
)
def test_format_park(text, park):
    assert format_park(text) == park
