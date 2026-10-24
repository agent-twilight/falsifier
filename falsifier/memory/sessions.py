"""Conversations about plans, and the unread flag that makes this different.

One sentence: a plan gets its own thread, and the agent can add to that
thread without being asked.

That last part is the whole product. A general assistant only ever replies
to you. This one watches the world on your behalf and speaks when something
changed, so a thread you have not opened in a week can be waiting with
something you needed to know. The side panel shows a dot, exactly as a
messaging app does.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class Message:
    id: int
    role: str
    kind: str
    body: str
    created_at: str
    run_id: int | None = None

    @property
    def unprompted(self) -> bool:
        """Did the agent start this, rather than answer?"""
        return self.kind == "alert"


@dataclass
class Session:
    id: int
    title: str
    unread: int
    pinned: int
    created_at: str
    last_message_at: str
    claim_id: int | None = None

    @property
    def has_news(self) -> bool:
        return self.unread > 0


def create(
    conn: sqlite3.Connection, title: str, *, mode: str = "personal",
    claim_id: int | None = None,
) -> int:
    return conn.execute(
        "INSERT INTO sessions (title, mode, claim_id) VALUES (?, ?, ?)",
        (title[:120] or "New plan", mode, claim_id),
    ).lastrowid


def add(
    conn: sqlite3.Connection, session_id: int, role: str, body: str,
    *, kind: str = "text", run_id: int | None = None,
) -> int:
    """Append a turn. An unprompted agent message marks the thread unread."""
    message_id = conn.execute(
        "INSERT INTO messages (session_id, role, kind, body, run_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (session_id, role, kind, body, run_id),
    ).lastrowid
    conn.execute(
        "UPDATE sessions SET last_message_at = datetime('now')"
        + (", unread = unread + 1" if kind == "alert" else "")
        + " WHERE id = ?",
        (session_id,),
    )
    conn.commit()
    return message_id


def history(conn: sqlite3.Connection, session_id: int) -> list[Message]:
    return [
        Message(r["id"], r["role"], r["kind"], r["body"], r["created_at"],
                r["run_id"])
        for r in conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
    ]


def listing(conn: sqlite3.Connection, mode: str = "personal") -> list[Session]:
    """For the side panel: pinned first, then whatever spoke most recently."""
    return [
        Session(r["id"], r["title"], r["unread"], r["pinned"], r["created_at"],
                r["last_message_at"], r["claim_id"])
        for r in conn.execute(
            "SELECT * FROM sessions WHERE mode = ? "
            "ORDER BY pinned DESC, last_message_at DESC LIMIT 60",
            (mode,),
        )
    ]


def get(conn: sqlite3.Connection, session_id: int, mode: str) -> Session | None:
    row = conn.execute(
        "SELECT * FROM sessions WHERE id = ? AND mode = ?", (session_id, mode)
    ).fetchone()
    if row is None:
        return None
    return Session(row["id"], row["title"], row["unread"], row["pinned"],
                   row["created_at"], row["last_message_at"], row["claim_id"])


def mark_read(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute("UPDATE sessions SET unread = 0 WHERE id = ?", (session_id,))
    conn.commit()


def set_pinned(conn: sqlite3.Connection, session_id: int, pinned: bool) -> None:
    conn.execute("UPDATE sessions SET pinned = ? WHERE id = ?",
                 (1 if pinned else 0, session_id))
    conn.commit()


def rename(conn: sqlite3.Connection, session_id: int, title: str) -> None:
    conn.execute("UPDATE sessions SET title = ? WHERE id = ?",
                 (title[:120], session_id))
    conn.commit()


def for_claim(conn: sqlite3.Connection, claim_id: int) -> int | None:
    """The thread a claim belongs to, so the watch knows where to speak."""
    row = conn.execute(
        "SELECT id FROM sessions WHERE claim_id = ? ORDER BY id DESC LIMIT 1",
        (claim_id,),
    ).fetchone()
    return row["id"] if row else None


def title_from(claim: str) -> str:
    """A short label for the panel. First clause, trimmed at a word."""
    text = " ".join(claim.split())
    for stop in (". ", "? ", " - ", ", so ", ", and "):
        if stop in text[:90]:
            text = text.split(stop)[0]
            break
    if len(text) <= 58:
        return text
    cut = text[:58].rfind(" ")
    return text[:cut if cut > 20 else 58].rstrip(",;:") + "…"
