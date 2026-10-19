"""One bad stage must not destroy a run.

A claim with several assumptions should still produce a report when one of
them fails, with the failure written down rather than swallowed. These tests
break each stage in turn and check the run survives.

No network and no model calls: every stage is replaced.
"""

from __future__ import annotations

import pytest

from falsifier import artifact, config
from falsifier.clients import nebius, tavily
from falsifier.memory import db
from falsifier.memory import routines
from falsifier.pipeline import (
    angles, authority, decompose, hypothesise, parsing, read, run, verdict,
)

EVIDENCE = read.Evidence(
    quote="Applicants must hold a Bachelor's degree.",
    url="https://cs.stanford.edu/admissions",
    title="Admissions",
    source_tier="primary",
    bearing="ABSENT",
    published_date=None,
)


@pytest.fixture()
def wired(tmp_path, monkeypatch):
    """A working pipeline with every external edge stubbed out."""
    monkeypatch.setattr(config, "FIXTURES_DIR", tmp_path / "fx")
    conn = db.init_db(tmp_path / "t.db")

    # Stub the stages that reach the network. Without these the suite made
    # live API calls: real money, and a test run that needs the internet.
    monkeypatch.setattr(routines, "classify", lambda c, **kw: routines.REQUIREMENT)
    monkeypatch.setattr(authority, "identify", lambda c, **kw: [
        authority.Authority("Stanford", "stanford.edu", "sets its own rules", True)
    ])

    monkeypatch.setattr(decompose, "decompose", lambda claim, **kw: _decomp(conn, kw))
    monkeypatch.setattr(hypothesise, "hypothesise", lambda c, s, **kw: _hyps(conn, kw))
    monkeypatch.setattr(angles, "angles", lambda c, h, **kw: ["a query"])
    monkeypatch.setattr(tavily, "search", lambda q, **kw: tavily.Search(
        query=q, results=[tavily.Result("https://cs.stanford.edu/admissions",
                                        "Admissions", "Applicants must hold a Bachelor's degree.")],
        credits=1))
    monkeypatch.setattr(read, "triage", lambda *a, **kw: True)
    monkeypatch.setattr(read, "read", lambda *a, **kw: EVIDENCE)
    monkeypatch.setattr(verdict, "judge", lambda c, s, ev, **kw: verdict.Verdict(
        verdict.SUPPORTED if ev else verdict.UNVERIFIABLE,
        "It held up." if ev else "Could not settle.",
        evidence=ev[0] if ev else None,
        reason=None if ev else "nothing retrieved", sub_claim=s))
    monkeypatch.setattr(run.freshness, "check", lambda url, **kw: run.freshness.PageState(
        url=url, status=200))
    monkeypatch.setattr(nebius, "spend_total", lambda *a, **k: 0.0)
    monkeypatch.setattr(tavily, "credits_spent", lambda *a, **k: 0)
    yield conn
    conn.close()


def _decomp(conn, kw):
    if kw.get("claim_id"):
        conn.executemany(
            "INSERT INTO sub_claims (claim_id, text, position) VALUES (?, ?, ?)",
            [(kw["claim_id"], "assumption one", 0), (kw["claim_id"], "assumption two", 1)],
        )
        conn.commit()
    return decompose.Decomposition(["assumption one", "assumption two"], [])


def _hyps(conn, kw):
    if kw.get("sub_claim_id"):
        conn.execute("INSERT INTO hypotheses (sub_claim_id, text) VALUES (?, ?)",
                     (kw["sub_claim_id"], "a hypothesis"))
        conn.commit()
    return ["a hypothesis"]


def test_a_clean_run_produces_findings_and_a_funnel(wired):
    result = run.investigate("a claim", profile="quick", conn=wired)
    assert result.funnel.searches > 0
    assert result.funnel.quotes_verified > 0
    assert result.report.supported
    assert result.failures == []
    stored = wired.execute("SELECT count(*) FROM findings").fetchone()[0]
    assert stored == 2


def test_a_failing_stage_is_recorded_not_raised(wired, monkeypatch):
    monkeypatch.setattr(angles, "angles", lambda *a, **kw: (_ for _ in ()).throw(
        parsing.ParseError("model returned nonsense")))
    result = run.investigate("a claim", profile="quick", conn=wired)
    assert result.failures, "the failure must be reported"
    assert "nonsense" in result.failures[0]
    assert result.report.verdicts, "the run still produced verdicts"


def test_search_failure_does_not_abort_the_run(wired, monkeypatch):
    monkeypatch.setattr(tavily, "search", lambda q, **kw: (_ for _ in ()).throw(
        tavily.SearchError("Tavily timed out")))
    result = run.investigate("a claim", profile="quick", conn=wired)
    assert any("timed out" in f for f in result.failures)
    assert result.report.unverifiable, "with no evidence it must say so"


def test_hitting_the_search_ceiling_stops_searching_but_still_reports(wired, monkeypatch):
    monkeypatch.setattr(tavily, "search", lambda q, **kw: (_ for _ in ()).throw(
        tavily.SearchBudgetExceeded("run 1 has spent 45 search credits")))
    result = run.investigate("a claim", profile="quick", conn=wired)
    assert any("ceiling" in f for f in result.failures)
    assert result.report.verdicts


def test_a_failing_verdict_becomes_unverifiable_not_a_crash(wired, monkeypatch):
    monkeypatch.setattr(verdict, "judge", lambda *a, **kw: (_ for _ in ()).throw(
        nebius.ModelCallError("502 from upstream")))
    result = run.investigate("a claim", profile="quick", conn=wired)
    assert all(v.stance == verdict.UNVERIFIABLE for v in result.report.verdicts)
    assert any("502" in f for f in result.failures)


def test_rejected_quotes_are_counted(wired, monkeypatch):
    """A discarded quote is a number in the funnel, not a silent drop."""
    monkeypatch.setattr(read, "read", lambda *a, **kw: None)
    result = run.investigate("a claim", profile="quick", conn=wired)
    assert result.funnel.quotes_rejected > 0
    assert result.funnel.quotes_verified == 0


def test_the_run_row_records_the_funnel(wired):
    result = run.investigate("a claim", profile="quick", conn=wired)
    row = wired.execute("SELECT * FROM runs WHERE id = ?", (result.run_id,)).fetchone()
    assert row["finished_at"] is not None
    assert row["n_searches"] == result.funnel.searches
    assert row["status"] == "complete"


def test_the_document_leads_with_the_verdict(wired, tmp_path):
    result = run.investigate("a claim", profile="quick", conn=wired)
    text = artifact.render(result)
    assert text.startswith("# a claim")
    assert "held up" in text
    assert "https://cs.stanford.edu/admissions" in text, "every finding shows its link"


def test_the_document_says_what_it_could_not_settle(wired, monkeypatch):
    monkeypatch.setattr(read, "read", lambda *a, **kw: None)
    result = run.investigate("a claim", profile="quick", conn=wired)
    text = artifact.render(result)
    assert "could not be settled" in text.lower()
    assert "nothing retrieved" in text


def test_the_document_reports_discarded_quotes(wired, monkeypatch):
    monkeypatch.setattr(read, "read", lambda *a, **kw: None)
    result = run.investigate("a claim", profile="quick", conn=wired)
    assert "could not be found word-for-word" in artifact.render(result)
