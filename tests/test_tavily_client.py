"""Retrieval must be replayable, cheap and honest about credits.

No network here. Fixtures are written into a temporary directory, so these
tests cost nothing and cannot touch the real credit balance.
"""

from __future__ import annotations

import json

import pytest

from falsifier import config
from falsifier.clients import tavily
from falsifier.memory import db

PAYLOAD = {
    "results": [
        {
            "url": "https://msande.stanford.edu/admission/stats",
            "title": "MS Admission Statistics",
            "content": "60% of the entering class enrolled directly from undergraduate study.",
            "published_date": "2026-09-01",
        },
        {
            "url": "https://someconsultant.example/blog",
            "title": "How to get into Stanford",
            "content": "Work experience always helps!",
        },
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """A temp database and a temp fixtures directory."""
    monkeypatch.setattr(config, "FIXTURES_DIR", tmp_path / "fixtures")
    monkeypatch.delenv("FALSIFIER_OFFLINE", raising=False)
    conn = db.init_db(tmp_path / "test.db")
    yield conn
    conn.close()


def fake_network(monkeypatch, payload=PAYLOAD):
    """Replace the Tavily client; record how many times it was called."""
    hits = []

    class Fake:
        def search(self, **kwargs):
            hits.append(kwargs)
            return payload

    monkeypatch.setattr(tavily, "client", lambda: Fake())
    return hits


def test_first_search_costs_a_credit_and_records_a_fixture(env, monkeypatch):
    hits = fake_network(monkeypatch)
    result = tavily.search("stanford class profile", conn=env)

    assert len(hits) == 1
    assert result.credits == 1
    assert result.from_cache is False
    assert len(result.results) == 2
    assert tavily.fixture_count() == 1


def test_second_identical_search_is_free(env, monkeypatch):
    """The whole point: a query is only ever paid for once."""
    hits = fake_network(monkeypatch)
    tavily.search("stanford class profile", conn=env)
    replay = tavily.search("stanford class profile", conn=env)

    assert len(hits) == 1, "the network must not be touched twice"
    assert replay.credits == 0
    assert replay.from_cache is True
    assert tavily.credits_spent(env) == 1


def test_search_depth_is_pinned_to_basic(env, monkeypatch):
    """auto_parameters can silently promote to advanced and double the cost."""
    hits = fake_network(monkeypatch)
    tavily.search("anything", conn=env)
    assert hits[0]["search_depth"] == "basic"
    assert hits[0]["auto_parameters"] is False


def test_offline_mode_replays_without_network(env, monkeypatch):
    hits = fake_network(monkeypatch)
    tavily.search("recorded query", conn=env)
    monkeypatch.setenv("FALSIFIER_OFFLINE", "1")

    replay = tavily.search("recorded query", conn=env)
    assert len(hits) == 1
    assert replay.from_cache is True
    assert len(replay.results) == 2


def test_offline_mode_refuses_an_unrecorded_query(env, monkeypatch):
    """Better a loud error than a silent credit spend during development."""
    hits = fake_network(monkeypatch)
    monkeypatch.setenv("FALSIFIER_OFFLINE", "1")

    with pytest.raises(tavily.FixtureMissing):
        tavily.search("never seen before", conn=env)
    assert hits == []


def test_search_ceiling_refuses_before_sending(env, monkeypatch):
    hits = fake_network(monkeypatch)
    env.execute("INSERT INTO claims (id, text) VALUES (1, 'c')")
    env.execute("INSERT INTO runs (id, claim_id, mode) VALUES (3, 1, 'personal')")
    env.execute(
        "INSERT INTO searches (run_id, query, credits, from_cache) "
        "VALUES (3, 'prior', ?, 0)",
        (config.MAX_SEARCHES_PER_RUN,),
    )
    env.commit()

    with pytest.raises(tavily.SearchBudgetExceeded):
        tavily.search("one too many", run_id=3, conn=env)
    assert hits == []


def test_undated_results_are_flagged(env, monkeypatch):
    fake_network(monkeypatch)
    result = tavily.search("stanford", conn=env)
    dated, undated = result.results
    assert dated.undated is False
    assert undated.undated is True, "a source with no date must be flagged"


def test_results_are_stored_against_the_search(env, monkeypatch):
    fake_network(monkeypatch)
    result = tavily.search("stanford", conn=env)
    rows = env.execute(
        "SELECT url, published_date FROM results WHERE search_id = ?",
        (result.search_id,),
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["url"].startswith("https://msande.stanford.edu")


def test_cache_replays_do_not_inflate_credits_spent(env, monkeypatch):
    """Credit accounting must count network calls, not cache hits."""
    fake_network(monkeypatch)
    for _ in range(5):
        tavily.search("same query", conn=env)
    assert tavily.credits_spent(env) == 1


def test_corrupt_fixture_surfaces_rather_than_passing_empty(env, monkeypatch):
    fake_network(monkeypatch)
    tavily.search("stanford", conn=env)
    path = tavily.fixture_path("stanford", "basic", 5)
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        tavily.search("stanford", conn=env)
