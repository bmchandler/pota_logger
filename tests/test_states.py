import pytest

from pota_logger_t3.states import US_STATES, parse_state


@pytest.mark.parametrize(
    "text, state",
    [
        ("NJ", "NJ"),
        ("nj", "NJ"),
        (" Nj ", "NJ"),
        ("DC", "DC"),
        ("AK", "AK"),
        ("NA", "NA"),
        ("na", "NA"),
        ("", ""),
        ("  ", ""),
    ],
)
def test_parse_state(text, state):
    assert parse_state(text) == state


@pytest.mark.parametrize("text", ["NN", "ZZ", "N", "NJX", "PR", "GU", "ON", "N.J."])
def test_parse_state_rejects(text):
    with pytest.raises(ValueError, match="isn't a US state"):
        parse_state(text)


def test_fifty_states_plus_dc():
    assert len(US_STATES) == 51
    assert all(len(code) == 2 and code.isupper() for code in US_STATES)
