"""The wrapper must log every call, including the ones that fail.

No network here: the OpenAI client is replaced with a fake, so these run
free and fast. The real call is covered by scripts/check_setup.py.
"""

from __future__ import annotations

import types

import pytest

from falsifier import config
from falsifier.clients import nebius
from falsifier.memory import db


@pytest.fixture()
def conn(tmp_path):
    connection = db.init_db(tmp_path / "test.db")
    yield connection
    connection.close()


def fake_response(content, reasoning="", prompt_tokens=100, completion_tokens=50,
                  finish_reason="stop"):
    message = types.SimpleNamespace(content=content, reasoning=reasoning)
    choice = types.SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = types.SimpleNamespace(
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
    )
    return types.SimpleNamespace(choices=[choice], usage=usage)


def install_fake(monkeypatch, response=None, raises=None):
    """Replace the OpenAI client with one that returns or raises as told."""
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if raises is not None:
            raise raises
        return response

    fake = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    monkeypatch.setattr(nebius, "client", lambda: fake)
    return calls


def test_rejects_max_tokens_below_the_floor(monkeypatch, conn):
    """The reasoning-model trap: too tight a budget yields empty content."""
    calls = install_fake(monkeypatch, fake_response("hi"))
    with pytest.raises(ValueError, match="MAX_TOKENS_FLOOR"):
        nebius.complete(config.NANO, "x", stage="triage", max_tokens=16, conn=conn)
    assert calls == [], "no request should be sent"
    assert conn.execute("SELECT count(*) FROM calls").fetchone()[0] == 0


def test_successful_call_logs_every_field(monkeypatch, conn):
    install_fake(monkeypatch, fake_response("YES", reasoning="thinking...",
                                            prompt_tokens=1000, completion_tokens=110))
    result = nebius.complete(config.NANO, "x", stage="triage", conn=conn)

    assert result.text == "YES"
    assert result.reasoning == "thinking..."
    expected = config.NANO.cost(1000, 110)
    assert result.cost_usd == pytest.approx(expected)

    row = conn.execute("SELECT * FROM calls").fetchone()
    assert row["tier"] == "nano"
    assert row["stage"] == "triage"
    assert row["input_tokens"] == 1000
    assert row["output_tokens"] == 110
    assert row["ok"] == 1
    assert row["error"] is None
    assert row["cost_usd"] == pytest.approx(expected)


def test_empty_content_is_an_error_not_a_success(monkeypatch, conn):
    """An empty string with finish_reason=stop must not pass as a result."""
    install_fake(monkeypatch, fake_response("", reasoning="spent it all thinking"))
    with pytest.raises(nebius.EmptyCompletion):
        nebius.complete(config.NANO, "x", stage="triage", conn=conn)

    row = conn.execute("SELECT * FROM calls").fetchone()
    assert row["ok"] == 0
    assert "empty content" in row["error"]
    # Billed even though unusable, so the spend figure stays honest.
    assert row["cost_usd"] > 0


def test_api_failure_is_logged_then_raised(monkeypatch, conn):
    install_fake(monkeypatch, raises=TimeoutError("connection reset"))
    with pytest.raises(nebius.ModelCallError, match="connection reset"):
        nebius.complete(config.SUPER, "x", stage="read", conn=conn)

    row = conn.execute("SELECT * FROM calls").fetchone()
    assert row["ok"] == 0
    assert row["tier"] == "super"
    assert "TimeoutError" in row["error"]
    assert row["cost_usd"] == 0, "a failed request bills nothing"


def test_no_think_prepends_the_system_prompt(monkeypatch, conn):
    calls = install_fake(monkeypatch, fake_response("YES"))
    nebius.complete(config.NANO, "x", stage="triage", no_think=True, conn=conn)
    assert calls[0]["messages"][0] == {
        "role": "system",
        "content": config.NO_THINK_SYSTEM_PROMPT,
    }


def test_spend_totals_come_from_logged_calls(monkeypatch, conn):
    install_fake(monkeypatch, fake_response("ok", prompt_tokens=1_000_000,
                                            completion_tokens=0))
    nebius.complete(config.NANO, "x", stage="triage", conn=conn)
    nebius.complete(config.ULTRA, "x", stage="survive", conn=conn)
    # 1M input tokens: $0.06 at Nano, $1.00 at Ultra.
    assert nebius.spend_total(conn) == pytest.approx(1.06)
    assert nebius.spend_today(conn) == pytest.approx(1.06)


def test_failed_calls_still_count_toward_tier_volume(monkeypatch, conn):
    """Per-tier volume in the README must include failures, or it overstates."""
    install_fake(monkeypatch, raises=RuntimeError("boom"))
    for _ in range(3):
        with pytest.raises(nebius.ModelCallError):
            nebius.complete(config.NANO, "x", stage="triage", conn=conn)
    count = conn.execute(
        "SELECT count(*) FROM calls WHERE tier='nano'"
    ).fetchone()[0]
    assert count == 3


# ---------------------------------------------------------------------------
# Step 9: the spend cap. A cap that notices after the money is gone is not a
# cap, so every test here asserts that NO request was sent.
# ---------------------------------------------------------------------------


def _spend(conn, dollars):
    """Put a known amount of historical spend in the calls table."""
    conn.execute(
        "INSERT INTO calls (tier, model, stage, cost_usd) "
        "VALUES ('nano', 'm', 'seed', ?)",
        (dollars,),
    )
    conn.commit()


