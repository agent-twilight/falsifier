"""The single door every model call goes through.

One sentence: call `complete()` instead of the OpenAI client, and every call
is timed, priced and written to the `calls` table.

Nothing else in the codebase may construct an OpenAI client. Three things
depend on that being true:

- the README's cost table is a query over `calls`, not an estimate
- the spend cap (step 9) can only stop a call it can see
- the tiering argument needs per-tier volume counted, not guessed

It also closes the trap found on 17 Oct: these are reasoning models, and a
tight `max_tokens` makes them spend the whole budget thinking and return an
empty string with `finish_reason="stop"`. That looks like success. Here it is
an error.
"""

from __future__ import annotations

import random
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from falsifier import config
from falsifier.memory import db

_client: OpenAI | None = None


class ModelCallError(RuntimeError):
    """A call failed, or returned something unusable."""


class EmptyCompletion(ModelCallError):
    """The model returned no content, usually having spent max_tokens thinking."""


class BudgetExceeded(ModelCallError):
    """A cap would have been breached. No request was sent, nothing was spent."""


# Transient network faults. Seen live on 18 Oct: a dropped connection
# mid-run cost nine stages of a single claim, because one blip was treated
# the same as a real refusal. A 490-call pipeline will meet these routinely,
# so they are retried with backoff rather than reported as failures.
TRANSIENT = ("APIConnectionError", "APITimeoutError", "ConnectionError",
             "Timeout", "ReadTimeout", "RateLimitError",
             "InternalServerError", "ServiceUnavailable")
MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Completion:
    """What a successful call produced, plus what it cost."""

    text: str
    reasoning: str
    tier: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    call_id: int
    truncated: bool = False


def client() -> OpenAI:
    """The one OpenAI client, pointed at Token Factory."""
    global _client
    if _client is None:
        missing = config.missing_credentials()
        if missing:
            raise ModelCallError(f"Missing settings in .env: {', '.join(missing)}")
        _client = OpenAI(
            api_key=config.NEBIUS_API_KEY, base_url=config.NEBIUS_BASE_URL
        )
    return _client


