"""The database must make a fabricated objection impossible to store.

Rule 1 says: no objection without a retrieved, quoted line and a live link.
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


def test_objection_requires_evidence(conn):
    """The core of rule 1: an objection with no evidence cannot be stored."""
    claim_id, hyp_id = _claim_chain(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO objections (claim_id, hypothesis_id, evidence_id, text) "
            "VALUES (?, ?, NULL, 'Sounds risky to me')",
            (claim_id, hyp_id),
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


def test_a_properly_evidenced_objection_is_accepted(conn):
    """The positive case: with a line and a link, it stores."""
    claim_id, hyp_id = _claim_chain(conn)
    evidence_id = conn.execute(
        "INSERT INTO evidence (hypothesis_id, quoted_line, url, source_tier, source_date) "
        "VALUES (?, '60% of the entering class enrolled directly from undergraduate study', "
        "'https://example.edu/class-profile', 'primary', '2026-09-01')",
        (hyp_id,),
    ).lastrowid
    conn.execute(
        "INSERT INTO objections (claim_id, hypothesis_id, evidence_id, text, confidence) "
        "VALUES (?, ?, ?, 'The published class profile shows most admits come straight from undergrad', 0.8)",
        (claim_id, hyp_id, evidence_id),
    )
    conn.commit()
    stored = conn.execute(
        "SELECT o.text, e.quoted_line, e.url, e.source_tier "
        "FROM objections o JOIN evidence e ON e.id = o.evidence_id"
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
