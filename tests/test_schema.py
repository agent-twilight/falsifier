"""The database must make an unsupported verdict impossible to store.

Rule 1, after the 18 Oct reframing: a finding that challenges or supports a
claim needs a retrieved quoted line and a live link; a finding that says
something is unverifiable needs a written reason instead. There is no third
option where the agent simply asserts a conclusion.

These tests check the constraint holds at the storage layer, where buggy
pipeline code cannot talk its way around it.
"""

from __future__ import annotations

import sqlite3

import pytest

from falsifier.memory import db


@pytest.fixture()
def conn(tmp_path):
    connection = db.init_db(tmp_path / "test.db")
    yield connection
    connection.close()


def _claim_chain(conn) -> tuple[int, int]:
    """A claim, a sub-claim and a hypothesis. Returns (claim_id, hypothesis_id)."""
    claim_id = conn.execute(
        "INSERT INTO claims (text) VALUES ('Two years of work helps my application')"
    ).lastrowid
    sub_id = conn.execute(
        "INSERT INTO sub_claims (claim_id, text) VALUES (?, 'The programme values work experience')",
        (claim_id,),
    ).lastrowid
    hyp_id = conn.execute(
        "INSERT INTO hypotheses (sub_claim_id, text) VALUES (?, 'Most admits come straight from undergrad')",
        (sub_id,),
    ).lastrowid
    return claim_id, hyp_id


def test_challenge_requires_evidence(conn):
    """The core of rule 1: a challenge with no evidence cannot be stored."""
    claim_id, hyp_id = _claim_chain(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO findings (claim_id, hypothesis_id, evidence_id, stance, text) "
            "VALUES (?, ?, NULL, 'challenges', 'Sounds risky to me')",
            (claim_id, hyp_id),
        )


def test_agreement_also_requires_evidence(conn):
    """Agreeing is a verdict too, so it needs a source like any other."""
    claim_id, hyp_id = _claim_chain(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO findings (claim_id, hypothesis_id, evidence_id, stance, text) "
            "VALUES (?, ?, NULL, 'supports', 'Seems right to me')",
            (claim_id, hyp_id),
        )


def test_unverifiable_requires_a_stated_reason(conn):
    """Saying 'cannot tell' is only honest if it says why."""
    claim_id, _ = _claim_chain(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO findings (claim_id, stance, text, reason) "
            "VALUES (?, 'unverifiable', 'Cannot determine', NULL)",
            (claim_id,),
        )


def test_unverifiable_with_a_reason_is_accepted(conn):
    claim_id, _ = _claim_chain(conn)
    conn.execute(
        "INSERT INTO findings (claim_id, stance, text, reason) VALUES "
        "(?, 'unverifiable', 'Cannot determine whether this applies to you', "
        "'You have not said which programme you are applying to.')",
        (claim_id,),
    )
    conn.commit()
    row = conn.execute("SELECT reason FROM findings").fetchone()
    assert "which programme" in row["reason"]


def test_unverifiable_may_not_smuggle_in_evidence(conn):
    """If there is evidence, it is not unverifiable."""
    claim_id, hyp_id = _claim_chain(conn)
    ev = conn.execute(
        "INSERT INTO evidence (hypothesis_id, quoted_line, url, source_tier) "
        "VALUES (?, 'a real line', 'https://example.edu', 'primary')",
        (hyp_id,),
    ).lastrowid
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO findings (claim_id, evidence_id, stance, text, reason) "
            "VALUES (?, ?, 'unverifiable', 'Cannot tell', 'no reason really')",
            (claim_id, ev),
        )


def test_stance_must_be_one_of_the_three(conn):
    claim_id, hyp_id = _claim_chain(conn)
    ev = conn.execute(
        "INSERT INTO evidence (hypothesis_id, quoted_line, url, source_tier) "
        "VALUES (?, 'a line', 'https://example.edu', 'primary')",
        (hyp_id,),
    ).lastrowid
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO findings (claim_id, evidence_id, stance, text) "
            "VALUES (?, ?, 'probably wrong', 'x')",
            (claim_id, ev),
        )


def test_evidence_requires_a_quoted_line(conn):
    _, hyp_id = _claim_chain(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO evidence (hypothesis_id, quoted_line, url, source_tier) "
            "VALUES (?, '   ', 'https://example.edu/profile', 'primary')",
            (hyp_id,),
        )


def test_evidence_requires_a_link(conn):
    _, hyp_id = _claim_chain(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO evidence (hypothesis_id, quoted_line, url, source_tier) "
            "VALUES (?, '60% admitted directly from undergrad', '', 'primary')",
            (hyp_id,),
        )


def test_source_tier_is_constrained(conn):
    _, hyp_id = _claim_chain(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO evidence (hypothesis_id, quoted_line, url, source_tier) "
            "VALUES (?, 'a line', 'https://example.edu', 'probably fine')",
            (hyp_id,),
        )


def test_a_properly_evidenced_finding_is_accepted(conn):
    """The positive case: with a line and a link, it stores."""
    claim_id, hyp_id = _claim_chain(conn)
    evidence_id = conn.execute(
        "INSERT INTO evidence (hypothesis_id, quoted_line, url, source_tier, source_date) "
        "VALUES (?, '60% of the entering class enrolled directly from undergraduate study', "
        "'https://example.edu/class-profile', 'primary', '2026-09-01')",
        (hyp_id,),
    ).lastrowid
    conn.execute(
        "INSERT INTO findings (claim_id, hypothesis_id, evidence_id, stance, text, confidence) "
        "VALUES (?, ?, ?, 'challenges', 'The published class profile shows most admits come straight from undergrad', 0.8)",
        (claim_id, hyp_id, evidence_id),
    )
    conn.commit()
    stored = conn.execute(
        "SELECT f.text, e.quoted_line, e.url, e.source_tier "
        "FROM findings f JOIN evidence e ON e.id = f.evidence_id"
    ).fetchone()
    assert stored["url"].startswith("https://")
    assert stored["source_tier"] == "primary"


def test_demo_mode_is_separable_from_personal(conn):
    """The public demo must never show personal claims."""
    conn.execute("INSERT INTO claims (text, mode) VALUES ('a personal belief', 'personal')")
    conn.execute("INSERT INTO claims (text, mode) VALUES ('a demo belief', 'demo')")
    conn.commit()
    demo = conn.execute("SELECT text FROM claims WHERE mode = 'demo'").fetchall()
    assert len(demo) == 1
    assert demo[0]["text"] == "a demo belief"


def test_mode_must_be_known(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO claims (text, mode) VALUES ('x', 'public-ish')")


def test_foreign_keys_are_enforced(conn):
    """SQLite leaves these off by default; connect() turns them on."""
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO sub_claims (claim_id, text) VALUES (9999, 'orphan')"
        )
