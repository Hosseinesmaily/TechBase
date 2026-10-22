"""Privacy: keep personal data out of the logs.

The assistant's logs contain the user's question, which may carry a name, a
phone number or an email address. The scrubber removes the obvious patterns
before anything is written.

It is a safety net, not a guarantee: it catches the shapes, not every possible
identifier. A user who types their national ID in a question is beyond what a
regex can fix — that is why the raw query is stored in the database (which the
editorial team can see) but not in the log lines.
"""

from __future__ import annotations

import re

#: An email address.
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
#: An Iranian mobile number (09xxxxxxxxx), with optional separators.
PHONE_RE = re.compile(r"(?:\+98|0098|0)?9\d{2}[\s-]?\d{3}[\s-]?\d{4}\b")
#: An Iranian national ID (10 digits, sometimes with dashes).
NATIONAL_ID_RE = re.compile(r"\b\d{3}[\s-]?\d{3}[\s-]?\d{4}\b")
#: A credit-card-like number (13–19 digits, with spaces or dashes).
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
#: An IP address.
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

#: What each pattern is replaced with.
REPLACEMENTS = {
    "email": "[email]",
    "phone": "[phone]",
    "national_id": "[national-id]",
    "card": "[card-number]",
    "ip": "[ip]",
}


def scrub(text: str) -> str:
    """Remove the personal data from a text."""
    if not text:
        return text
    scrubbed = EMAIL_RE.sub(REPLACEMENTS["email"], text)
    scrubbed = PHONE_RE.sub(REPLACEMENTS["phone"], scrubbed)
    scrubbed = CARD_RE.sub(REPLACEMENTS["card"], scrubbed)
    scrubbed = NATIONAL_ID_RE.sub(REPLACEMENTS["national_id"], scrubbed)
    scrubbed = IP_RE.sub(REPLACEMENTS["ip"], scrubbed)
    return scrubbed


def scrub_dict(data: dict) -> dict:
    """Scrub every string value of a dictionary."""
    return {key: scrub(value) if isinstance(value, str) else value for key, value in data.items()}
