from pota_logger.screens.warning_screen import WarningScreen

# As dictated.
PARKS_OFFER = (
    "Download POTA's parks list (about 9 MB)?\n"
    "It lets the app fill in ST, show park names,\n"
    "and warn on a park not in the list.\n"
    "You can download it later in Settings (f2).\n"
    "Esc to skip, or download with Enter."
)


class ParksOfferScreen(WarningScreen):
    """Offer POTA's parks list at first start, once the station callsign
    is saved. Dismisses with True to download, or False (Esc, Skip).
    """

    # Wider than a warning, so the lines as dictated fit unwrapped.
    DEFAULT_CSS = """
    ParksOfferScreen > Vertical {
        width: 50;
    }
    """

    def __init__(self) -> None:
        super().__init__(PARKS_OFFER, confirm_label="Download", back_label="Skip")
