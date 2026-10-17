"""The claim register: SQLite schema and connection handling.

One sentence: this is where every claim, objection, model call and search is
stored, so the agent remembers across sessions and the cost table can be
computed from real data rather than estimates.

Two design decisions worth knowing:

1. **Rule 1 is enforced by the database, not by a prompt.** An objection
   cannot exist without an evidence row, and an evidence row cannot exist
   without a non-empty quoted line and URL. CHECK constraints make a
   fabricated objection unstorable rather than merely discouraged.

2. **Every table that holds user content carries a `mode`.** Personal runs
   and public demo runs share one schema but never share rows, so the demo
   cannot leak personal claims.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from falsifier import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id          INTEGER PRIMARY KEY,
    text        TEXT NOT NULL CHECK (trim(text) <> ''),
    mode        TEXT NOT NULL DEFAULT 'personal'
                CHECK (mode IN ('personal', 'demo')),
    status      TEXT NOT NULL DEFAULT 'live'
                CHECK (status IN ('live', 'retracted', 'superseded')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY,
    claim_id        INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    mode            TEXT NOT NULL CHECK (mode IN ('personal', 'demo')),
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at     TEXT,
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'complete', 'failed',
                                      'halted_budget')),
    -- the funnel, which is also the rejection log and the video's best shot
    n_hypotheses    INTEGER NOT NULL DEFAULT 0,
    n_searches      INTEGER NOT NULL DEFAULT 0,
    n_results       INTEGER NOT NULL DEFAULT 0,
    n_read          INTEGER NOT NULL DEFAULT 0,
    n_survived      INTEGER NOT NULL DEFAULT 0,
    cost_usd        REAL NOT NULL DEFAULT 0,
    tavily_credits  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sub_claims (
    id          INTEGER PRIMARY KEY,
    claim_id    INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    text        TEXT NOT NULL CHECK (trim(text) <> ''),
    position    INTEGER NOT NULL DEFAULT 0
);

-- A way a sub-claim could be false. The opposition, invented before search.
CREATE TABLE IF NOT EXISTS hypotheses (
    id              INTEGER PRIMARY KEY,
    sub_claim_id    INTEGER NOT NULL REFERENCES sub_claims(id) ON DELETE CASCADE,
    run_id          INTEGER REFERENCES runs(id) ON DELETE SET NULL,
    text            TEXT NOT NULL CHECK (trim(text) <> ''),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS searches (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER REFERENCES runs(id) ON DELETE CASCADE,
    hypothesis_id   INTEGER REFERENCES hypotheses(id) ON DELETE SET NULL,
    query           TEXT NOT NULL,
    depth           TEXT NOT NULL DEFAULT 'basic'
                    CHECK (depth IN ('basic', 'advanced')),
    credits         INTEGER NOT NULL DEFAULT 1,
    from_cache      INTEGER NOT NULL DEFAULT 0,
    n_results       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS results (
    id              INTEGER PRIMARY KEY,
    search_id       INTEGER NOT NULL REFERENCES searches(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    title           TEXT,
    snippet         TEXT,
    published_date  TEXT,
    triaged_keep    INTEGER,
    triage_reason   TEXT,
    fetched_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Rule 1 lives here. No quoted line and no link means no row, which means
-- no objection can reference it.
CREATE TABLE IF NOT EXISTS evidence (
    id              INTEGER PRIMARY KEY,
    result_id       INTEGER REFERENCES results(id) ON DELETE SET NULL,
    hypothesis_id   INTEGER NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    quoted_line     TEXT NOT NULL CHECK (trim(quoted_line) <> ''),
    url             TEXT NOT NULL CHECK (trim(url) <> ''),
    source_tier     TEXT NOT NULL
                    CHECK (source_tier IN ('primary', 'secondary', 'weak')),
    source_date     TEXT,
    undated         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- evidence_id is NOT NULL on purpose: an objection without evidence is
-- unstorable, so rule 1 cannot be violated even by buggy code.
CREATE TABLE IF NOT EXISTS objections (
    id                  INTEGER PRIMARY KEY,
    claim_id            INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    sub_claim_id        INTEGER REFERENCES sub_claims(id) ON DELETE SET NULL,
    hypothesis_id       INTEGER REFERENCES hypotheses(id) ON DELETE SET NULL,
    evidence_id         INTEGER NOT NULL REFERENCES evidence(id),
    text                TEXT NOT NULL CHECK (trim(text) <> ''),
    confidence          REAL CHECK (confidence BETWEEN 0 AND 1),
    status              TEXT NOT NULL DEFAULT 'live'
                        CHECK (status IN ('live', 'retracted', 'superseded')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    next_check_at       TEXT,
    retracted_at        TEXT,
    retracted_reason    TEXT
);

-- Every model call, logged by the wrapper. The cost table is a query over
-- this, never an estimate.
CREATE TABLE IF NOT EXISTS calls (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER REFERENCES runs(id) ON DELETE SET NULL,
    tier            TEXT NOT NULL CHECK (tier IN ('nano', 'super', 'ultra')),
    model           TEXT NOT NULL,
    stage           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    latency_ms      INTEGER NOT NULL DEFAULT 0,
    cost_usd        REAL NOT NULL DEFAULT 0,
    ok              INTEGER NOT NULL DEFAULT 1,
    error           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Which domains have proved worth trusting.
CREATE TABLE IF NOT EXISTS sources (
    domain      TEXT PRIMARY KEY,
    tier        TEXT NOT NULL
                CHECK (tier IN ('primary', 'secondary', 'weak')),
    times_seen  INTEGER NOT NULL DEFAULT 0,
    note        TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_calls_run ON calls(run_id);
CREATE INDEX IF NOT EXISTS idx_calls_created ON calls(created_at);
CREATE INDEX IF NOT EXISTS idx_objections_claim ON objections(claim_id);
CREATE INDEX IF NOT EXISTS idx_objections_due
    ON objections(next_check_at) WHERE status = 'live';
CREATE INDEX IF NOT EXISTS idx_searches_query ON searches(query);
"""

TABLES = (
    "claims", "runs", "sub_claims", "hypotheses", "searches",
    "results", "evidence", "objections", "calls", "sources",
)


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the register. Foreign keys are off by default in SQLite."""
    db_path = Path(path) if path else config.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | None = None) -> sqlite3.Connection:
    """Create any missing tables. Safe to run repeatedly."""
    conn = connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


if __name__ == "__main__":
    conn = init_db()
    print(f"database: {config.DB_PATH}")
    print()
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    for row in rows:
        count = conn.execute(f"SELECT count(*) FROM {row['name']}").fetchone()[0]
        print(f"  {row['name']:<12} {count} rows")
    missing = set(TABLES) - {r["name"] for r in rows}
    print()
    print("missing tables:", ", ".join(sorted(missing)) if missing else "none")
