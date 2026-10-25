"""The claim register: SQLite schema and connection handling.

One sentence: this is where every claim, objection, model call and search is
stored, so the agent remembers across sessions and the cost table can be
computed from real data rather than estimates.

Two design decisions worth knowing:

1. **Rule 1 is enforced by the database, not by a prompt.** A finding that
   challenges or supports a claim cannot exist without an evidence row, and
   an evidence row cannot exist without a non-empty quoted line and URL. A
   finding that claims something is unverifiable must instead carry a
   written reason. CHECK constraints make an unsupported verdict unstorable
   rather than merely discouraged.

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
    -- What a counter-example must satisfy, one per line. Set by the user,
    -- because only they can say what would actually change their mind.
    criteria    TEXT,
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
    -- What it is doing right now, for the live progress view.
    stage           TEXT,
    -- the funnel, which is also the rejection log and the video's best shot
    n_hypotheses    INTEGER NOT NULL DEFAULT 0,
    n_searches      INTEGER NOT NULL DEFAULT 0,
    n_results       INTEGER NOT NULL DEFAULT 0,
    n_read          INTEGER NOT NULL DEFAULT 0,
    n_survived      INTEGER NOT NULL DEFAULT 0,
    cost_usd        REAL NOT NULL DEFAULT 0,
    tavily_credits  INTEGER NOT NULL DEFAULT 0,
    -- Reasoning past the citations, kept separate from findings so the
    -- two can never be confused. See pipeline/assess.py.
    hinges_on       TEXT,
    assessment      TEXT,
    inferred        TEXT,
    worth_finding   TEXT
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
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    -- Freshness. The agent cannot know a fact is current; it can know when
    -- the page last changed, and whether it has changed since we looked.
    last_modified   TEXT,   -- what the server reports, not what we assume
    etag            TEXT,   -- lets a re-check cost one 304 and no body
    content_hash    TEXT,   -- detects change the ETag missed
    last_checked_at TEXT,
    quote_still_present INTEGER NOT NULL DEFAULT 1
);

-- Findings, of all three kinds. Named findings rather than objections
-- because agreeing with the user is a legitimate result: see CLAUDE.md.
--
-- Rule 1 survives the reframing, via the table CHECK below:
--   challenges / supports  -> MUST carry evidence (a quoted line and a link)
--   unverifiable           -> MUST carry a reason, and has no evidence
-- So a verdict either rests on a real quote, or explains why none exists.
-- There is no third option where it merely asserts something.
CREATE TABLE IF NOT EXISTS findings (
    id                  INTEGER PRIMARY KEY,
    claim_id            INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    sub_claim_id        INTEGER REFERENCES sub_claims(id) ON DELETE SET NULL,
    hypothesis_id       INTEGER REFERENCES hypotheses(id) ON DELETE SET NULL,
    evidence_id         INTEGER REFERENCES evidence(id),
    stance              TEXT NOT NULL
                        CHECK (stance IN ('challenges', 'supports',
                                          'unverifiable')),
    text                TEXT NOT NULL CHECK (trim(text) <> ''),
    reason              TEXT,
    confidence          REAL CHECK (confidence BETWEEN 0 AND 1),
    status              TEXT NOT NULL DEFAULT 'live'
                        CHECK (status IN ('live', 'retracted', 'superseded')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    next_check_at       TEXT,
    retracted_at        TEXT,
    retracted_reason    TEXT,

    CHECK (
        (stance IN ('challenges', 'supports') AND evidence_id IS NOT NULL)
        OR
        (stance = 'unverifiable' AND evidence_id IS NULL
         AND reason IS NOT NULL AND trim(reason) <> '')
    )
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

-- A conversation about one plan. Separate sessions for separate plans,
-- because a plan is a long-lived thing that gets revisited, not a query.
--
-- `unread` is what makes this product different from a chat app: the agent
-- can speak without being spoken to, and the session it spoke in gets a
-- dot in the side panel. A general assistant only ever replies.
CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY,
    title           TEXT NOT NULL DEFAULT 'New plan',
    mode            TEXT NOT NULL DEFAULT 'personal'
                    CHECK (mode IN ('personal', 'demo')),
    claim_id        INTEGER REFERENCES claims(id) ON DELETE SET NULL,
    pinned          INTEGER NOT NULL DEFAULT 0,
    unread          INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_message_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Every turn, from either side. `kind` separates what the agent said from
-- what it can prove: a 'finding' carries a citation, an 'assessment' is
-- labelled reasoning, an 'alert' arrived unprompted.
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'agent')),
    kind        TEXT NOT NULL DEFAULT 'text'
                CHECK (kind IN ('text', 'finding', 'assessment', 'alert',
                                'status')),
    body        TEXT NOT NULL,
    run_id      INTEGER REFERENCES runs(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages(session_id, id);
CREATE INDEX IF NOT EXISTS idx_sessions_recent
    ON sessions(mode, last_message_at DESC);

-- Falsification routines: how to attack a *class* of claim. Three are
-- built in; the rest are written by the agent when it meets a domain it
-- has no routine for, and reused from then on. Data, not code, so a new
-- domain costs a row rather than a deploy.
CREATE TABLE IF NOT EXISTS routines (
    name                TEXT PRIMARY KEY,
    description         TEXT NOT NULL,
    applies_when        TEXT NOT NULL,
    angles              TEXT NOT NULL,   -- JSON [[name, description], ...]
    primary_sources     TEXT NOT NULL,
    weak_sources        TEXT NOT NULL DEFAULT '',
    decompose_guidance  TEXT NOT NULL DEFAULT '',
    query_guidance      TEXT NOT NULL,
    generated           INTEGER NOT NULL DEFAULT 0,
    times_used          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Who decides, per claim. Grading uses it, and the monitoring loop
-- re-checks these pages rather than searching fresh every week.
CREATE TABLE IF NOT EXISTS claim_authorities (
    claim_id    INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    domain      TEXT,
    why         TEXT,
    reachable   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (claim_id, name)
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
CREATE INDEX IF NOT EXISTS idx_findings_claim ON findings(claim_id);
CREATE INDEX IF NOT EXISTS idx_findings_due
    ON findings(next_check_at) WHERE status = 'live';
CREATE INDEX IF NOT EXISTS idx_searches_query ON searches(query);
"""

TABLES = (
    "claims", "runs", "sub_claims", "hypotheses", "searches",
    "results", "evidence", "findings", "calls", "sources",
    "claim_authorities", "routines", "sessions", "messages",
)


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the register. Foreign keys are off by default in SQLite."""
    db_path = Path(path) if path else config.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Stages run in parallel, so several connections write at once. Without
    # a busy timeout they fail immediately with "database is locked"; with
    # it they wait their turn. WAL lets readers carry on meanwhile.
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass  # a read-only image, which is fine
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
