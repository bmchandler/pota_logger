# ADIF's characters: ASCII 32 (space) to 126 (~), every character on a US
# keyboard. Checked on every field before its own rules, since look-alikes
# (５ for 5, é for e, curly quotes) would otherwise get a confusing message.
ASCII_CHARACTERS = {chr(code) for code in range(32, 127)}


def check_ascii(name: str, text: str, example: str = "") -> None:
    """Refuse text with characters outside ASCII 32-126, naming them.

    Raises ValueError with a message suitable for showing the operator,
    ending with the example of plain ASCII, if given.
    """
    # Each character once, in the order they appear.
    others = [c for c in dict.fromkeys(text) if c not in ASCII_CHARACTERS]
    if not others:
        return
    listed = ", ".join(repr(character) for character in others)
    message = f"{name} {text!r} has non-ASCII characters: {listed}."
    if example:
        message += f"\nUse plain ASCII, like {example}."
    raise ValueError(message)


def check_trimmed(name: str, text: str) -> None:
    """Refuse spaces before or after a value read from a data file, which
    the app never saves: a hand edit is held to exactly what's saved.

    Raises ValueError with a message suitable for showing the operator.
    """
    trimmed = text.strip()
    if text == trimmed:
        return
    if not trimmed:
        raise ValueError(f"{name} {text!r} should be empty, with no spaces")
    raise ValueError(f"{name} {text!r} should have no spaces around it, like {trimmed}")
