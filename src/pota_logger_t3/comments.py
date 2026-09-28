# ADIF's String type: ASCII 32 (space) to 126 (~), which is every character
# on a US keyboard.
ADIF_CHARACTERS = {chr(code) for code in range(32, 127)}


def parse_comment(text: str) -> str:
    """Parse COMMENT: free text, possibly blank, in ADIF's characters.

    Raises ValueError with a message suitable for showing the operator.
    """
    comment = text.strip()
    # Each character once, in the order they appear.
    others = [c for c in dict.fromkeys(comment) if c not in ADIF_CHARACTERS]
    if others:
        listed = ", ".join(repr(character) for character in others)
        raise ValueError(
            f"COMMENT can't include {listed}; ADIF allows only plain keyboard characters"
        )
    return comment
