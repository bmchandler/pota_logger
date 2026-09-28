import pytest

from pota_logger_t3.comments import parse_comment


@pytest.mark.parametrize(
    "text, comment",
    [
        ("POTA US-1234 NC", "POTA US-1234 NC"),
        (" RSGB Field Day Serial #042 ", "RSGB Field Day Serial #042"),
        ("", ""),
        ("  ", ""),
        ("""~!@#$%^&*()_+`-={}[]|\\:;"'<>,.?/""", """~!@#$%^&*()_+`-={}[]|\\:;"'<>,.?/"""),
    ],
)
def test_parse_comment(text, comment):
    assert parse_comment(text) == comment


@pytest.mark.parametrize("text", ["Café", "20°F", "Nice “signal”", "73 🙂", "tab\there"])
def test_parse_comment_rejects_characters_outside_adif(text):
    with pytest.raises(ValueError, match="ADIF allows only plain keyboard characters"):
        parse_comment(text)


def test_rejection_names_each_character_once_in_order():
    with pytest.raises(ValueError, match=r"COMMENT can't include 'é', '°';"):
        parse_comment("é é 20°")
