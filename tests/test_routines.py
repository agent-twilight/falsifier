"""The agent must write a routine for a domain it has not met, and keep it.

Three hand-written routines cover three kinds of question. A user brings
whatever they bring. So an unfamiliar domain gets a routine written for it
and stored, rather than being forced through a generic one whose sources
point somewhere useless.
"""

from __future__ import annotations

import pytest

from falsifier.memory import db, routines
from falsifier.pipeline import parsing

BALLET = {
    "name": "late-entry-profession",
    "description": "Claims about reaching professional level starting late.",
    "applies_when": "the claim is about entering a skilled profession late",
    "angles": [
        ["AGE_LIMITS", "development peaks before the claimed start age"],
        ["ACCESS_BARRIERS", "elite schools rarely accept adult beginners"],
        ["INJURY_RISK", "late starters face higher injury rates"],
        ["PRACTICE_HOURS", "insufficient time to accumulate the hours"],
    ],
    "primary_sources": "dance school admission statistics, IADMS guidance",
    "weak_sources": "motivational blogs, influencer testimonials",
    "decompose_guidance": "separate physical, access and market constraints",
    "query_guidance": "use audition and admission vocabulary",
}


@pytest.fixture()
def conn(tmp_path):
    connection = db.init_db(tmp_path / "t.db")
    routines.seed(connection)
    yield connection
    connection.close()


def answers(monkeypatch, classification, generated=BALLET):
    """Stub the classifier reply and the generator reply."""
    import types

    def fake_complete(tier, prompt, **kwargs):
        return types.SimpleNamespace(text=classification)

    import falsifier.clients.nebius as nebius_mod

    monkeypatch.setattr(nebius_mod, "complete", fake_complete)
    monkeypatch.setattr(parsing, "complete_json", lambda *a, **k: generated)


def test_the_three_built_ins_are_seeded(conn):
    names = {r.name for r in routines.available(conn)}
    assert {"existence", "requirement", "effect"} <= names


def test_a_known_claim_type_reuses_a_built_in(monkeypatch, conn):
    answers(monkeypatch, "requirement")
    chosen = routines.classify("Stanford requires a degree", conn=conn)
    assert chosen.name == "requirement"
    assert chosen.generated is False


def test_an_unfamiliar_domain_gets_a_new_routine(monkeypatch, conn):
    answers(monkeypatch, "none")
    chosen = routines.classify("Can I turn professional in ballet at 22?", conn=conn)
    assert chosen.generated is True
    assert chosen.name == "late-entry-profession"
    assert ("AGE_LIMITS", "development peaks before the claimed start age") in chosen.angles


def test_a_generated_routine_is_stored_for_next_time(monkeypatch, conn):
    answers(monkeypatch, "none")
    routines.classify("ballet at 22", conn=conn)
    stored = {r.name for r in routines.available(conn)}
    assert "late-entry-profession" in stored

    row = conn.execute(
        "SELECT generated FROM routines WHERE name = 'late-entry-profession'"
    ).fetchone()
    assert row["generated"] == 1, "marked as written by the agent, not built in"


def test_a_stored_routine_survives_a_reload(monkeypatch, conn):
    """It has to come back with its angles intact, or reuse is worthless."""
    answers(monkeypatch, "none")
    routines.classify("ballet at 22", conn=conn)

    reloaded = next(
        r for r in routines.available(conn) if r.name == "late-entry-profession"
    )
    assert len(reloaded.angles) == 4
    assert reloaded.primary_sources.startswith("dance school")
    assert reloaded.weak_sources.startswith("motivational")


def test_use_is_counted_so_useful_routines_are_visible(monkeypatch, conn):
    answers(monkeypatch, "requirement")
    for _ in range(3):
        routines.classify("Stanford requires a degree", conn=conn)
    row = conn.execute(
        "SELECT times_used FROM routines WHERE name = 'requirement'"
    ).fetchone()
    assert row["times_used"] == 3


def test_a_thin_routine_is_refused(monkeypatch, conn):
    """Two angles is not a routine, and storing it would poison every
    future claim in that domain."""
    thin = dict(BALLET, angles=[["ONE", "only angle"]])
    answers(monkeypatch, "none", generated=thin)
    chosen = routines.classify("something unfamiliar", conn=conn)
    assert chosen.generated is False, "fell back rather than storing rubbish"
    assert "late-entry-profession" not in {r.name for r in routines.available(conn)}


def test_an_unnamed_routine_is_refused(monkeypatch, conn):
    nameless = dict(BALLET, name="")
    answers(monkeypatch, "none", generated=nameless)
    assert routines.classify("something unfamiliar", conn=conn).generated is False


def test_a_generated_name_cannot_overwrite_a_built_in(monkeypatch, conn):
    clash = dict(BALLET, name="effect")
    answers(monkeypatch, "none", generated=clash)
    chosen = routines.classify("something unfamiliar", conn=conn)
    assert chosen.name == "effect-2"
    assert routines.BY_NAME["effect"].generated is False


def test_generation_failure_falls_back_rather_than_crashing(monkeypatch, conn):
    def boom(*a, **k):
        raise parsing.ParseError("model returned nonsense")

    import types
    import falsifier.clients.nebius as nebius_mod

    monkeypatch.setattr(
        nebius_mod, "complete", lambda *a, **k: types.SimpleNamespace(text="none")
    )
    monkeypatch.setattr(parsing, "complete_json", boom)

    chosen = routines.classify("something unfamiliar", conn=conn)
    assert chosen is routines.DEFAULT
