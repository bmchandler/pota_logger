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
