"""Meeting-notes helpers: deterministic filename derivation.

The meeting-notes capability (specs/meeting-notes) fixes the output location to
docs/meetings/<date>-<topic>.md. This module owns that path rule so the scenario
test and any future pipeline agree on the exact name.
"""
from __future__ import annotations

import re

_CJK = r"一-鿿㐀-䶿豈-﫿"
_UNSAFE = re.compile(f"[^{_CJK}a-zA-Z0-9]+")


def slugify_topic(topic: str) -> str:
    """Slugify a meeting topic for a filename: keep CJK and ASCII alphanumerics,
    collapse every other run (spaces, path separators, punctuation) to a single
    '-', and strip leading/trailing separators so the result is path-traversal
    safe."""
    return _UNSAFE.sub("-", topic.strip()).strip("-")


def meeting_filename(meeting_date: str, topic: str) -> str:
    """Return the deterministic minutes path: docs/meetings/<date>-<topic>.md.

    meeting_date is expected as YYYY-MM-DD — the meeting's date as stated or
    implied in the material, or the current date when the material gives none.
    Both parts are slugified; an empty part falls back to a placeholder.
    """
    date_part = slugify_topic(meeting_date) or "unknown-date"
    topic_part = slugify_topic(topic) or "meeting"
    return f"docs/meetings/{date_part}-{topic_part}.md"
