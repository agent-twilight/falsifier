"""The web interface: four things a stranger can click through.

One sentence: shows your claims, what was concluded and why, and the funnel
of everything that was thrown away to get there.

Two modes, decided on day one rather than retrofitted:

- personal, on your own machine, reading your real claim register
- demo, for the public URL, which reads only rows marked mode='demo' and
  can never see a personal claim even if both ever shared a database

The funnel matters more than it looks. It is the rejection log: fifty
hypotheses down to two findings, with the discarded quotes counted. Any
tool can show you its answer. Showing what it threw away is what makes the
answer worth anything.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from falsifier import config, report
from falsifier.memory import db

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="The Falsifier", docs_url=None, redoc_url=None)


def demo_mode() -> bool:
    """True on the public deployment. Set FALSIFIER_DEMO=1 there."""
    return os.getenv("FALSIFIER_DEMO", "").strip() not in ("", "0", "false")


def mode() -> str:
    return "demo" if demo_mode() else "personal"


def connect() -> sqlite3.Connection:
    return db.connect()


def _rows(conn, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


@app.get("/", response_class=HTMLResponse)
def register(request: Request):
    """Every claim, with what was concluded about it."""
    conn = connect()
    try:
        claims = _rows(conn, """
            SELECT c.id, c.text, c.status, c.created_at,
                   sum(f.stance = 'challenges' AND f.status = 'live') AS challenged,
                   sum(f.stance = 'supports' AND f.status = 'live') AS supported,
                   sum(f.stance = 'unverifiable') AS unsettled,
                   sum(f.status = 'retracted') AS retracted
            FROM claims c LEFT JOIN findings f ON f.claim_id = c.id
            WHERE c.mode = ?
            GROUP BY c.id ORDER BY c.created_at DESC
        """, (mode(),))
        return TEMPLATES.TemplateResponse(request, "register.html", {
            "claims": claims, "demo": demo_mode(),
        })
    finally:
        conn.close()


@app.get("/claim/{claim_id}", response_class=HTMLResponse)
def claim(request: Request, claim_id: int):
    """One claim: the verdicts, each with its quote, link and source tier."""
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM claims WHERE id = ? AND mode = ?", (claim_id, mode())
        ).fetchone()
        if row is None:
            return TEMPLATES.TemplateResponse(
                request, "missing.html", {"demo": demo_mode()}, status_code=404
            )

        findings = _rows(conn, """
            SELECT f.*, s.text AS sub_claim, e.quoted_line, e.url,
                   e.source_tier, e.last_modified, e.source_date
            FROM findings f
            LEFT JOIN sub_claims s ON s.id = f.sub_claim_id
            LEFT JOIN evidence e ON e.id = f.evidence_id
            WHERE f.claim_id = ?
            ORDER BY CASE f.stance WHEN 'challenges' THEN 0
                                   WHEN 'supports' THEN 1 ELSE 2 END,
                     f.status
        """, (claim_id,))
        authorities = _rows(
            conn, "SELECT * FROM claim_authorities WHERE claim_id = ?", (claim_id,)
        )
        run = conn.execute(
            "SELECT * FROM runs WHERE claim_id = ? ORDER BY id DESC LIMIT 1",
            (claim_id,),
        ).fetchone()
        return TEMPLATES.TemplateResponse(request, "claim.html", {
            "claim": dict(row), "findings": findings,
            "authorities": authorities, "run": dict(run) if run else None,
            "demo": demo_mode(),
        })
    finally:
        conn.close()


@app.get("/funnel/{claim_id}", response_class=HTMLResponse)
def funnel(request: Request, claim_id: int):
    """What was thrown away, and why. The rejection log."""
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM claims WHERE id = ? AND mode = ?", (claim_id, mode())
        ).fetchone()
        if row is None:
            return TEMPLATES.TemplateResponse(
                request, "missing.html", {"demo": demo_mode()}, status_code=404
            )

        run = conn.execute(
            "SELECT * FROM runs WHERE claim_id = ? ORDER BY id DESC LIMIT 1",
            (claim_id,),
        ).fetchone()
        hypotheses = _rows(conn, """
            SELECT h.text, count(DISTINCT s.id) AS searches,
                   count(DISTINCT e.id) AS evidence
            FROM hypotheses h
            JOIN sub_claims sc ON sc.id = h.sub_claim_id
            LEFT JOIN searches s ON s.hypothesis_id = h.id
            LEFT JOIN evidence e ON e.hypothesis_id = h.id
            WHERE sc.claim_id = ? GROUP BY h.id ORDER BY evidence DESC, h.id
        """, (claim_id,))
        searches = _rows(conn, """
            SELECT s.query, s.credits, s.from_cache, s.n_results
            FROM searches s JOIN runs r ON r.id = s.run_id
            WHERE r.claim_id = ? ORDER BY s.id
        """, (claim_id,))
        tiers = _rows(conn, """
            SELECT tier, count(*) AS calls, sum(cost_usd) AS cost,
                   avg(latency_ms) AS latency
            FROM calls WHERE run_id IN (SELECT id FROM runs WHERE claim_id = ?)
            GROUP BY tier
        """, (claim_id,))
        return TEMPLATES.TemplateResponse(request, "funnel.html", {
            "claim": dict(row), "run": dict(run) if run else None,
            "hypotheses": hypotheses, "searches": searches, "tiers": tiers,
            "demo": demo_mode(),
        })
    finally:
        conn.close()


@app.get("/numbers", response_class=HTMLResponse)
def numbers(request: Request):
    """Cost and tiering, computed from logged calls rather than estimated."""
    conn = connect()
    try:
        return TEMPLATES.TemplateResponse(request, "numbers.html", {
            "table": report.render(conn), "demo": demo_mode(),
            "budget": config.TOTAL_BUDGET_USD,
        })
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"ok": True, "mode": mode()}
