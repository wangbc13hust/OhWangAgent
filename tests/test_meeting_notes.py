"""Unit tests for the meeting-notes filename helpers."""

from ohwang.services.meeting_notes import meeting_filename, slugify_topic


def test_slugify_keeps_cjk_and_alnum():
    assert slugify_topic("周会") == "周会"
    assert slugify_topic("Release v0.4 周会") == "Release-v0-4-周会"


def test_slugify_collapses_path_separators():
    # Path separators and dots must never survive into a filename.
    assert slugify_topic("../周会/纪要") == "周会-纪要"
    assert slugify_topic("a..b/..\\c") == "a-b-c"


def test_slugify_strips_edges():
    assert slugify_topic("  周会  ") == "周会"
    assert slugify_topic("---周会---") == "周会"


def test_slugify_empty_returns_empty():
    assert slugify_topic("") == ""
    assert slugify_topic("///") == ""


def test_meeting_filename_format():
    assert meeting_filename("2026-08-02", "周会") == "docs/meetings/2026-08-02-周会.md"


def test_meeting_filename_sanitizes_topic():
    assert meeting_filename("2026-08-02", "周会 / 纪要") == (
        "docs/meetings/2026-08-02-周会-纪要.md"
    )


def test_meeting_filename_empty_parts_fall_back():
    assert meeting_filename("2026-08-02", "") == "docs/meetings/2026-08-02-meeting.md"
    assert meeting_filename("", "周会") == "docs/meetings/unknown-date-周会.md"
