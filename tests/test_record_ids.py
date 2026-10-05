import pytest

from pota_logger.record_ids import EXAMPLE_ID, new_id, parse_id


def test_new_ids_are_version_4_and_differ():
    first, second = new_id(), new_id()
    assert parse_id(first) == first
    assert first != second


def test_example_id_is_valid():
    assert parse_id(EXAMPLE_ID) == EXAMPLE_ID


def test_uppercase_reads_as_lowercase():
    # As the UUID standard reads it, and as macOS's uuidgen writes it.
    assert parse_id(EXAMPLE_ID.upper()) == EXAMPLE_ID


@pytest.mark.parametrize(
    "text",
    [
        EXAMPLE_ID.replace("-", ""),
        "{" + EXAMPLE_ID + "}",
        "urn:uuid:" + EXAMPLE_ID,
        # Version 1, not 4.
        "1b4e28ba-2fa1-11d2-883f-0016d3cca427",
        # A version 4 nibble, but not the standard variant.
        "1b4e28ba-2fa1-4d2b-083f-0016d3cca427",
        EXAMPLE_ID[:-1],
        "not an id",
    ],
)
def test_only_the_form_the_app_writes_is_an_id(text):
    with pytest.raises(ValueError) as caught:
        parse_id(text)
    assert str(caught.value) == (
        f"UUIDv4 {text!r} should be a UUID as the app writes it, like {EXAMPLE_ID}"
    )
