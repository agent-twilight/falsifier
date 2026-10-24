"""Build the database that ships inside the public demo.

One sentence: copy a few finished checks into a fresh database, marked as
demo rows, so a visitor sees real worked examples the moment the page
loads instead of an empty list.

Two things this is careful about.

It copies only the claims you name, and marks every copied row mode='demo'.
The application already refuses to show a personal row in demo mode, but
the stronger guarantee is that personal rows are never in the file at all.

It copies the whole chain - sub-claims, hypotheses, searches, results,
evidence, findings, model calls - because the funnel is the point. A demo
that shows conclusions without the work discarded to reach them is the
thing this product exists to argue against.

Run it with:
    .venv\\Scripts\\python.exe scripts\\build_demo_db.py 3 2
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from falsifier import config  # noqa: E402
from falsifier.memory import db, routines  # noqa: E402

TARGET = config.DATA_DIR / "demo.db"


def copy_claim(src: sqlite3.Connection, dst: sqlite3.Connection, claim_id: int) -> bool:
    """Copy one claim and everything beneath it. Returns False if absent."""
    claim = src.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if claim is None:
        print(f"  claim {claim_id}: not found, skipped")
        return False

    dst.execute(
        "INSERT INTO claims (id, text, mode, status, criteria, created_at) "
        "VALUES (?, ?, 'demo', ?, ?, ?)",
        (claim["id"], claim["text"], claim["status"], claim["criteria"],
         claim["created_at"]),
    )

    for row in src.execute("SELECT * FROM runs WHERE claim_id = ?", (claim_id,)):
        dst.execute(
            "INSERT INTO runs (id, claim_id, mode, started_at, finished_at, "
            "status, stage, n_hypotheses, n_searches, n_results, n_read, "
            "n_survived, cost_usd, tavily_credits) "
            "VALUES (?, ?, 'demo', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row["id"], row["claim_id"], row["started_at"], row["finished_at"],
             row["status"], row["stage"], row["n_hypotheses"], row["n_searches"],
             row["n_results"], row["n_read"], row["n_survived"], row["cost_usd"],
             row["tavily_credits"]),
        )

    def copy_table(table: str, where: str, params: tuple) -> None:
        rows = src.execute(f"SELECT * FROM {table} WHERE {where}", params).fetchall()
        if not rows:
            return
        cols = rows[0].keys()
        placeholders = ", ".join("?" for _ in cols)
        dst.executemany(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
            [tuple(r[c] for c in cols) for r in rows],
        )

    copy_table("sub_claims", "claim_id = ?", (claim_id,))
    copy_table("hypotheses",
               "sub_claim_id IN (SELECT id FROM sub_claims WHERE claim_id = ?)",
               (claim_id,))
    copy_table("searches",
               "run_id IN (SELECT id FROM runs WHERE claim_id = ?)", (claim_id,))
    copy_table("results",
               "search_id IN (SELECT s.id FROM searches s JOIN runs r "
               "ON r.id = s.run_id WHERE r.claim_id = ?)", (claim_id,))
    copy_table("evidence",
               "hypothesis_id IN (SELECT h.id FROM hypotheses h "
               "JOIN sub_claims sc ON sc.id = h.sub_claim_id WHERE sc.claim_id = ?)",
               (claim_id,))
    copy_table("findings", "claim_id = ?", (claim_id,))
    copy_table("claim_authorities", "claim_id = ?", (claim_id,))
    copy_table("calls",
               "run_id IN (SELECT id FROM runs WHERE claim_id = ?)", (claim_id,))

    # The conversation itself. Without it the demo opens on an empty panel
    # and a visitor cannot see what a finished thread looks like.
    for row in src.execute("SELECT * FROM sessions WHERE claim_id = ?", (claim_id,)):
        dst.execute(
            "INSERT INTO sessions (id, title, mode, claim_id, pinned, unread, "
            "created_at, last_message_at) VALUES (?, ?, 'demo', ?, ?, 0, ?, ?)",
            (row["id"], row["title"], row["claim_id"], row["pinned"],
             row["created_at"], row["last_message_at"]),
        )
    copy_table("messages",
               "session_id IN (SELECT id FROM sessions WHERE claim_id = ?)",
               (claim_id,))

    findings = dst.execute(
        "SELECT count(*) FROM findings WHERE claim_id = ?", (claim_id,)
    ).fetchone()[0]
    print(f"  claim {claim_id}: {findings} findings — {claim['text'][:56]}…")
    return True


def main(claim_ids: list[int]) -> int:
    if TARGET.exists():
        TARGET.unlink()

    src = db.connect()
    dst = db.init_db(TARGET)
    routines.seed(dst)

    print(f"building {TARGET.name} from claims {claim_ids}")
    copied = sum(copy_claim(src, dst, cid) for cid in claim_ids)
    dst.commit()

    for table in ("claims", "sessions"):
        leaked = dst.execute(
            f"SELECT count(*) FROM {table} WHERE mode != 'demo'"
        ).fetchone()[0]
        if leaked:
            raise SystemExit(
                f"ABORT: {leaked} non-demo rows in {table} of the demo file"
            )

    totals = {
        t: dst.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in ("claims", "findings", "evidence", "searches", "calls",
                  "sessions", "messages")
    }
    print(f"\n{copied} claims copied. Rows: " +
          ", ".join(f"{k} {v}" for k, v in totals.items()))
    print("every claim is mode='demo' — no personal rows in the file")
    src.close()
    dst.close()
    return 0


if __name__ == "__main__":
    ids = [int(a) for a in sys.argv[1:]] or [3, 2]
    raise SystemExit(main(ids))
