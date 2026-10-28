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


# ---------------------------------------------------------------------------
# The contradiction, 25 Oct. Seeding read whatever the notice currently
# said, while the claim text hardcodes April, so the thread announced
# "your plan has the right date" while quoting a different month.
# ---------------------------------------------------------------------------


def test_seeding_ignores_a_date_someone_already_changed(conn):
    watchdemo.set_date(conn, "14 August 2026")
    finding_id = watchdemo.ensure(conn, URL)

    row = conn.execute(
        "SELECT f.text, e.quoted_line FROM findings f "
        "JOIN evidence e ON e.id = f.evidence_id WHERE f.id = ?",
        (finding_id,)).fetchone()
    assert watchdemo.ORIGINAL_DATE in row["quoted_line"]
    assert "August" not in row["quoted_line"]
    assert "August" not in row["text"]


def test_the_finding_never_contradicts_the_claim(conn):
    """It must not say a plan is right while quoting a different date."""
    watchdemo.set_date(conn, "3 November 2026")
    finding_id = watchdemo.ensure(conn, URL)

    claim = conn.execute(
        "SELECT c.text FROM claims c JOIN findings f ON f.claim_id = c.id "
        "WHERE f.id = ?", (finding_id,)).fetchone()["text"]
    finding = conn.execute(
        "SELECT f.text, e.quoted_line FROM findings f "
        "JOIN evidence e ON e.id = f.evidence_id WHERE f.id = ?",
        (finding_id,)).fetchone()

    month = watchdemo.ORIGINAL_DATE.split()[1]
    assert month in claim
    assert month in finding["text"], "the verdict must agree with the claim"
    assert month in finding["quoted_line"], "and with the line it quotes"


def test_seeding_puts_the_notice_back_to_the_original(conn):
    watchdemo.set_date(conn, "3 November 2026")
    watchdemo.ensure(conn, URL)
    assert watchdemo.get_date(conn) == watchdemo.ORIGINAL_DATE


# ---------------------------------------------------------------------------
# The three bugs reported on 28 Oct, two days before submission.
# ---------------------------------------------------------------------------


def test_the_same_page_never_gets_a_second_conversation(conn):
    """Behind a TLS proxy the app sees its own address as http one request
    and https the next. Matching the whole URL made those different pages,
    so every change seeded a fresh claim with a fabricated opening message
    while the real conversation was left alone."""
    first = watchdemo.ensure(conn, "http://host.test/notice")
    second = watchdemo.ensure(conn, "https://host.test/notice")

    assert first == second
    assert conn.execute("SELECT count(*) FROM claims").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1
    url = conn.execute(
        "SELECT e.url FROM evidence e JOIN findings f ON f.evidence_id = e.id "
        "WHERE f.id = ?", (first,)).fetchone()["url"]
    assert url == "https://host.test/notice", "stored address kept current"


def test_the_message_says_the_claim_no_longer_holds(conn, monkeypatch):
    """It used to quote the old agreeing sentence and leave the reader to
    work out it no longer applied, which read as self-contradiction."""
    finding_id = watchdemo.ensure(conn, URL)
    session_id = watchdemo.session_for(conn, finding_id)
    page_says(monkeypatch, "14 September 2026")
    due(conn, finding_id)

    monitor.run_once(conn, include_research=False, notify=False)
    body = sessions.history(conn, session_id)[-1].body

    assert "no longer holds" in body
    assert "That page now says" in body
    assert "14 September 2026" in body, "says what the source says instead"
    assert body.index("no longer holds") < body.index("I had told you")


def test_it_keeps_watching_after_the_first_change(conn, monkeypatch):
    """Filtering the watch list to live findings meant it went quiet for
    ever once something had been withdrawn."""
    finding_id = watchdemo.ensure(conn, URL)
    session_id = watchdemo.session_for(conn, finding_id)

    page_says(monkeypatch, "14 September 2026")
    due(conn, finding_id)
    monitor.run_once(conn, include_research=False, notify=False)
    first = len(sessions.history(conn, session_id))

    # Changed again. The finding is already withdrawn, but the page moving
    # again is still worth knowing about.
    page_says(monkeypatch, "2 December 2026")
    due(conn, finding_id)
    result = monitor.run_once(conn, include_research=False, notify=False)

    assert not result.quiet, "a second change must still be noticed"
    messages = sessions.history(conn, session_id)
    assert len(messages) > first
    assert "2 December 2026" in messages[-1].body


def test_a_page_that_has_not_moved_again_says_nothing(conn, monkeypatch):
    """Keeping watch must not mean repeating itself every morning."""
    finding_id = watchdemo.ensure(conn, URL)
    page_says(monkeypatch, "14 September 2026")
    due(conn, finding_id)
    monitor.run_once(conn, include_research=False, notify=False)

    due(conn, finding_id)
    assert monitor.run_once(conn, include_research=False,
                            notify=False).quiet


def test_a_line_coming_back_is_reported_too(conn, monkeypatch):
    """An agent that only ever withdraws is not keeping anything current."""
    finding_id = watchdemo.ensure(conn, URL)
    session_id = watchdemo.session_for(conn, finding_id)

    page_says(monkeypatch, "14 September 2026")
    due(conn, finding_id)
    monitor.run_once(conn, include_research=False, notify=False)
    assert conn.execute("SELECT status FROM findings WHERE id = ?",
                        (finding_id,)).fetchone()[0] == "retracted"

    page_says(monkeypatch, watchdemo.ORIGINAL_DATE)
    due(conn, finding_id)
    monitor.run_once(conn, include_research=False, notify=False)

    assert conn.execute("SELECT status FROM findings WHERE id = ?",
                        (finding_id,)).fetchone()[0] == "live"
    assert "stands again" in sessions.history(conn, session_id)[-1].body


def test_the_replacement_sentence_is_found():
    old = watchdemo.quote_for("14 April 2026")
    page = ("Notice to Candidates. " + watchdemo.quote_for("14 September 2026")
            + " Candidates must report one hour before.")
    found = monitor.replacement_line(old, page)
    assert found and "14 September 2026" in found


def test_an_unrelated_page_yields_no_replacement():
    old = watchdemo.quote_for("14 April 2026")
    assert monitor.replacement_line(old, "A page about dog grooming.") is None
