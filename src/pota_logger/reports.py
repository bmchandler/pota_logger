THREE_DIGIT_MODE = "CW"

# (part of the report, lowest, highest) for each digit: RST.
DIGITS = [("readability", 1, 5), ("strength", 1, 9), ("tone", 1, 9)]


def parse_report(name: str, text: str, mode: str) -> str:
    """Parse SNT or RCD: 3 digits (599) when MODE is CW, 2 (59) otherwise, each in
    range: readability 1-5, strength 1-9, tone 1-9. Returned as entered.

    Raises ValueError with a message suitable for showing the operator.
    """
    report = text.strip()
    if not report.isdigit() or len(report) not in (2, 3):
        raise ValueError(f"{name} {report!r} should be 2 digits like 59, or 3 like 599 on CW")
    if len(report) == 3 and mode != THREE_DIGIT_MODE:
        raise ValueError(f"{name} {report!r} needs MODE CW for a 3-digit report")
    if len(report) == 2 and mode == THREE_DIGIT_MODE:
        raise ValueError(f"{name} {report!r} needs 3 digits on CW, like 599")
    for digit, (part, lowest, highest) in zip(report, DIGITS):
        if not lowest <= int(digit) <= highest:
            raise ValueError(
                f"{name} {report!r} isn't a real report: {part} is {lowest}-{highest}"
            )
    return report
