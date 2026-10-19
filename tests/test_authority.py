"""Evidence must be graded by who published it, not by how the URL ends.

The motivating case: jeemain.nta.nic.in is the body that decides the JEE
exam date, and the old suffix rule graded it the same as a newspaper
because it does not end in .gov.
"""

from __future__ import annotations

import pytest

from falsifier.memory import db
from falsifier.pipeline import authority, parsing, read

JEE = "https://jeemain.nta.nic.in/notifications"
NEWS = "https://timesofindia.indiatimes.com/jee-date-change"
BLOG = "https://allen.ac.in/coaching-blog/jee-2026"


@pytest.fixture()
def conn(tmp_path):
    connection = db.init_db(tmp_path / "t.db")
    yield connection
    connection.close()


# --- grading ---------------------------------------------------------------


def test_the_suffix_rule_alone_gets_the_exam_board_wrong():
    """Documents the bug this module exists to fix."""
    assert read.grade_source(JEE) == "secondary"


def test_the_deciding_body_outranks_a_newspaper(conn):
    domains = {"nta.nic.in"}
    assert read.grade_source(JEE, domains) == "primary"
    assert read.grade_source(NEWS, domains) == "secondary"


def test_subdomains_of_an_authority_count(conn):
    assert read.grade_source("https://sub.deep.nta.nic.in/x", {"nta.nic.in"}) == "primary"


def test_a_lookalike_domain_does_not_count():
    """nta.nic.in.evil.com must not pass as the exam board."""
    assert read.grade_source("https://nta.nic.in.evil.com/x", {"nta.nic.in"}) != "primary"


def test_nothing_else_can_be_primary_once_an_authority_is_known():
    """A .edu page is not primary evidence about someone else's exam."""
    assert read.grade_source("https://harvard.edu/jee-notes", {"nta.nic.in"}) == "secondary"


def test_noise_stays_noise_even_with_an_authority_known():
    assert read.grade_source(BLOG, {"nta.nic.in"}) == "weak"


def test_grading_still_works_when_no_authority_was_identified():
    assert read.grade_source("https://cs.stanford.edu/admissions") == "primary"


# --- identification --------------------------------------------------------


def canned(monkeypatch, payload, reachable=True):
    monkeypatch.setattr(parsing, "complete_json", lambda *a, **k: payload)
    monkeypatch.setattr(authority.freshness, "check",
                        lambda url, **kw: authority.freshness.PageState(
                            url=url, status=200 if reachable else 0))


def test_an_identified_authority_is_usable(monkeypatch):
    canned(monkeypatch, {"authorities": [
        {"name": "NTA", "domain": "nta.nic.in", "why": "sets the exam date"}]})
    found = authority.identify("JEE is in April")
    assert found[0].usable
    assert authority.domains(found) == {"nta.nic.in"}


def test_an_invented_domain_is_kept_but_not_trusted(monkeypatch):
    """Models produce plausible domains for bodies that do not publish."""
    canned(monkeypatch, {"authorities": [
        {"name": "Ministry of Nothing", "domain": "notreal.example",
         "why": "invented"}]}, reachable=False)
    found = authority.identify("x")
    assert found[0].usable is False
    assert authority.domains(found) == set(), "unreachable domains never grade as primary"


def test_a_refused_domain_is_handled(monkeypatch):
    canned(monkeypatch, {"authorities": [
        {"name": "Board", "domain": "null", "why": "not sure"}]})
    found = authority.identify("x")
    assert found[0].domain is None
    assert found[0].usable is False


def test_urls_and_www_are_normalised(monkeypatch):
    canned(monkeypatch, {"authorities": [
        {"name": "NTA", "domain": "https://www.nta.nic.in/exams", "why": "x"}]})
    assert authority.identify("x")[0].domain == "nta.nic.in"


def test_authorities_round_trip_through_the_database(conn, monkeypatch):
    """The watchlist must survive, so the monitor re-checks stable pages."""
    canned(monkeypatch, {"authorities": [
        {"name": "NTA", "domain": "nta.nic.in", "why": "sets the date"}]})
    conn.execute("INSERT INTO claims (id, text) VALUES (1, 'JEE in April')")
    conn.commit()
    authority.store(conn, 1, authority.identify("JEE in April"))

    loaded = authority.load(conn, 1)
    assert loaded[0].name == "NTA"
    assert loaded[0].domain == "nta.nic.in"
    assert authority.domains(loaded) == {"nta.nic.in"}
