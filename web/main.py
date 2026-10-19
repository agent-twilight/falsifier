"""The window into the work.

One sentence: Telegram is where this product lives day to day; this page is
where someone can look inside and see what was actually done.

A phone notification gives you a conclusion. It cannot show you the forty
searches behind it, the thirty results thrown away, or the one line on one
official page that the answer rests on. That is what this is for, and it is
also the hackathon's demo URL.

Two modes, decided on day one rather than retrofitted:

- personal, on the user's own machine, reading their real register
- demo, on the public URL, which reads only rows marked mode='demo' and
  cannot open a personal claim even if its id is guessed

A live check takes one to three minutes, which is too slow for a normal
request. So it runs in the background and the page watches the funnel fill
in. The wait becomes the demonstration.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from falsifier import config, report
from falsifier.memory import db

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app = FastAPI(title="The Falsifier", docs_url=None, redoc_url=None)

# A live check costs search credits. The public demo caps how many strangers
# can trigger per day, because that budget is the one that runs out.
DEMO_RUNS_PER_DAY = 25


def demo_mode() -> bool:
    return os.getenv("FALSIFIER_DEMO", "").strip() not in ("", "0", "false")


def mode() -> str:
    return "demo" if demo_mode() else "personal"


def connect() -> sqlite3.Connection:
    return db.connect()


def _rows(conn, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _ctx(extra: dict) -> dict:
    return {"demo": demo_mode(), **extra}


# --------------------------------------------------------------------------
# Looking at what has been checked
# --------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Enter a claim, and see the ones already checked with their verdicts."""
    conn = connect()
    try:
        claims = _rows(conn, """
            SELECT c.id, c.text, c.created_at,
                   (SELECT count(*) FROM findings f WHERE f.claim_id = c.id
                      AND f.stance = 'challenges' AND f.status = 'live') AS stale,
                   (SELECT count(*) FROM findings f WHERE f.claim_id = c.id
                      AND f.stance = 'supports' AND f.status = 'live') AS holds,
                   (SELECT count(*) FROM findings f WHERE f.claim_id = c.id
                      AND f.stance = 'unverifiable') AS unknown,
                   (SELECT count(*) FROM findings f WHERE f.claim_id = c.id
                      AND f.status = 'retracted') AS retracted,
                   (SELECT r.id FROM runs r WHERE r.claim_id = c.id
                      ORDER BY r.id DESC LIMIT 1) AS run_id
            FROM claims c WHERE c.mode = ?
            GROUP BY c.id ORDER BY c.created_at DESC
        """, (mode(),))

        headline = _rows(conn, """
            SELECT f.text, f.confidence, f.claim_id, c.text AS claim,
                   e.quoted_line, e.url, e.source_tier
            FROM findings f
            JOIN claims c ON c.id = f.claim_id
            JOIN evidence e ON e.id = f.evidence_id
            WHERE c.mode = ? AND f.status = 'live'
            ORDER BY CASE f.stance WHEN 'challenges' THEN 0 ELSE 1 END,
                     f.confidence DESC LIMIT 1
        """, (mode(),))

        return TEMPLATES.TemplateResponse(request, "home.html", _ctx({
            "claims": claims, "headline": headline[0] if headline else None,
        }))
    finally:
        conn.close()


@app.get("/claim/{claim_id}", response_class=HTMLResponse)
def claim(request: Request, claim_id: int):
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM claims WHERE id = ? AND mode = ?", (claim_id, mode())
        ).fetchone()
        if row is None:
            return TEMPLATES.TemplateResponse(
                request, "missing.html", _ctx({}), status_code=404)

        findings = _rows(conn, """
            SELECT f.*, s.text AS sub_claim, e.quoted_line, e.url,
                   e.source_tier, e.last_modified, e.source_date
            FROM findings f
            LEFT JOIN sub_claims s ON s.id = f.sub_claim_id
            LEFT JOIN evidence e ON e.id = f.evidence_id
            WHERE f.claim_id = ?
            ORDER BY CASE f.stance WHEN 'challenges' THEN 0
                                   WHEN 'supports' THEN 1 ELSE 2 END, f.status
        """, (claim_id,))
        run = conn.execute(
            "SELECT * FROM runs WHERE claim_id = ? ORDER BY id DESC LIMIT 1",
            (claim_id,)).fetchone()
        return TEMPLATES.TemplateResponse(request, "claim.html", _ctx({
            "claim": dict(row), "findings": findings,
            "authorities": _rows(
                conn, "SELECT * FROM claim_authorities WHERE claim_id = ?",
                (claim_id,)),
            "run": dict(run) if run else None,
        }))
    finally:
        conn.close()


