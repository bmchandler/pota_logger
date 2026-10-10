from pota_logger.fields.freq import band_name, format_freq, voice_range

# Room a sideband signal takes beside the logged (dial) frequency.
SIDEBAND_WIDTH = 3_000


def signal_edges(hz: int, mode: str) -> tuple[int, int]:
    """The (low, high) Hz a voice signal takes: USB above the dial, LSB
    below it. SSB is the standard sideband away from edges, so it's taken
    as just the dial frequency.
    """
    if mode == "USB":
        return hz, hz + SIDEBAND_WIDTH
    if mode == "LSB":
        return hz - SIDEBAND_WIDTH, hz
    return hz, hz


def check_sideband(hz: int, mode: str) -> None:
    """Refuse SSB within SIDEBAND_WIDTH of a voice range edge, where which
    sideband was used decides whether the signal stayed inside.

    Raises ValueError with a message suitable for showing the operator.
    """
    edges = voice_range(hz)
    if mode != "SSB" or edges is None:
        return
    low, high = edges
    if low <= hz < low + SIDEBAND_WIDTH or high - SIDEBAND_WIDTH < hz <= high:
        raise ValueError(
            f"SSB on {format_freq(hz)} is within 3 kHz of {band_name(hz)}'s voice edge; "
            "log USB or LSB"
        )
