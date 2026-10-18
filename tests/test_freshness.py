"""Freshness must be reported, never assumed.

The agent cannot know a fact is current. It can know what a page said when
it looked, when the server says the page changed, and whether it has
changed since. These tests hold it to exactly that and no more.
"""

from __future__ import annotations

import types
from datetime import datetime, timedelta, timezone

import requests

from falsifier.pipeline import freshness


def fake_head(monkeypatch, status=200, headers=None, raises=None):
    def head(url, **kwargs):
        if raises:
            raise raises
        return types.SimpleNamespace(
            status_code=status, headers=headers or {}, text=""
        )

    monkeypatch.setattr(freshness.requests, "head", head)


def test_reads_last_modified_from_the_server(monkeypatch):
    fake_head(monkeypatch, headers={"Last-Modified": "Wed, 14 Oct 2026 18:45:21 GMT"})
    state = freshness.check("https://example.edu/x")
    assert state.last_modified.year == 2026
    assert state.last_modified.month == 10
    assert "14 Oct 2026" in state.describe()


def test_says_so_when_the_server_gives_no_date(monkeypatch):
    """Silence must be reported as silence, not treated as fresh."""
    fake_head(monkeypatch, headers={})
    state = freshness.check("https://example.edu/x")
    assert state.last_modified is None
    assert "does not say" in state.describe()


def test_304_means_definitively_unchanged(monkeypatch):
    fake_head(monkeypatch, status=304, headers={})
    state = freshness.check("https://example.edu/x", known_etag='"abc"')
    assert state.unchanged is True
    assert state.etag == '"abc"', "the known etag is carried forward"


def test_a_deleted_source_is_detected(monkeypatch):
    fake_head(monkeypatch, status=404, headers={})
    state = freshness.check("https://example.edu/gone")
    assert state.gone is True
    assert "gone" in state.describe()


def test_network_failure_is_reported_not_swallowed(monkeypatch):
    fake_head(monkeypatch, raises=requests.ConnectionError("boom"))
    state = freshness.check("https://example.edu/x")
    assert state.reachable is False
    assert "could not check" in state.describe()


def test_age_in_days_is_computed_from_the_server_date():
    now = datetime.now(timezone.utc)
    state = freshness.PageState(
        url="u", status=200,
        last_modified=now - timedelta(days=10), checked_at=now,
    )
    assert round(state.age_days) == 10


def test_fingerprint_ignores_whitespace_and_case():
    assert freshness.fingerprint("Hello   World") == freshness.fingerprint("hello world")


def test_fingerprint_changes_when_content_changes():
    assert freshness.fingerprint("admits 60%") != freshness.fingerprint("admits 40%")


def test_recently_changed_pages_are_rechecked_sooner():
    """Churn predicts churn."""
    now = datetime.now(timezone.utc)
    volatile = freshness.PageState(
        "u", 200, last_modified=now - timedelta(days=2), checked_at=now
    )
    stable = freshness.PageState(
        "u", 200, last_modified=now - timedelta(days=900), checked_at=now
    )
    assert freshness.next_check_days("primary", volatile) < \
           freshness.next_check_days("primary", stable)


def test_unknown_tier_still_gets_a_schedule():
    assert freshness.next_check_days("something-else") > 0
