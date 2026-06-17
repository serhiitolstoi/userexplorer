"""Tests for deterministic insight extraction, especially recency vs. the clock."""

from __future__ import annotations

from datetime import date, datetime

from user_explorer.insights import extract_insights


def _blob(last_seen: str) -> dict[str, object]:
    """Minimal blob with a known last-seen timestamp."""
    return {
        "u": "u1",
        "te": 10,
        "sn": 2,
        "fs": "2024-01-01 09:00",
        "ls": last_seen,
        "fc": {"view": 6, "click": 4},
        "attrs": {},
        "s": [],
    }


def test_days_since_last_uses_as_of_when_provided() -> None:
    blob = _blob("2024-03-01 12:00")
    out = extract_insights(blob, [blob], as_of=date(2024, 3, 11))
    assert out["days_since_last"] == 10


def test_days_since_last_defaults_to_today() -> None:
    """Without as_of the metric must track the real clock, not a frozen constant."""
    blob = _blob("2024-03-01 12:00")
    expected = (date.today() - date(2024, 3, 1)).days
    out = extract_insights(blob, [blob])
    assert out["days_since_last"] == expected


def test_days_since_last_handles_bad_timestamp() -> None:
    blob = _blob("")
    out = extract_insights(blob, [blob])
    assert out["days_since_last"] == -1


def test_recency_is_not_frozen_to_2026() -> None:
    """Regression guard: a blob seen 'today' must report ~0 days, not a 2026-relative value."""
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    blob = _blob(today_str)
    out = extract_insights(blob, [blob])
    assert out["days_since_last"] == 0


def test_engagement_active_when_recent() -> None:
    blob = _blob("2024-03-09 12:00")  # 2 days before as_of, 2 sessions
    out = extract_insights(blob, [blob], as_of=date(2024, 3, 11))
    assert out["engagement"] == "active"


def test_engagement_cooling_then_dormant_by_recency() -> None:
    blob = _blob("2024-03-01 12:00")  # 20 days before as_of
    assert extract_insights(blob, [blob], as_of=date(2024, 3, 21))["engagement"] == "cooling"
    # same blob, much later as_of -> dormant
    assert extract_insights(blob, [blob], as_of=date(2024, 5, 1))["engagement"] == "dormant"


def test_engagement_one_shot_for_single_session() -> None:
    blob = _blob("2024-03-10 12:00")
    blob["sn"] = 1
    out = extract_insights(blob, [blob], as_of=date(2024, 3, 11))
    assert out["engagement"] == "one_shot"
