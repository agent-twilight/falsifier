"""A watch a judge can set off themselves.

One sentence: a notice page anyone can edit, a real finding that cites it,
and a button that runs the real re-check on demand.

Why this exists. The useful part of this product only shows itself when
the world changes, which nobody can wait around for. Worse, on the public
demo there is no daily watch running at all — that lives on the owner's
machine, against their own database. So the first version of this page
told a judge to change a date and then wait for something that could
never happen there.

Nothing here is simulated except who moves the date. The citation, the
word-for-word check that the quoted line is still on the page, the
withdrawal with its reason and timestamp, and the unprompted message in
the thread are the same code paths that run against Stanford.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from falsifier.memory import sessions

ORIGINAL_DATE = "14 April 2026"
CLAIM_TEXT = "My exam is on 14 April 2026, so I have a little over five months."
QUOTE_PREFIX = "will be conducted on"


def get_date(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'notice_date'"
    ).fetchone()
    return row["value"] if row else ORIGINAL_DATE


def set_date(conn: sqlite3.Connection, date: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('notice_date', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (" ".join(date.split())[:40] or ORIGINAL_DATE,),
    )
    conn.commit()


def quote_for(date: str) -> str:
    """The sentence the finding cites, as it appears on the notice."""
    return (f"Candidates are hereby informed that the written examination "
            f"for the 2026 cycle will be conducted on {date} at all "
            f"designated centres.")


def existing(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """Any finding already watching the notice page, whatever its URL.

    Matched on the path rather than the whole URL. Behind a TLS proxy the
    app can build its own address as http:// one request and https:// the
    next, and an exact match treated those as different pages - so every
    change seeded a fresh claim and a fresh conversation, with a
    fabricated opening message, while the real one was left alone.
    """
    return conn.execute(
        "SELECT f.id, e.id AS evidence_id, e.url FROM findings f "
        "JOIN evidence e ON e.id = f.evidence_id "
        "WHERE e.url LIKE '%/notice' OR e.url LIKE '%/notice/' "
        "ORDER BY f.id DESC LIMIT 1"
    ).fetchone()


def ensure(conn: sqlite3.Connection, notice_url: str, mode: str = "demo") -> int:
    """Make sure the demo thread and its finding exist. Returns the finding id.

    Seeded lazily from a real request, so the URL matches whatever host
    this is actually running on.
    """
    row = existing(conn)
    if row:
        # Keep the stored address current without creating a second
        # conversation for what is the same page.
        if row["url"] != notice_url:
            conn.execute("UPDATE evidence SET url = ? WHERE id = ?",
                         (notice_url, row["evidence_id"]))
            conn.commit()
        return row["id"]

    # Always seed against the original date. The claim says April, so a
    # finding built from a date someone has since changed would contradict
    # itself in its own sentence - which is exactly what happened.
    set_date(conn, ORIGINAL_DATE)
    date = ORIGINAL_DATE
    claim_id = conn.execute(
        "INSERT INTO claims (text, mode) VALUES (?, ?)", (CLAIM_TEXT, mode)
    ).lastrowid
    sub_id = conn.execute(
        "INSERT INTO sub_claims (claim_id, text) VALUES (?, ?)",
        (claim_id, "The examination board has the date as 14 April 2026."),
    ).lastrowid
    hyp_id = conn.execute(
        "INSERT INTO hypotheses (sub_claim_id, text) VALUES (?, ?)",
        (sub_id, "The board has moved the date since it was last checked."),
    ).lastrowid
    evidence_id = conn.execute(
        "INSERT INTO evidence (hypothesis_id, quoted_line, url, source_tier, "
        "last_checked_at) VALUES (?, ?, ?, 'primary', ?)",
        (hyp_id, quote_for(date), notice_url,
         datetime.now(timezone.utc).isoformat()),
    ).lastrowid
    finding_id = conn.execute(
        "INSERT INTO findings (claim_id, sub_claim_id, evidence_id, stance, "
        "text, confidence) VALUES (?, ?, ?, 'supports', ?, 0.95)",
        (claim_id, sub_id, evidence_id,
         f"The board's own notice gives the date as {date}, so your plan "
         f"has the right date in it."),
    ).lastrowid

    session_id = sessions.create(conn, "My exam is on 14 April",
                                 mode=mode, claim_id=claim_id)
    # Pinned so it is the first thing in the panel, since it is the one a
    # visitor is invited to interfere with.
    sessions.set_pinned(conn, session_id, True)
    sessions.add(conn, session_id, "user", CLAIM_TEXT)
    sessions.add(
        conn, session_id, "agent",
        f"**This bit checks out.** The board's own notice gives the date as "
        f"{date}, so your plan has the right date in it.\n\n"
        f"> {quote_for(date)}\n\n"
        f"[{notice_url}]({notice_url}) — primary source\n\n"
        f"I will keep an eye on that page. If the date moves, you will hear "
        f"from me without having to ask.",
        kind="finding")
    conn.commit()
    return finding_id


def session_for(conn: sqlite3.Connection, finding_id: int) -> int | None:
    row = conn.execute(
        "SELECT s.id FROM sessions s JOIN findings f ON f.claim_id = s.claim_id "
        "WHERE f.id = ?", (finding_id,)
    ).fetchone()
    return row["id"] if row else None


def all_watching(conn: sqlite3.Connection) -> list[int]:
    """Every finding citing the notice page, including any the user made.

    The watch re-verifies all of them, so a claim the user raised
    themselves is updated too rather than only the seeded example.
    """
    return [
        r["id"] for r in conn.execute(
            "SELECT f.id FROM findings f JOIN evidence e ON e.id = f.evidence_id "
            "WHERE e.url LIKE '%/notice' OR e.url LIKE '%/notice/'"
        )
    ]


def reset(conn: sqlite3.Connection, notice_url: str) -> None:
    """Put the date and the finding back, so the next visitor starts clean."""
    set_date(conn, ORIGINAL_DATE)
    finding_id = ensure(conn, notice_url)
    conn.execute(
        "UPDATE findings SET status = 'live', retracted_at = NULL, "
        "retracted_reason = NULL WHERE id = ?", (finding_id,))
    conn.execute(
        "UPDATE evidence SET quoted_line = ?, etag = NULL "
        "WHERE id = (SELECT evidence_id FROM findings WHERE id = ?)",
        (quote_for(ORIGINAL_DATE), finding_id))
    session_id = session_for(conn, finding_id)
    if session_id:
        conn.execute(
            "DELETE FROM messages WHERE session_id = ? AND kind = 'alert'",
            (session_id,))
        conn.execute("UPDATE sessions SET unread = 0 WHERE id = ?",
                     (session_id,))
    conn.commit()
