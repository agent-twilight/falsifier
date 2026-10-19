"""The single door for retrieval, with a cache and an offline replay mode.

One sentence: call `search()` instead of Tavily directly, and every query is
costed in credits, logged, cached on disk, and replayable with no network.

Tavily credits are the binding constraint on this project - roughly 22 full
runs exist, against hundreds of claims affordable on Nebius. So three things
happen here that would be optional elsewhere:

1. **Every response is written to disk as a fixture.** The first real search
   for a query is the only one that ever costs a credit.
2. **Offline mode replays fixtures and refuses to touch the network.** Set
   FALSIFIER_OFFLINE=1 and the whole pipeline can be iterated on for free.
3. **search_depth is pinned to basic.** Tavily's auto_parameters can promote
   a query to advanced on its own and silently double the credit cost.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

from tavily import TavilyClient

from falsifier import config
from falsifier.memory import db

_client: TavilyClient | None = None


class SearchError(RuntimeError):
    """Retrieval failed, or was refused."""


class SearchBudgetExceeded(SearchError):
    """A search ceiling would be breached. Nothing was sent, no credit spent."""


class FixtureMissing(SearchError):
    """Offline mode, and this query has never been recorded."""


@dataclass(frozen=True)
class Result:
    """One retrieved page."""

    url: str
    title: str
    snippet: str
    published_date: str | None = None

    @property
    def undated(self) -> bool:
        return not self.published_date


@dataclass(frozen=True)
class Search:
    """What a query returned, and what it cost."""

    query: str
    results: list[Result] = field(default_factory=list)
    credits: int = 0
    from_cache: bool = False
    latency_ms: int = 0
    search_id: int | None = None


def offline() -> bool:
    """True when the network is off limits and only fixtures may be used."""
    return os.getenv("FALSIFIER_OFFLINE", "").strip() not in ("", "0", "false")


def client() -> TavilyClient:
    global _client
    if _client is None:
        if not config.TAVILY_API_KEY:
            raise SearchError("TAVILY_API_KEY is not set in .env")
        _client = TavilyClient(api_key=config.TAVILY_API_KEY)
    return _client


def fixture_path(query: str, depth: str, max_results: int):
    """Where a given query's recorded response lives.

    Hashed rather than named after the query, because queries contain
    characters that are not legal in filenames.
    """
    key = f"{depth}|{max_results}|{query.strip().lower()}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return config.FIXTURES_DIR / f"{digest}.json"


def _parse(payload: dict[str, Any]) -> list[Result]:
    results = []
    for item in payload.get("results", []):
        results.append(
            Result(
                url=item.get("url", ""),
                title=item.get("title", "") or "",
                snippet=item.get("content", "") or "",
                published_date=item.get("published_date") or None,
            )
        )
    return results


def _check_search_budget(run_id: int | None, conn: sqlite3.Connection) -> None:
    """Refuse before sending, same principle as the model spend cap."""
    if run_id is None:
        return
    spent = conn.execute(
        "SELECT coalesce(sum(credits), 0) FROM searches "
        "WHERE run_id = ? AND from_cache = 0",
        (run_id,),
    ).fetchone()[0]
    if spent >= config.MAX_SEARCHES_PER_RUN:
        raise SearchBudgetExceeded(
            f"run {run_id} has spent {spent} search credits, ceiling "
            f"{config.MAX_SEARCHES_PER_RUN}"
        )


def search(
    query: str,
    *,
    run_id: int | None = None,
    hypothesis_id: int | None = None,
    max_results: int = 5,
    conn: sqlite3.Connection | None = None,
    store_results: bool = True,
    force_fresh: bool = False,
) -> Search:
    """Run one query, preferring a recorded fixture over the network.

    Costs a credit only on a genuine network call. Replays are free, and in
    offline mode a missing fixture is an error rather than a silent request.
    """
    depth = config.TAVILY_SEARCH_DEPTH
    path = fixture_path(query, depth, max_results)
    owned = conn is None
    connection = conn or db.connect()

    try:
        started = time.monotonic()
        if path.exists() and not force_fresh:
            payload = json.loads(path.read_text(encoding="utf-8"))
            credits, from_cache = 0, True
        elif offline():
            raise FixtureMissing(
                f"FALSIFIER_OFFLINE is set and no fixture exists for {query!r}. "
                f"Record it first by running once with the network allowed."
            )
        else:
            _check_search_budget(run_id, connection)
            try:
                payload = client().search(
                    query=query,
                    search_depth=depth,
                    max_results=max_results,
                    auto_parameters=False,
                )
            except Exception as exc:  # noqa: BLE001
                raise SearchError(f"{type(exc).__name__}: {exc}") from exc
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            credits = (
                config.TAVILY_CREDITS_BASIC
                if depth == "basic"
                else config.TAVILY_CREDITS_ADVANCED
            )
            from_cache = False

        latency_ms = int((time.monotonic() - started) * 1000)
        results = _parse(payload)

        cursor = connection.execute(
            "INSERT INTO searches (run_id, hypothesis_id, query, depth, credits, "
            "from_cache, n_results) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, hypothesis_id, query, depth, credits,
             1 if from_cache else 0, len(results)),
        )
        search_id = cursor.lastrowid

        if store_results:
            connection.executemany(
                "INSERT INTO results (search_id, url, title, snippet, published_date) "
                "VALUES (?, ?, ?, ?, ?)",
                [(search_id, r.url, r.title, r.snippet, r.published_date)
                 for r in results],
            )
        connection.commit()

        return Search(
            query=query,
            results=results,
            credits=credits,
            from_cache=from_cache,
            latency_ms=latency_ms,
            search_id=search_id,
        )
    finally:
        if owned:
            connection.close()


def credits_spent(conn: sqlite3.Connection | None = None) -> int:
    """Credits actually spent on the network, ignoring cache replays."""
    owned = conn is None
    connection = conn or db.connect()
    try:
        return connection.execute(
            "SELECT coalesce(sum(credits), 0) FROM searches WHERE from_cache = 0"
        ).fetchone()[0]
    finally:
        if owned:
            connection.close()


def fixture_count() -> int:
    """How many queries can be replayed for free."""
    if not config.FIXTURES_DIR.exists():
        return 0
    return len(list(config.FIXTURES_DIR.glob("*.json")))
