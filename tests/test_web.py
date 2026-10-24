"""The interface must show the evidence, and the demo must never leak.

Two things here are correctness rather than presentation: a personal thread
must be unreachable from the public demo even by guessing its id, and
anything a model or a stranger writes must not be able to inject markup.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from falsifier.memory import db, sessions
from web import main, markup


def visible(html: str) -> str:
    """Just the words a reader sees. Styles and scripts are not copy."""
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / "t.db"
    conn = db.init_db(path)
    monkeypatch.setattr(main, "connect", lambda: db.connect(path))
    monkeypatch.delenv("FALSIFIER_DEMO", raising=False)
    monkeypatch.setattr(
        main.threading, "Thread",
        lambda *a, **k: type("T", (), {"start": lambda s: None})())
    _seed(conn)
    conn.close()
    yield TestClient(main.app)


def _seed(conn):
    conn.execute("INSERT INTO claims (id, text, mode) VALUES "
                 "(1, 'A degree is required to apply', 'personal')")
    conn.execute("INSERT INTO claims (id, text, mode) VALUES "
                 "(2, 'A public example plan', 'demo')")
    conn.execute("INSERT INTO sub_claims (id, claim_id, text) VALUES (1, 1, 'the sub-claim')")
    conn.execute("INSERT INTO hypotheses (id, sub_claim_id, text) VALUES (1, 1, 'a hypothesis')")
    conn.execute("INSERT INTO evidence (id, hypothesis_id, quoted_line, url, source_tier) "
                 "VALUES (1, 1, 'Applicants must hold a degree.', "
                 "'https://cs.stanford.edu/admissions', 'primary')")
    conn.execute("INSERT INTO findings (id, claim_id, sub_claim_id, evidence_id, stance, "
                 "text, confidence) VALUES (1, 1, 1, 1, 'supports', 'It held up.', 0.9)")
    conn.execute("INSERT INTO runs (id, claim_id, mode, status, n_hypotheses, n_searches, "
                 "n_results, n_read, n_survived, assessment, hinges_on) VALUES "
                 "(1, 1, 'personal', 'complete', 50, 40, 412, 25, 2, "
                 "'The arithmetic only works if the grant grows.', 'Equity, not salary.')")
    conn.execute("INSERT INTO searches (id, run_id, hypothesis_id, query, n_results) "
                 "VALUES (1, 1, 1, 'a query that was run', 5)")
    conn.commit()

    personal = sessions.create(conn, "A degree is required", claim_id=1)
    sessions.add(conn, personal, "user", "A degree is required to apply")
    sessions.add(conn, personal, "agent",
                 "**This part still holds.** It held up.\n\n"
                 "> Applicants must hold a degree.\n\n"
                 "[https://cs.stanford.edu/admissions](https://cs.stanford.edu/admissions)"
                 " - primary source", kind="finding")
    demo = sessions.create(conn, "A public example plan", mode="demo", claim_id=2)
    sessions.add(conn, demo, "user", "A public example plan")


# --- the evidence is visible ----------------------------------------------


def test_a_thread_shows_the_quote_and_the_link(client):
    body = client.get("/s/1").text
    assert "Applicants must hold a degree." in body
    assert "https://cs.stanford.edu/admissions" in body


def test_reasoning_is_labelled_as_reasoning(client):
    """Inference must never be mistaken for evidence."""
    conn = main.connect()
    sessions.add(conn, 1, "agent", "Some reasoning.", kind="assessment")
    conn.close()
    assert "reasoning, not evidence" in client.get("/s/1").text


def test_an_unprompted_message_is_marked_as_such(client):
    conn = main.connect()
    sessions.add(conn, 1, "agent", "The date moved.", kind="alert")
    conn.close()
    assert "arrived unprompted" in client.get("/s/1").text


# --- the dot ---------------------------------------------------------------


def test_a_waiting_thread_shows_a_dot_in_the_panel(client):
    conn = main.connect()
    sessions.add(conn, 1, "agent", "The date moved.", kind="alert")
    conn.close()
    assert 'class="dot"' in client.get("/").text


def test_opening_the_thread_clears_the_dot(client):
    conn = main.connect()
    sessions.add(conn, 1, "agent", "The date moved.", kind="alert")
    conn.close()
    client.get("/s/1")
    assert 'class="dot"' not in client.get("/").text


# --- using it --------------------------------------------------------------


def test_the_front_page_is_an_empty_box(client):
    body = client.get("/").text
    assert 'action="/say"' in body
    assert "<textarea" in body
    assert "What are you planning?" in visible(body)


def test_saying_something_new_starts_a_thread(client):
    r = client.post("/say", data={"message": "I am preparing for JEE in April."},
                    follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/s/")


def test_a_follow_up_stays_in_the_same_thread(client):
    r = client.post("/say", data={"message": "what did you mean?",
                                  "session_id": "1"}, follow_redirects=False)
    assert r.headers["location"] == "/s/1"
    conn = main.connect()
    assert any(m.body == "what did you mean?" for m in sessions.history(conn, 1))
    conn.close()


def test_an_empty_message_is_refused(client):
    r = client.post("/say", data={"message": " "}, follow_redirects=False)
    assert r.headers["location"] == "/"


def test_the_thread_api_returns_only_new_messages(client):
    data = client.get("/api/thread/1?after=1").json()
    assert all(m["id"] > 1 for m in data["messages"])
    assert data["progress"]["n_searches"] == 40


# --- demo isolation, a correctness requirement ------------------------------


def test_personal_threads_are_listed_in_personal_mode(client):
    assert "A degree is required" in visible(client.get("/").text)


def test_demo_mode_lists_only_demo_threads(client, monkeypatch):
    monkeypatch.setenv("FALSIFIER_DEMO", "1")
    body = visible(client.get("/").text)
    assert "A public example plan" in body
    assert "A degree is required" not in body


def test_demo_mode_cannot_open_a_personal_thread_by_id(client, monkeypatch):
    monkeypatch.setenv("FALSIFIER_DEMO", "1")
    assert client.get("/s/1").status_code == 404
    assert client.get("/funnel/1").status_code == 404
    assert client.get("/api/thread/1").status_code == 404


def test_demo_mode_says_it_is_a_demo(client, monkeypatch):
    monkeypatch.setenv("FALSIFIER_DEMO", "1")
    assert "Nothing personal is shown or kept" in client.get("/").text


def test_health_reports_the_mode(client, monkeypatch):
    assert client.get("/health").json()["mode"] == "personal"
    monkeypatch.setenv("FALSIFIER_DEMO", "1")
    assert client.get("/health").json()["mode"] == "demo"


# --- looking inside --------------------------------------------------------


def test_the_funnel_shows_what_was_discarded(client):
    body = client.get("/funnel/1").text
    for n in ("50", "40", "412", "25"):
        assert n in body
    assert "a query that was run" in body
    assert "a hypothesis" in body


def test_the_funnel_links_back_to_the_conversation(client):
    assert 'href="/s/1"' in client.get("/funnel/1").text


def test_an_unknown_thread_is_a_clean_404(client):
    r = client.get("/s/9999")
    assert r.status_code == 404
    assert "Start a plan" in visible(r.text)


def test_the_numbers_page_renders(client):
    assert "measured" in client.get("/numbers").text


# --- voice -----------------------------------------------------------------


def test_the_copy_is_not_adversarial(client):
    for page in ("/", "/s/1", "/funnel/1"):
        body = visible(client.get(page).text).lower()
        assert "evidence that you are wrong" not in body, page
        assert "objection" not in body, page
        assert "falsification" not in body, page


def test_the_old_report_framing_is_gone(client):
    body = visible(client.get("/").text)
    assert "unsettled" not in body
    assert "unverifiable" not in body


# --- markup safety ---------------------------------------------------------


def test_markup_escapes_html():
    assert "<script>" not in markup.render("<script>alert(1)</script>")


def test_markup_refuses_a_javascript_link():
    """It may appear as text, but never as something clickable."""
    out = markup.render("[x](javascript:alert(1))")
    assert "<a " not in out
    assert 'href="javascript' not in out


def test_markup_keeps_the_marks_the_agent_uses():
    out = markup.render("**bold**\n\n> quoted\n\n[a](https://example.edu)")
    assert "<strong>bold</strong>" in out
    assert "<blockquote>quoted</blockquote>" in out
    assert 'href="https://example.edu"' in out
