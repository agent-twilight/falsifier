"""The part that runs every day and usually says nothing.

One sentence: re-check the sources behind every live finding, hunt weekly
for developments that did not exist before, and message you only when
something actually changed.

Two jobs on two schedules, because they cost very different amounts:

- RE-VERIFY, daily, free. Ask each source "changed since I looked?" using
  the stored ETag. A 304 means definitively no, with no body transferred.
  If it has changed, fetch it and check whether the exact quoted sentence
  is still there. A finding whose quote has vanished is retracted.

- RE-SEARCH, weekly, costs credits. Look for things that did not exist
  before - a new announcement, a competitor launching. Re-checking a known
  page can never find these. Capped, because ~22 full runs a month exist.

The hard part is not the plumbing, it is the silence. A loop that messages
you daily gets muted within a week, and a muted agent is a dead one. So
the default outcome of a day's work is no message at all.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

from falsifier import config
from falsifier.memory import db
from falsifier.pipeline import freshness


@dataclass
class Change:
    """Something that happened to a finding you were relying on."""

    finding_id: int
    claim: str
    statement: str
    url: str
    kind: str  # retracted | source_gone | source_changed
    detail: str

    def describe(self) -> str:
        headline = {
            "retracted": "An objection no longer holds",
            "source_gone": "A source has disappeared",
            "source_changed": "A source changed",
        }[self.kind]
        return f"{headline}: {self.detail}"


@dataclass
class DayResult:
    """What a day's checking found. Usually nothing, by design."""

    checked: int = 0
    unchanged: int = 0
    changes: list[Change] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    credits_spent: int = 0

    @property
    def quiet(self) -> bool:
        return not self.changes

    def summary(self) -> str:
        return (
            f"checked {self.checked}, unchanged {self.unchanged}, "
            f"changes {len(self.changes)}, errors {len(self.errors)}, "
            f"credits {self.credits_spent}"
        )


# --------------------------------------------------------------------------
# Telegram
# --------------------------------------------------------------------------


def send(text: str) -> bool:
    """Message the user. Returns False rather than raising; a failed
    notification must not take the loop down with it."""
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": text,
                "disable_web_page_preview": False,
            },
            timeout=20,
        )
        return bool(response.json().get("ok"))
    except Exception:  # noqa: BLE001
        return False


def compose(changes: list[Change]) -> str:
    """What the user actually reads. Outward-facing facts only.

    Never their own plan read back at them: a deadline approaching is
    something every reminder app already does, and is not this product.
    """
    if not changes:
        return ""
    if len(changes) == 1:
        change = changes[0]
        return (
            f"{change.describe()}\n\n"
            f'Your claim: "{change.claim[:160]}"\n\n'
            f"What I had said: {change.statement[:200]}\n\n"
            f"Source: {change.url}"
        )
    lines = [f"{len(changes)} things changed since I last checked.", ""]
    for change in changes[:5]:
        lines.append(f"- {change.describe()}")
        lines.append(f"  {change.url}")
    if len(changes) > 5:
        lines.append(f"...and {len(changes) - 5} more.")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Daily re-verification, free
# --------------------------------------------------------------------------


def due_findings(conn: sqlite3.Connection, limit: int = 200) -> list[sqlite3.Row]:
    """Live findings whose next check has come around."""
    return conn.execute(
        "SELECT f.id, f.text AS statement, f.claim_id, c.text AS claim, "
        "       e.id AS evidence_id, e.quoted_line, e.url, e.etag, "
        "       e.source_tier "
        "FROM findings f "
        "JOIN claims c ON c.id = f.claim_id "
        "JOIN evidence e ON e.id = f.evidence_id "
        "WHERE f.status = 'live' AND f.evidence_id IS NOT NULL "
        "  AND (f.next_check_at IS NULL OR f.next_check_at <= ?) "
        "ORDER BY f.next_check_at IS NULL DESC, f.next_check_at "
        "LIMIT ?",
        (datetime.now(timezone.utc).isoformat(), limit),
    ).fetchall()


def _reschedule(conn: sqlite3.Connection, finding_id: int, tier: str,
                state: freshness.PageState | None = None) -> None:
    days = freshness.next_check_days(tier, state)
    when = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    conn.execute(
        "UPDATE findings SET next_check_at = ? WHERE id = ?", (when, finding_id)
    )


def _retract(conn: sqlite3.Connection, finding_id: int, reason: str) -> None:
    """Mark a finding as no longer holding, keeping its history.

    Never deleted. A retraction is the most interesting thing this agent
    produces, and the record of having been wrong is the point.
    """
    conn.execute(
        "UPDATE findings SET status = 'retracted', retracted_at = ?, "
        "retracted_reason = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), reason, finding_id),
    )


