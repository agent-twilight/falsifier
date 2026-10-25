"""A judge must be able to set the watch off themselves.

The daily loop runs on the owner's machine, so on the public demo nobody
is watching anything. Telling a judge to change a date and wait would be
inviting them to wait for ever. These cover the on-demand path.

The fetching itself is stubbed, because a test must not need a live HTTP
server. The live path is exercised by hand against the running app.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from falsifier import monitor, watchdemo
from falsifier.memory import db, sessions
from falsifier.pipeline import freshness

URL = "https://example.test/notice"


@pytest.fixture()
def conn(tmp_path):
    connection = db.init_db(tmp_path / "t.db")
    yield connection
    connection.close()


def page_says(monkeypatch, date):
    """Serve a notice page carrying the given date."""
    body = watchdemo.quote_for(date)
    state = freshness.PageState(url=URL, status=200, etag='"v"',
                                checked_at=datetime.now(timezone.utc))
    monkeypatch.setattr(freshness, "check", lambda url, **kw: state)
    monkeypatch.setattr(freshness, "fetch_text", lambda url: (body, state))


def due(conn, finding_id):
    conn.execute("UPDATE findings SET next_check_at = datetime('now','-1 hour') "
                 "WHERE id = ?", (finding_id,))
    conn.commit()


def test_the_demo_seeds_itself_on_first_visit(conn):
    finding_id = watchdemo.ensure(conn, URL)
    row = conn.execute("SELECT stance, status FROM findings WHERE id = ?",
                       (finding_id,)).fetchone()
    assert row["stance"] == "supports"
    assert row["status"] == "live"
    assert watchdemo.session_for(conn, finding_id) is not None


def test_seeding_twice_does_not_duplicate(conn):
    first = watchdemo.ensure(conn, URL)
    assert watchdemo.ensure(conn, URL) == first
    assert conn.execute("SELECT count(*) FROM claims").fetchone()[0] == 1


def test_the_date_survives_between_requests(conn):
    """In-memory state would not, and a host may run several workers."""
    watchdemo.set_date(conn, "28 May 2026")
    assert watchdemo.get_date(conn) == "28 May 2026"


def test_checking_an_unchanged_notice_says_nothing(conn, monkeypatch):
    finding_id = watchdemo.ensure(conn, URL)
    page_says(monkeypatch, watchdemo.ORIGINAL_DATE)
    due(conn, finding_id)

    result = monitor.run_once(conn, include_research=False, notify=False)
    assert result.quiet
    assert conn.execute("SELECT status FROM findings WHERE id = ?",
                        (finding_id,)).fetchone()[0] == "live"


def test_changing_the_date_withdraws_the_finding(conn, monkeypatch):
    finding_id = watchdemo.ensure(conn, URL)
    watchdemo.set_date(conn, "28 May 2026")
    page_says(monkeypatch, "28 May 2026")
    due(conn, finding_id)

    monitor.run_once(conn, include_research=False, notify=False)
    row = conn.execute("SELECT status, retracted_reason, retracted_at "
                       "FROM findings WHERE id = ?", (finding_id,)).fetchone()
    assert row["status"] == "retracted"
    assert "no longer present" in row["retracted_reason"]
    assert row["retracted_at"]


def test_the_thread_gets_an_unprompted_message(conn, monkeypatch):
    finding_id = watchdemo.ensure(conn, URL)
    session_id = watchdemo.session_for(conn, finding_id)
    watchdemo.set_date(conn, "28 May 2026")
    page_says(monkeypatch, "28 May 2026")
    due(conn, finding_id)

    monitor.run_once(conn, include_research=False, notify=False)
    last = sessions.history(conn, session_id)[-1]
    assert last.unprompted
    assert sessions.get(conn, session_id, "demo").has_news


def test_reset_puts_everything_back_for_the_next_visitor(conn, monkeypatch):
    finding_id = watchdemo.ensure(conn, URL)
    session_id = watchdemo.session_for(conn, finding_id)
    watchdemo.set_date(conn, "28 May 2026")
    page_says(monkeypatch, "28 May 2026")
    due(conn, finding_id)
    monitor.run_once(conn, include_research=False, notify=False)

    watchdemo.reset(conn, URL)
    row = conn.execute("SELECT status FROM findings WHERE id = ?",
                       (finding_id,)).fetchone()
    assert row["status"] == "live"
    assert watchdemo.get_date(conn) == watchdemo.ORIGINAL_DATE
    assert not sessions.get(conn, session_id, "demo").has_news
    assert not any(m.unprompted for m in sessions.history(conn, session_id))


def test_the_quoted_sentence_matches_the_page_exactly(conn):
    """If these drift apart the demo withdraws on every check, for ever."""
    from falsifier.pipeline import read

    date = watchdemo.ORIGINAL_DATE
    page = (f"Candidates are hereby informed that the written examination "
            f"for the 2026 cycle will be conducted on {date} at all "
            f"designated centres.")
    assert read.quote_is_present(watchdemo.quote_for(date), page)
