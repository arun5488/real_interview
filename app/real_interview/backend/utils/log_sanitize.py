import logging
import re
from typing import Any

_EMAIL_IN_TEXT = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    re.IGNORECASE,
)


def mask_email(email: str) -> str:
    """Mask an email for logs, keeping the domain visible."""
    if not isinstance(email, str):
        return "***"
    raw = email.strip()
    if not raw or "@" not in raw:
        return "***"
    local, _, domain = raw.partition("@")
    if not local or not domain:
        return "***"
    masked_local = "*" if len(local) <= 1 else f"{local[0]}***"
    return f"{masked_local}@{domain}"


def mask_for_log(text: str) -> str:
    """Replace email addresses embedded in arbitrary log text."""
    if not isinstance(text, str) or not text:
        return text or ""

    return _EMAIL_IN_TEXT.sub(lambda match: mask_email(match.group(0)), text)


def _mask_log_value(value: Any) -> Any:
    if isinstance(value, str):
        return mask_for_log(value)
    return value


class EmailMaskingFilter(logging.Filter):
    """Strip or mask email addresses from log records before they are written."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_for_log(record.msg)

        args = record.args
        if isinstance(args, dict):
            record.args = {key: _mask_log_value(value) for key, value in args.items()}
        elif isinstance(args, tuple):
            record.args = tuple(_mask_log_value(value) for value in args)

        return True
