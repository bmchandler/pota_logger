import pytest

from pota_logger_t3.sidebands import check_sideband, signal_edges


def test_signal_edges():
    assert signal_edges(21_300_000, "USB") == (21_300_000, 21_303_000)
    assert signal_edges(7_200_000, "LSB") == (7_197_000, 7_200_000)
    assert signal_edges(14_285_000, "SSB") == (14_285_000, 14_285_000)


@pytest.mark.parametrize(
    "hz, mode",
    [
        (21_300_000, "SSB"),
        (21_203_000, "SSB"),  # 3 kHz clear: either sideband fits
        (21_447_000, "SSB"),
        (21_200_000, "USB"),
        (21_200_000, "LSB"),  # a warning, not a block
        (21_450_000, "USB"),
        (14_074_000, "SSB"),  # below the voice range: a warning, not a block
        (10_120_000, "SSB"),  # 30m has no voice range: a warning
        (21_200_000, "CW"),
    ],
)
def test_check_sideband_allows(hz, mode):
    check_sideband(hz, mode)


@pytest.mark.parametrize(
    "hz", [21_200_000, 21_202_999, 21_447_001, 21_450_000, 7_125_000, 7_300_000, 28_300_000]
)
def test_check_sideband_refuses_ssb_near_edge(hz):
    with pytest.raises(ValueError, match="within 3 kHz of .*'s voice edge; log USB or LSB"):
        check_sideband(hz, "SSB")


def test_check_sideband_message():
    with pytest.raises(ValueError) as error:
        check_sideband(21_450_000, "SSB")
    assert str(error.value) == (
        "SSB on 21.450.000 is within 3 kHz of 15m's voice edge; log USB or LSB"
    )