@app.get("/funnel/{claim_id}", response_class=HTMLResponse)
def funnel(request: Request, claim_id: int):
    """Everything that was discarded on the way to the answer."""
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM claims WHERE id = ? AND mode = ?", (claim_id, mode())
        ).fetchone()
        if row is None:
            return TEMPLATES.TemplateResponse(
                request, "missing.html", _ctx({}), status_code=404)

        run = conn.execute(
            "SELECT * FROM runs WHERE claim_id = ? ORDER BY id DESC LIMIT 1",
            (claim_id,)).fetchone()
        return TEMPLATES.TemplateResponse(request, "funnel.html", _ctx({
            "claim": dict(row), "run": dict(run) if run else None,
            "hypotheses": _rows(conn, """
                SELECT h.text, count(DISTINCT s.id) AS searches,
                       count(DISTINCT e.id) AS evidence
                FROM hypotheses h JOIN sub_claims sc ON sc.id = h.sub_claim_id
                LEFT JOIN searches s ON s.hypothesis_id = h.id
                LEFT JOIN evidence e ON e.hypothesis_id = h.id
                WHERE sc.claim_id = ? GROUP BY h.id
                ORDER BY evidence DESC, h.id
            """, (claim_id,)),
            "searches": _rows(conn, """
                SELECT s.query, s.credits, s.from_cache, s.n_results
                FROM searches s JOIN runs r ON r.id = s.run_id
                WHERE r.claim_id = ? ORDER BY s.id
            """, (claim_id,)),
            "tiers": _rows(conn, """
                SELECT tier, count(*) AS calls, sum(cost_usd) AS cost,
                       avg(latency_ms) AS latency
                FROM calls
                WHERE run_id IN (SELECT id FROM runs WHERE claim_id = ?)
                GROUP BY tier
            """, (claim_id,)),
        }))
    finally:
        conn.close()


@app.get("/numbers", response_class=HTMLResponse)
def numbers(request: Request):
    conn = connect()
    try:
        return TEMPLATES.TemplateResponse(request, "numbers.html", _ctx({
            "table": report.render(conn), "budget": config.TOTAL_BUDGET_USD,
        }))
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Checking something new
# --------------------------------------------------------------------------


def _runs_today(conn) -> int:
    return conn.execute(
        "SELECT count(*) FROM runs WHERE date(started_at) = date('now')"
    ).fetchone()[0]


def _work(claim_text: str, run_mode: str) -> None:
    """Do the check on a worker thread, with its own connection."""
    from falsifier.pipeline import run as pipeline

    try:
        # A stranger will not wait three minutes. The personal instance
        # digs deeper because its user has a reason to care.
        profile = "demo" if run_mode == "demo" else "quick"
        pipeline.investigate(claim_text, profile=profile, mode=run_mode)
    except Exception as exc:  # noqa: BLE001 - record it, never crash the server
        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT r.id FROM runs r JOIN claims c ON c.id = r.claim_id "
                "WHERE c.text = ? ORDER BY r.id DESC LIMIT 1", (claim_text,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE runs SET status = 'failed', stage = ? WHERE id = ?",
                    (f"stopped: {exc}"[:200], row["id"]))
                conn.commit()
        finally:
            conn.close()


@app.post("/check")
def check(claim: str = Form(...)):
    """Start a check and send the visitor to the live view."""
    claim = " ".join(claim.split())[:500]
    if len(claim) < 15:
        return RedirectResponse("/?error=short", status_code=303)

    conn = connect()
    try:
        if demo_mode() and _runs_today(conn) >= DEMO_RUNS_PER_DAY:
            return RedirectResponse("/?error=busy", status_code=303)
    finally:
        conn.close()

    threading.Thread(target=_work, args=(claim, mode()), daemon=True).start()
    return RedirectResponse(f"/watch?claim={claim[:200]}", status_code=303)


@app.get("/watch", response_class=HTMLResponse)
def watch(request: Request, claim: str = ""):
    """The page that shows the funnel filling in while it works."""
    return TEMPLATES.TemplateResponse(request, "watch.html", _ctx({
        "claim": claim}))


@app.get("/api/progress")
def progress(claim: str = ""):
    """Funnel counts so far, polled by the watch page."""
    conn = connect()
    try:
        row = conn.execute("""
            SELECT r.*, c.id AS cid FROM runs r JOIN claims c ON c.id = r.claim_id
            WHERE c.text = ? AND c.mode = ? ORDER BY r.id DESC LIMIT 1
        """, (claim, mode())).fetchone()
        if row is None:
            return JSONResponse({"state": "starting"})
        return JSONResponse({
            "state": row["status"],
            "stage": row["stage"] or "thinking about what this rests on",
            "claim_id": row["cid"],
            "hypotheses": row["n_hypotheses"], "searches": row["n_searches"],
            "results": row["n_results"], "read": row["n_read"],
            "survived": row["n_survived"],
        })
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"ok": True, "mode": mode()}
