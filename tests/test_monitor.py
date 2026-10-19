"""The loop must stay silent, and must speak when it matters.

Silence is the hard part. A loop that messages daily gets muted within a
week, and a muted agent is a dead one. So most of these tests assert that
nothing was sent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from falsifier import config, monitor
from falsifier.memory import db
from falsifier.pipeline import freshness

QUOTE = "Applicants must hold a Bachelor's degree before enrollment."
URL = "https://cs.stanford.edu/admissions"


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    connection = db.init_db(tmp_path / "t.db")
    monkeypatch.setattr(monitor, "send", lambda text: sent.append(text) or True)
    sent.clear()
    yield connection
    connection.close()


sent: list[str] = []


def seed_finding(conn, *, quote=QUOTE, url=URL, etag='"v1"', due=True):
    conn.execute("INSERT INTO claims (id, text) VALUES (1, 'A degree is required')")
    conn.execute("INSERT INTO sub_claims (id, claim_id, text) VALUES (1, 1, 'sub')")
    conn.execute("INSERT INTO hypotheses (id, sub_claim_id, text) VALUES (1, 1, 'hyp')")
    conn.execute(
        "INSERT INTO evidence (id, hypothesis_id, quoted_line, url, source_tier, etag) "
        "VALUES (1, 1, ?, ?, 'primary', ?)", (quote, url, etag))
    when = (datetime.now(timezone.utc) - timedelta(days=1)) if due else \
           (datetime.now(timezone.utc) + timedelta(days=30))
    conn.execute(
        "INSERT INTO findings (id, claim_id, sub_claim_id, evidence_id, stance, "
        "text, next_check_at) VALUES (1, 1, 1, 1, 'supports', "
        "'Stanford requires a degree', ?)", (when.isoformat(),))
    conn.commit()


def page(monkeypatch, *, status=200, unchanged=False, text=QUOTE, gone=False):
    state = freshness.PageState(
        url=URL, status=404 if gone else status, etag='"v2"',
        checked_at=datetime.now(timezone.utc), unchanged=unchanged,
    )
    monkeypatch.setattr(freshness, "check", lambda url, **kw: state)
    monkeypatch.setattr(freshness, "fetch_text", lambda url: (text, state))


# --- silence ---------------------------------------------------------------


def test_an_unchanged_source_says_nothing(conn, monkeypatch):
    seed_finding(conn)
    page(monkeypatch, unchanged=True)
    result = monitor.run_once(conn, include_research=False)
    assert result.quiet
    assert result.unchanged == 1
    assert sent == [], "a quiet day must send nothing at all"


def test_a_changed_page_whose_quote_survived_says_nothing(conn, monkeypatch):
    """What matters is the sentence, not the page."""
    seed_finding(conn)
    page(monkeypatch, unchanged=False, text="Preamble. " + QUOTE + " Footer.")
    result = monitor.run_once(conn, include_research=False)
    assert result.quiet
    assert sent == []


def test_findings_not_yet_due_are_left_alone(conn, monkeypatch):
    seed_finding(conn, due=False)
    page(monkeypatch, unchanged=True)
    assert monitor.run_once(conn, include_research=False).checked == 0


def test_unverifiable_findings_are_not_monitored(conn, monkeypatch):
    """There is no source to re-check, so there is nothing to watch."""
    conn.execute("INSERT INTO claims (id, text) VALUES (1, 'c')")
    conn.execute(
        "INSERT INTO findings (claim_id, stance, text, reason) "
        "VALUES (1, 'unverifiable', 'cannot tell', 'no sources')")
    conn.commit()
    page(monkeypatch, unchanged=True)
    assert monitor.run_once(conn, include_research=False).checked == 0


# --- speaking --------------------------------------------------------------


def test_a_vanished_quote_retracts_the_finding(conn, monkeypatch):
    seed_finding(conn)
    page(monkeypatch, unchanged=False, text="This page now says something else.")
    result = monitor.run_once(conn, include_research=False)

    assert not result.quiet
    row = conn.execute("SELECT * FROM findings WHERE id = 1").fetchone()
    assert row["status"] == "retracted"
    assert "no longer present" in row["retracted_reason"]
    assert row["retracted_at"] is not None


def test_a_retraction_keeps_its_history(conn, monkeypatch):
    """Being wrong on the record is the point. Never delete."""
    seed_finding(conn)
    page(monkeypatch, unchanged=False, text="different now")
    monitor.run_once(conn, include_research=False)
    row = conn.execute("SELECT text, evidence_id FROM findings WHERE id = 1").fetchone()
    assert row["text"] == "Stanford requires a degree"
    assert row["evidence_id"] == 1, "the evidence it rested on is kept"


def test_a_deleted_source_retracts_the_finding(conn, monkeypatch):
    seed_finding(conn)
    page(monkeypatch, gone=True)
    monitor.run_once(conn, include_research=False)
    row = conn.execute("SELECT status, retracted_reason FROM findings WHERE id = 1").fetchone()
    assert row["status"] == "retracted"
    assert "404" in row["retracted_reason"]


def test_the_message_names_the_claim_and_the_source(conn, monkeypatch):
    seed_finding(conn)
    page(monkeypatch, unchanged=False, text="changed")
    monitor.run_once(conn, include_research=False)
    assert len(sent) == 1
    assert "A degree is required" in sent[0]
    assert URL in sent[0]


def test_a_network_failure_is_an_error_not_a_retraction(conn, monkeypatch):
    """Being unable to check is not evidence that the claim changed."""
    seed_finding(conn)
    state = freshness.PageState(url=URL, status=0, error="ConnectionError",
                                checked_at=datetime.now(timezone.utc))
    monkeypatch.setattr(freshness, "check", lambda url, **kw: state)
    result = monitor.run_once(conn, include_research=False)
    assert result.errors
    assert result.quiet, "an unreachable source must not alarm the user"
    assert conn.execute("SELECT status FROM findings WHERE id=1").fetchone()[0] == "live"


# --- scheduling ------------------------------------------------------------


def test_checking_reschedules_the_next_look(conn, monkeypatch):
    seed_finding(conn)
    page(monkeypatch, unchanged=True)
    monitor.run_once(conn, include_research=False)
    when = conn.execute("SELECT next_check_at FROM findings WHERE id=1").fetchone()[0]
    assert datetime.fromisoformat(when) > datetime.now(timezone.utc)


def test_a_failed_notification_does_not_break_the_loop(conn, monkeypatch):
    seed_finding(conn)
    page(monkeypatch, unchanged=False, text="changed")
    monkeypatch.setattr(monitor, "send", lambda text: False)
    result = monitor.run_once(conn, include_research=False)
    assert not result.quiet, "the change is still recorded even if the message failed"


# --- the weekly hunt -------------------------------------------------------


def test_a_claim_searched_recently_is_not_researched_again(conn, monkeypatch):
    """The weekly hunt costs credits, so it must not run early."""
    from falsifier.clients import tavily

    conn.execute("INSERT INTO claims (id, text) VALUES (1, 'a claim')")
    conn.execute("INSERT INTO runs (id, claim_id, mode) VALUES (1, 1, 'personal')")
    conn.execute("INSERT INTO searches (run_id, query) VALUES (1, 'searched just now')")
    conn.commit()
    monkeypatch.setattr(tavily, "search", lambda q, **kw: pytest.fail(
        "must not search a claim checked this week"))
    assert monitor.research(conn).credits_spent == 0


def test_research_reports_only_pages_not_seen_before(conn, monkeypatch):
    from falsifier.clients import tavily

    conn.execute("INSERT INTO claims (id, text) VALUES (1, 'a claim')")
    conn.execute("INSERT INTO runs (id, claim_id, mode) VALUES (1, 1, 'personal')")
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    conn.execute("INSERT INTO searches (id, run_id, query, created_at) "
                 "VALUES (1, 1, 'a query', ?)", (old,))
    conn.execute("INSERT INTO results (search_id, url, title) "
                 "VALUES (1, 'https://old.example/a', 'old')")
    conn.commit()

    monkeypatch.setattr(tavily, "search", lambda q, **kw: tavily.Search(
        query=q, credits=1, results=[
            tavily.Result("https://old.example/a", "old", "x"),
            tavily.Result("https://new.example/b", "brand new", "y"),
        ]))
    result = monitor.research(conn)
    urls = [c.url for c in result.changes]
    assert "https://new.example/b" in urls
    assert "https://old.example/a" not in urls, "already seen is not news"


def test_research_respects_its_credit_ceiling(conn, monkeypatch):
    from falsifier.clients import tavily

    conn.execute("INSERT INTO claims (id, text) VALUES (1, 'a claim')")
    conn.execute("INSERT INTO runs (id, claim_id, mode) VALUES (1, 1, 'personal')")
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    for i in range(10):
        conn.execute("INSERT INTO searches (run_id, query, created_at) "
                     "VALUES (1, ?, ?)", (f"q{i}", old))
    conn.commit()

    monkeypatch.setattr(tavily, "search", lambda q, **kw: tavily.Search(
        query=q, credits=1, results=[tavily.Result(f"https://new/{q}", "t", "s")]))
    result = monitor.research(conn, max_credits=2)
    assert result.credits_spent <= 2, "the one budget that actually runs out"


# ---------------------------------------------------------------------------
# The message has to read properly end to end. It is going in the demo video,
# and an arbitrary 200-character slice cut it off mid-sentence.
# ---------------------------------------------------------------------------


def test_a_normal_message_is_not_shortened_at_all():
    statement = (
        "The Stanford MS in Computer Science admissions page states that "
        "applicants must hold or expect to hold a bachelor's degree before "
        "enrollment, not that it is required at the time of application, "
        "which contradicts the claim that a degree is required to apply."
    )
    change = monitor.Change(1, "A degree is required to apply.", statement,
                            URL, "retracted", "the line has gone")
    message = monitor.compose([change])
    assert statement in message, "the statement must appear whole"
    assert "\u2026" not in message
    assert message.rstrip().endswith(URL)


def test_an_enormous_statement_is_cut_at_a_sentence_not_mid_word():
    statement = ("First sentence here. " * 400).strip()
    change = monitor.Change(1, "c", statement, URL, "retracted", "gone")
    message = monitor.compose([change])
    assert len(message) <= monitor.TELEGRAM_MAX_CHARS
    assert URL in message, "the link survives shortening"


def test_the_claim_and_link_are_never_sacrificed():
    change = monitor.Change(1, "A short claim.", "x " * 5000, URL,
                            "retracted", "gone")
    message = monitor.compose([change])
    assert "A short claim." in message
    assert URL in message
    assert len(message) <= monitor.TELEGRAM_MAX_CHARS


def test_trim_ends_on_a_sentence_when_it_can():
    text = "One sentence. Two sentence. Three sentence that runs on and on."
    assert monitor._trim(text, 30).endswith(". ") or monitor._trim(text, 30).endswith(".")


def test_trim_never_splits_a_word():
    assert not monitor._trim("supercalifragilistic expialidocious", 20).rstrip(
        "\u2026").endswith("supercalifragi")
