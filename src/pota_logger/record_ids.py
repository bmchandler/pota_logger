from uuid import UUID, uuid4

# Shown as the form an ID takes.
EXAMPLE_ID = "1b4e28ba-2fa1-4d2b-883f-0016d3cca427"


def new_id() -> str:
    """A fresh record ID: a random UUID (version 4), as stored."""
    return str(uuid4())


def parse_id(text: str) -> str:
    """A record ID as the app writes it: a version 4 UUID with hyphens.
    Case is ignored, as the UUID standard reads it (macOS's uuidgen writes
    uppercase); it's returned lowercase, as stored. Raises ValueError if
    it isn't one.
    """
    try:
        valid = str(UUID(text)) == text.lower() and UUID(text).version == 4
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(f"UUIDv4 {text!r} should be a UUID as the app writes it, like {EXAMPLE_ID}")
    return text.lower()
