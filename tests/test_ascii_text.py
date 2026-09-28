import pytest

from pota_logger_t3.ascii_text import check_ascii


@pytest.mark.parametrize(
    "text",
    ["", "59", "W1ABC", "RSGB Field Day Serial #042", """~!@#$%^&*()_+`-={}[]|\\:;"'<>,.?/"""],
)
def test_plain_ascii_passes(text):
    check_ascii("COMMENT", text, "")


def test_names_each_character_once_in_order_with_example():
    with pytest.raises(ValueError) as error:
        check_ascii("SNT", "٥٩٥", "59, or 599 on CW")
    assert str(error.value) == (
        "SNT '٥٩٥' has non-ASCII characters: '٥', '٩'.\nUse plain ASCII, like 59, or 599 on CW."
    )


def test_no_example_ends_after_the_characters():
    with pytest.raises(ValueError) as error:
        check_ascii("COMMENT", "Café", "")
    assert str(error.value) == "COMMENT 'Café' has non-ASCII characters: 'é'."


@pytest.mark.parametrize("text", ["５９", "5²", "20°F", "Nice “signal”", "73 🙂", "tab\there"])
def test_refuses_characters_outside_ascii_32_to_126(text):
    with pytest.raises(ValueError, match="has non-ASCII characters"):
        check_ascii("COMMENT", text, "")
