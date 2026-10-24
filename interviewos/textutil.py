from __future__ import annotations

import re
from datetime import datetime, timezone

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

OPT_OUT = ("unsubscribe", "stop emailing", "not interested", "do not contact", "remove me")
POSITIVE = ("yes", "interested", "happy to", "let's talk", "lets talk", "free to chat", "sounds good")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_email(value: str | None) -> bool:
    if not value:
        return False
    return EMAIL_RE.match(value.strip()) is not None


def excerpt_in_source(excerpt: str, source: str) -> bool:
    needle = " ".join(excerpt.split())
    haystack = " ".join(source.split())
    return bool(needle) and needle in haystack


def classify_reply(text: str, agreed_time: str | None) -> str:
    """Map a reply to a case state. A time must be explicit to confirm a meeting."""
    lowered = (text or "").lower()
    if any(phrase in lowered for phrase in OPT_OUT):
        return "closed"
    if agreed_time and agreed_time.strip():
        return "meeting_confirmed"
    if any(phrase in lowered for phrase in POSITIVE):
        return "replied"
    if text and text.strip():
        return "replied"
    return "replied"
