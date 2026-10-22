"""A logging filter that scrubs the personal data out of the messages.

It is installed on the root logger when `SCRUB_LOGS` is on, so a message that
accidentally carries an email address never reaches the log file.
"""

from __future__ import annotations

import logging

from django.conf import settings

from .privacy import scrub


class ScrubFilter(logging.Filter):
    """Remove the personal data from a log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(settings, "SCRUB_LOGS", True):
            return True
        try:
            message = record.getMessage()
        except Exception:
            return True
        scrubbed = scrub(message)
        if scrubbed != message:
            record.msg = scrubbed
            record.args = ()
        return True