def test_total_budget_cap_refuses_before_sending(monkeypatch, conn):
    calls = install_fake(monkeypatch, fake_response("hi"))
    _spend(conn, config.TOTAL_BUDGET_USD)

    with pytest.raises(nebius.BudgetExceeded, match="total budget"):
        nebius.complete(config.NANO, "x", stage="triage", conn=conn)

    assert calls == [], "no request may be sent once the budget is gone"


def test_daily_cap_refuses_before_sending(monkeypatch, conn):
    calls = install_fake(monkeypatch, fake_response("hi"))
    _spend(conn, config.DAILY_SPEND_CAP_USD)

    with pytest.raises(nebius.BudgetExceeded, match="daily cap"):
        nebius.complete(config.NANO, "x", stage="triage", conn=conn)

    assert calls == []


def test_per_run_call_ceiling_catches_a_retry_loop(monkeypatch, conn):
    """The failure mode named in the project's own risk list."""
    calls = install_fake(monkeypatch, fake_response("hi"))
    conn.execute("INSERT INTO claims (id, text) VALUES (1, 'a claim')")
    conn.execute("INSERT INTO runs (id, claim_id, mode) VALUES (7, 1, 'personal')")
    for _ in range(config.MAX_CALLS_PER_RUN):
        conn.execute(
            "INSERT INTO calls (run_id, tier, model, stage) "
            "VALUES (7, 'nano', 'm', 'triage')"
        )
    conn.commit()

    with pytest.raises(nebius.BudgetExceeded, match="retry loop"):
        nebius.complete(config.NANO, "x", stage="triage", run_id=7, conn=conn)

    assert calls == []


def test_refusals_are_not_logged_as_calls(monkeypatch, conn):
    """`calls` means requests actually sent, or per-tier volume is wrong."""
    install_fake(monkeypatch, fake_response("hi"))
    _spend(conn, config.TOTAL_BUDGET_USD)
    before = conn.execute("SELECT count(*) FROM calls").fetchone()[0]

    with pytest.raises(nebius.BudgetExceeded):
        nebius.complete(config.NANO, "x", stage="triage", conn=conn)

    after = conn.execute("SELECT count(*) FROM calls").fetchone()[0]
    assert after == before


def test_cap_accounts_for_the_cost_this_call_could_add(monkeypatch, conn):
    """Refuse when the worst case would breach, not only once it has."""
    calls = install_fake(monkeypatch, fake_response("hi"))
    # Just under the daily cap, but one Ultra call at max_tokens exceeds it.
    _spend(conn, config.DAILY_SPEND_CAP_USD - 0.001)

    with pytest.raises(nebius.BudgetExceeded):
        nebius.complete(config.ULTRA, "x" * 4000, stage="survive",
                        max_tokens=2000, conn=conn)

    assert calls == []


def test_a_call_within_budget_still_goes_through(monkeypatch, conn):
    """The cap must not block ordinary work."""
    calls = install_fake(monkeypatch, fake_response("YES"))
    _spend(conn, 0.0001)
    result = nebius.complete(config.NANO, "x", stage="triage", conn=conn)
    assert result.text == "YES"
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# Transient network faults. A dropped connection cost nine stages of a real
# run on 18 Oct; one blip must not be treated as a refusal.
# ---------------------------------------------------------------------------


def install_flaky(monkeypatch, fail_times, error, then=None):
    """Fail the first `fail_times` calls, then succeed."""
    state = {"n": 0}

    def create(**kwargs):
        state["n"] += 1
        if state["n"] <= fail_times:
            raise error
        return then or fake_response("YES")

    monkeypatch.setattr(nebius, "client", lambda: types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))))
    monkeypatch.setattr(nebius.time, "sleep", lambda s: None)
    return state


class APIConnectionError(Exception):
    pass


def test_a_transient_fault_is_retried_and_succeeds(monkeypatch, conn):
    state = install_flaky(monkeypatch, 2, APIConnectionError("connection reset"))
    result = nebius.complete(config.NANO, "x", stage="triage", conn=conn)
    assert result.text == "YES"
    assert state["n"] == 3, "two failures then a success"


def test_retries_are_logged_so_flakiness_is_visible(monkeypatch, conn):
    install_flaky(monkeypatch, 1, APIConnectionError("reset"))
    nebius.complete(config.NANO, "x", stage="triage", conn=conn)
    rows = conn.execute("SELECT ok, error FROM calls ORDER BY id").fetchall()
    assert rows[0]["ok"] == 0 and "[retry 1]" in rows[0]["error"]
    assert rows[-1]["ok"] == 1


def test_gives_up_after_the_attempt_limit(monkeypatch, conn):
    state = install_flaky(monkeypatch, 99, APIConnectionError("still down"))
    with pytest.raises(nebius.ModelCallError):
        nebius.complete(config.NANO, "x", stage="triage", conn=conn)
    assert state["n"] == nebius.MAX_ATTEMPTS


def test_a_real_error_is_not_retried(monkeypatch, conn):
    """Retrying a genuine rejection just wastes time and money."""
    state = install_flaky(monkeypatch, 99, ValueError("bad model id"))
    with pytest.raises(nebius.ModelCallError):
        nebius.complete(config.NANO, "x", stage="triage", conn=conn)
    assert state["n"] == 1, "non-transient errors fail immediately"