def _log(
    conn: sqlite3.Connection | None,
    **fields: Any,
) -> int:
    """Write one row to `calls`. Returns its id."""
    owned = conn is None
    connection = conn or db.connect()
    try:
        cursor = connection.execute(
            "INSERT INTO calls (run_id, tier, model, stage, input_tokens, "
            "output_tokens, latency_ms, cost_usd, ok, error) "
            "VALUES (:run_id, :tier, :model, :stage, :input_tokens, "
            ":output_tokens, :latency_ms, :cost_usd, :ok, :error)",
            fields,
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        if owned:
            connection.close()


def _estimate_input_tokens(messages: list[dict[str, str]]) -> int:
    """Cheap upper-ish estimate. Roughly four characters per token.

    Deliberately not exact: the point is to refuse a call *before* sending it,
    and an approximate bound is enough for a circuit breaker. The real token
    count is recorded afterwards from the API response.
    """
    characters = sum(len(message["content"]) for message in messages)
    return characters // 4 + 20


def check_budget(
    tier: config.Tier,
    messages: list[dict[str, str]],
    max_tokens: int,
    run_id: int | None,
    conn: sqlite3.Connection | None,
) -> None:
    """Raise BudgetExceeded if this call could breach a cap.

    Checked before the request is sent, and costed at the worst case: the
    prompt as estimated, plus the full max_tokens as output. A cap that only
    notices after the money is gone is not a cap.

    Refusals are deliberately NOT written to `calls`. That table means
    "requests actually sent", and the README's per-tier volume is computed
    from it. A run halted by the cap is recorded on `runs.status` instead.
    """
    owned = conn is None
    connection = conn or db.connect()
    try:
        total = spend_total(connection)
        today = spend_today(connection)
        worst_case = tier.cost(_estimate_input_tokens(messages), max_tokens)

        if total + worst_case > config.TOTAL_BUDGET_USD:
            raise BudgetExceeded(
                f"total budget: ${total:.4f} spent, this call could add "
                f"${worst_case:.4f}, ceiling ${config.TOTAL_BUDGET_USD:.2f}"
            )
        if today + worst_case > config.DAILY_SPEND_CAP_USD:
            raise BudgetExceeded(
                f"daily cap: ${today:.4f} spent today, this call could add "
                f"${worst_case:.4f}, ceiling ${config.DAILY_SPEND_CAP_USD:.2f}"
            )
        if run_id is not None:
            calls_so_far = connection.execute(
                "SELECT count(*) FROM calls WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            if calls_so_far >= config.MAX_CALLS_PER_RUN:
                raise BudgetExceeded(
                    f"run {run_id} has made {calls_so_far} calls, ceiling "
                    f"{config.MAX_CALLS_PER_RUN}. Likely a retry loop."
                )
    finally:
        if owned:
            connection.close()


def complete(
    tier: config.Tier,
    prompt: str,
    *,
    stage: str,
    system: str | None = None,
    no_think: bool = False,
    max_tokens: int = config.MAX_TOKENS_FLOOR,
    temperature: float = 0.0,
    run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
    retry_on_overrun: bool = True,
) -> Completion:
    """Send one prompt to one tier, log it, and return the answer.

    `stage` names the pipeline step ("triage", "decompose", ...) so per-stage
    volume can be reported later. `no_think` suppresses most reasoning, which
    cut measured triage output from 190 tokens to 108.

    Raises EmptyCompletion if the model returns no usable content.
    """
    if max_tokens < config.MAX_TOKENS_FLOOR:
        raise ValueError(
            f"max_tokens={max_tokens} is below MAX_TOKENS_FLOOR="
            f"{config.MAX_TOKENS_FLOOR}. These are reasoning models: a tight "
            "budget is spent thinking and returns empty content."
        )

    messages: list[dict[str, str]] = []
    if no_think:
        messages.append({"role": "system", "content": config.NO_THINK_SYSTEM_PROMPT})
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    check_budget(tier, messages, max_tokens, run_id, conn)

    row = {
        "run_id": run_id,
        "tier": tier.name,
        "model": tier.model_id,
        "stage": stage,
        "input_tokens": 0,
        "output_tokens": 0,
        "latency_ms": 0,
        "cost_usd": 0.0,
        "ok": 1,
        "error": None,
    }

    started = time.monotonic()
    response = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client().chat.completions.create(
                model=tier.model_id,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            break
        except Exception as exc:  # noqa: BLE001 - log it, then decide
            name = type(exc).__name__
            transient = any(marker in name for marker in TRANSIENT)
            row["latency_ms"] = int((time.monotonic() - started) * 1000)
            row["ok"] = 0
            row["error"] = f"{name}: {exc}"[:500]
            if transient and attempt < MAX_ATTEMPTS:
                row["error"] = f"[retry {attempt}] {row['error']}"[:500]
                _log(conn, **row)
                # Exponential backoff with jitter, so a wobble upstream is
                # not met by every pending call hammering it in lockstep.
                time.sleep(min(8.0, 2 ** (attempt - 1)) * (0.5 + random.random()))
                started = time.monotonic()
                continue
            _log(conn, **row)
            raise ModelCallError(row["error"]) from exc

    latency_ms = int((time.monotonic() - started) * 1000)
    usage = response.usage
    message = response.choices[0].message
    text = (message.content or "").strip()
    reasoning = (getattr(message, "reasoning", None) or "").strip()

    row.update(
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
        latency_ms=latency_ms,
        # Billed whether or not the content was usable.
        cost_usd=tier.cost(usage.prompt_tokens, usage.completion_tokens),
        # Cleared explicitly: a retry leaves the previous attempt's failure
        # in this dict, which would log the eventual success as an error.
        ok=1,
        error=None,
    )

    if not text:
        finish_reason = response.choices[0].finish_reason
        row["ok"] = 0
        row["error"] = (
            f"empty content, finish_reason={finish_reason}, "
            f"{len(reasoning)} chars of reasoning, max_tokens={max_tokens}"
        )
        _log(conn, **row)

        # Ran out of room mid-thought rather than genuinely having nothing
        # to say. Retry once with double the budget, so one unlucky call
        # does not abort a 490-call run.
        if finish_reason == "length" and retry_on_overrun:
            return complete(
                tier, prompt, stage=stage, system=system, no_think=no_think,
                max_tokens=max_tokens * 2, temperature=temperature,
                run_id=run_id, conn=conn, retry_on_overrun=False,
            )
        raise EmptyCompletion(row["error"])

    call_id = _log(conn, **row)
    return Completion(
        text=text,
        reasoning=reasoning,
        tier=tier.name,
        model=tier.model_id,
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        latency_ms=latency_ms,
        cost_usd=row["cost_usd"],
        call_id=call_id,
        truncated=response.choices[0].finish_reason == "length",
    )


def spend_today(conn: sqlite3.Connection | None = None) -> float:
    """Dollars spent since midnight, from logged calls. Used by the cap."""
    owned = conn is None
    connection = conn or db.connect()
    try:
        return connection.execute(
            "SELECT coalesce(sum(cost_usd), 0) FROM calls "
            "WHERE date(created_at) = date('now')"
        ).fetchone()[0]
    finally:
        if owned:
            connection.close()


def spend_total(conn: sqlite3.Connection | None = None) -> float:
    """Dollars spent across every logged call."""
    owned = conn is None
    connection = conn or db.connect()
    try:
        return connection.execute(
            "SELECT coalesce(sum(cost_usd), 0) FROM calls"
        ).fetchone()[0]
    finally:
        if owned:
            connection.close()
