"""The interface must show the evidence, and the demo must never leak.

The separation between personal and demo mode is the one thing here that
is a correctness requirement rather than presentation: the public URL and
the user's own instance run the same code against the same schema, so the
filter has to be real.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from falsifier.memory import db
from web import main


def visible(html: str) -> str:
    """Just the words a reader sees. Styles and scripts are not copy."""
    import re
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    conn = db.init_db(tmp_path / "t.db")
    monkeypatch.setattr(main, "connect", lambda: db.connect(tmp_path / "t.db"))
    monkeypatch.delenv("FALSIFIER_DEMO", raising=False)
    _seed(conn)
    conn.close()
    yield TestClient(main.app)


def _seed(conn):
    conn.execute("INSERT INTO claims (id, text, mode) VALUES "
                 "(1, 'A degree is required', 'personal')")
    conn.execute("INSERT INTO claims (id, text, mode) VALUES "
                 "(2, 'A public example claim', 'demo')")
    conn.execute("INSERT INTO sub_claims (id, claim_id, text) VALUES (1, 1, 'the sub-claim')")
    conn.execute("INSERT INTO hypotheses (id, sub_claim_id, text) VALUES (1, 1, 'a hypothesis')")
    conn.execute(
        "INSERT INTO evidence (id, hypothesis_id, quoted_line, url, source_tier) "
        "VALUES (1, 1, 'Applicants must hold a degree.', "
        "'https://cs.stanford.edu/admissions', 'primary')")
    conn.execute(
        "INSERT INTO findings (id, claim_id, sub_claim_id, evidence_id, stance, "
        "text, confidence) VALUES (1, 1, 1, 1, 'supports', 'The claim held up.', 0.9)")
    conn.execute(
        "INSERT INTO findings (claim_id, stance, text, reason) VALUES "
        "(1, 'unverifiable', 'Could not settle this.', 'the sources are silent')")
    conn.execute("INSERT INTO runs (id, claim_id, mode, n_hypotheses, n_searches, "
                 "n_results, n_read, n_survived) VALUES (1, 1, 'personal', 50, 40, 412, 25, 2)")
    conn.execute("INSERT INTO searches (id, run_id, hypothesis_id, query, n_results) "
                 "VALUES (1, 1, 1, 'a query that was run', 5)")
    conn.execute("INSERT INTO claim_authorities (claim_id, name, domain, why, reachable) "
                 "VALUES (1, 'Stanford', 'stanford.edu', 'sets its own rules', 1)")
    conn.commit()


# --- the evidence must be visible ------------------------------------------


def test_a_verdict_always_shows_its_quote_and_link(client):
    body = client.get("/claim/1").text
    assert "Applicants must hold a degree." in body
    assert "https://cs.stanford.edu/admissions" in body
    assert "primary" in body


def test_an_unsettled_finding_shows_why(client):
    body = client.get("/claim/1").text
    assert "Could not settle this." in body
    assert "the sources are silent" in body


def test_a_missing_date_is_stated_not_hidden(client):
    assert "does not say when it was last updated" in client.get("/claim/1").text


def test_the_claim_page_names_who_decides(client):
    body = client.get("/claim/1").text
    assert "Stanford" in body and "stanford.edu" in body


# --- the funnel ------------------------------------------------------------


def test_the_funnel_shows_what_was_discarded(client):
    body = client.get("/funnel/1").text
    for n in ("50", "40", "412", "25", "2"):
        assert n in body
    assert "a query that was run" in body
    assert "a hypothesis" in body


def test_the_funnel_explains_itself_to_a_stranger(client):
    body = client.get("/funnel/1").text
    assert "invented before searching" in body
    assert "word-for-word" in body


# --- demo isolation, the part that is a correctness requirement ------------


def test_personal_mode_lists_only_personal_claims(client):
    body = client.get("/").text
    assert "A degree is required" in body
    assert "A public example claim" not in body


def test_demo_mode_lists_only_demo_claims(client, monkeypatch):
    monkeypatch.setenv("FALSIFIER_DEMO", "1")
    body = client.get("/").text
    assert "A public example claim" in body
    assert "A degree is required" not in body, "the demo must never show personal claims"


def test_demo_mode_cannot_open_a_personal_claim_by_id(client, monkeypatch):
    """Guessing the URL must not work."""
    monkeypatch.setenv("FALSIFIER_DEMO", "1")
    assert client.get("/claim/1").status_code == 404
    assert client.get("/funnel/1").status_code == 404


def test_demo_mode_says_it_is_a_demo(client, monkeypatch):
    monkeypatch.setenv("FALSIFIER_DEMO", "1")
    assert "Nothing personal is shown or kept" in client.get("/").text


def test_health_reports_the_mode(client, monkeypatch):
    assert client.get("/health").json()["mode"] == "personal"
    monkeypatch.setenv("FALSIFIER_DEMO", "1")
    assert client.get("/health").json()["mode"] == "demo"


# --- it must not fall over on an empty or missing thing --------------------


def test_an_unknown_claim_is_a_clean_404(client):
    response = client.get("/claim/9999")
    assert response.status_code == 404
    assert "No such claim" in response.text


def test_the_numbers_page_renders(client):
    body = client.get("/numbers").text
    assert "measured" in body or "planned" in body


# ---------------------------------------------------------------------------
# A visitor has to be able to use it, and the voice has to be right.
# ---------------------------------------------------------------------------


def test_a_visitor_can_enter_a_claim(client):
    """The hard requirement: a judge must be able to run something."""
    body = client.get("/").text
    assert 'action="/check"' in body
    assert "<textarea" in body


def test_the_opening_explains_the_product_without_jargon(client):
    body = client.get("/").text
    assert "exam board moved the" in body, "the JEE story is the explanation"
    assert "never tells you things you already know" in body


def test_the_copy_is_not_adversarial(client):
    """The method is adversarial; the stance toward the user is not."""
    for page in ("/", "/claim/1", "/funnel/1"):
        body = visible(client.get(page).text).lower()
        assert "evidence that you are wrong" not in body, page
        assert "objection" not in body, page
        assert "falsification" not in body, page


def test_status_words_are_plain_english(client):
    body = visible(client.get("/").text)
    assert "still true" in body
    assert "unsettled" not in body
    assert "unverifiable" not in body


def test_a_very_short_claim_is_refused(client):
    r = client.post("/check", data={"claim": "too short"}, follow_redirects=False)
    assert r.status_code == 303
    assert "error=short" in r.headers["location"]


def test_the_watch_page_polls_for_progress(client):
    body = client.get("/watch?claim=something").text
    assert "/api/progress" in body
    assert "ways it could be wrong" in body


def test_progress_reports_starting_for_an_unknown_claim(client):
    assert client.get("/api/progress?claim=never+seen").json()["state"] == "starting"


def test_progress_reports_the_funnel_as_it_fills(client, tmp_path):
    conn = db.connect(tmp_path / "t.db")
    conn.execute("UPDATE runs SET stage = 'searching', n_searches = 7 WHERE id = 1")
    conn.commit()
    conn.close()
    data = client.get("/api/progress?claim=A degree is required").json()
    assert data["searches"] == 7
    assert data["stage"] == "searching"
    assert data["claim_id"] == 1
