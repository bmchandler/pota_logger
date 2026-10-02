from textual.theme import Theme

# Outdoors palette: dark text on light leaf and grass greens, with a
# darker grass green for focus, and hunter and rust oranges for accents
# and warnings.
POTA_THEME = Theme(
    name="pota",
    primary="#6B8E4E",  # grass green
    secondary="#7D8F6E",  # sage (grey-green)
    accent="#D9772B",  # muted hunter orange
    warning="#EC9430",  # amber-leaning hunter orange
    error="#A8432F",  # brick red, kept apart from the oranges
    success="#9BBF6A",  # light green
    foreground="#1F2E17",  # deep forest
    background="#D2E6B5",  # light leaf green
    surface="#E8F3D8",  # pale new-leaf green
    panel="#AACD80",  # fresh grass
    dark=False,
)