def reverify(conn: sqlite3.Connection, limit: int = 200) -> DayResult:
    """Check that every cited source still says what we said it said."""
    result = DayResult()

    for row in due_findings(conn, limit):
        result.checked += 1
        state = freshness.check(row["url"], known_etag=row["etag"])

        if state.gone:
            _retract(conn, row["id"], f"The source returned {state.status}.")
            result.changes.append(Change(
                row["id"], row["claim"], row["statement"], row["url"],
                "source_gone",
                "the page it rested on is no longer there",
            ))
            continue

        if not state.reachable and not state.unchanged:
            result.errors.append(f"{row['url']}: {state.error or state.status}")
            _reschedule(conn, row["id"], row["source_tier"])
            continue

        if state.unchanged:
            result.unchanged += 1
            _reschedule(conn, row["id"], row["source_tier"], state)
            continue

        # Changed, or no ETag to compare. The question that matters is not
        # whether the page changed but whether our sentence survived it.
        text, fetched = freshness.fetch_text(row["url"])
        if text is None:
            result.errors.append(f"{row['url']}: could not fetch")
            _reschedule(conn, row["id"], row["source_tier"])
            continue

        from falsifier.pipeline import read as read_stage

        if read_stage.quote_is_present(row["quoted_line"], text):
            result.unchanged += 1
        else:
            _retract(
                conn, row["id"],
                "The quoted line is no longer present on the page.",
            )
            result.changes.append(Change(
                row["id"], row["claim"], row["statement"], row["url"],
                "retracted",
                "the line it rested on has gone from the page",
            ))

        conn.execute(
            "UPDATE evidence SET etag = ?, last_modified = ?, "
            "last_checked_at = ?, content_hash = ? WHERE id = ?",
            (fetched.etag,
             fetched.last_modified.isoformat() if fetched.last_modified else None,
             fetched.checked_at.isoformat() if fetched.checked_at else None,
             freshness.fingerprint(text), row["evidence_id"]),
        )
        _reschedule(conn, row["id"], row["source_tier"], fetched)

    conn.commit()
    return result


# --------------------------------------------------------------------------
# Weekly hunt for things that did not exist before
# --------------------------------------------------------------------------


def claims_due_for_research(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Live claims not re-searched within the interval."""
    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(days=config.RESEARCH_INTERVAL_DAYS)
    ).isoformat()
    return conn.execute(
        "SELECT c.id, c.text, max(s.created_at) AS last_search "
        "FROM claims c LEFT JOIN runs r ON r.claim_id = c.id "
        "LEFT JOIN searches s ON s.run_id = r.id "
        "WHERE c.status = 'live' AND c.mode = 'personal' "
        "GROUP BY c.id HAVING last_search IS NULL OR last_search <= ? "
        "ORDER BY last_search",
        (cutoff,),
    ).fetchall()


def research(conn: sqlite3.Connection, max_credits: int | None = None) -> DayResult:
    """Re-run a few searches per due claim, looking only for new pages.

    Re-checking a known source can never find a development that appeared
    somewhere else. This can, and it is the only part that costs credits,
    so it is capped and weekly rather than daily.
    """
    from falsifier.clients import tavily

    ceiling = max_credits or config.RESEARCH_MAX_CREDITS_PER_WEEK
    result = DayResult()

    for claim_row in claims_due_for_research(conn):
        if result.credits_spent >= ceiling:
            break

        seen = {
            r["url"] for r in conn.execute(
                "SELECT DISTINCT res.url FROM results res "
                "JOIN searches s ON s.id = res.search_id "
                "JOIN runs r ON r.id = s.run_id WHERE r.claim_id = ?",
                (claim_row["id"],),
            )
        }
        queries = [
            q["query"] for q in conn.execute(
                "SELECT DISTINCT s.query FROM searches s "
                "JOIN runs r ON r.id = s.run_id WHERE r.claim_id = ? "
                "ORDER BY s.id DESC LIMIT ?",
                (claim_row["id"], config.RESEARCH_QUERIES_PER_CLAIM),
            )
        ]

        for query in queries:
            if result.credits_spent >= ceiling:
                break
            try:
                # force_fresh: the whole point is to bypass the cache
                found = tavily.search(
                    query, conn=conn, store_results=False, force_fresh=True
                )
            except tavily.SearchError as exc:
                result.errors.append(f"{query!r}: {exc}")
                continue

            result.credits_spent += found.credits
            for item in found.results:
                if item.url in seen:
                    continue
                seen.add(item.url)
                result.changes.append(Change(
                    0, claim_row["text"], "A new source has appeared.",
                    item.url, "source_changed",
                    f"something new turned up: {item.title[:90]}",
                ))

    conn.commit()
    return result


# --------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------


def run_once(
    conn: sqlite3.Connection | None = None,
    *,
    include_research: bool | None = None,
    notify: bool = True,
) -> DayResult:
    """One pass. Silent unless something genuinely changed."""
    owned = conn is None
    connection = conn or db.connect()
    try:
        if include_research is None:
            include_research = (
                datetime.now(timezone.utc).weekday()
                == config.RESEARCH_WEEKDAY
            )

        result = reverify(connection)
        if include_research:
            weekly = research(connection)
            result.changes.extend(weekly.changes)
            result.errors.extend(weekly.errors)
            result.credits_spent += weekly.credits_spent

        if notify and result.changes:  # silence is the default outcome
            send(compose(result.changes))
        return result
    finally:
        if owned:
            connection.close()


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    outcome = run_once()
    print(f"[{stamp}] {outcome.summary()}")
    if outcome.quiet:
        print("Nothing changed. Said nothing.")
    else:
        for change in outcome.changes:
            print(f"  ! {change.describe()}  {change.url}")
