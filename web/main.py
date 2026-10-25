"""The interface: a conversation per plan, and a dot when the agent speaks.

One sentence: it looks like any chat app, except the agent can start a
message, and the thread it starts in lights up in the side panel.

That difference is the product. A general assistant answers when asked and
forgets. This one keeps a thread per plan, watches the sources behind it,
and adds to the thread unprompted when something outside your control
changes. The unread dot is the whole selling point rendered in one pixel.

Two modes, decided on day one rather than retrofitted:

- personal, on your own machine, reading your real threads
- demo, on the public URL, which reads only rows marked mode='demo' and
  cannot open a personal thread even if its id is guessed

A check takes a minute or two, which is too slow for a request. So it runs
on a worker thread and the page watches the funnel fill in.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from falsifier import config, report
from falsifier.memory import db, sessions
from web import markup

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.filters["md"] = lambda text: Markup(markup.render(text))
# Rendered server-side as a fallback; the page rewrites these into local
# time, because the database stores UTC.
TEMPLATES.env.filters["when"] = lambda stamp: (stamp or "")[:16]


def greeting() -> str:
    """Addressed to a person, with their name if they told us one."""
    from datetime import datetime

    hour = datetime.now().hour
    part = ("Good morning" if hour < 12
            else "Good afternoon" if hour < 18 else "Good evening")
    name = (os.getenv("USER_NAME") or "").strip().split(" ")[0]
    if demo_mode() or not name:
        return "What are you planning?"
    return f"{part}, {name}. What are you planning?"

app = FastAPI(title="The Falsifier", docs_url=None, redoc_url=None)

# A live check spends search credits, the one budget that runs out.
DEMO_RUNS_PER_DAY = 25


def demo_mode() -> bool:
    return os.getenv("FALSIFIER_DEMO", "").strip() not in ("", "0", "false")


def mode() -> str:
    return "demo" if demo_mode() else "personal"


def connect() -> sqlite3.Connection:
    return db.connect()


def _ctx(request: Request, conn, extra: dict) -> dict:
    """Every page needs the side panel."""
    return {
        "demo": demo_mode(),
        "sessions": sessions.listing(conn, mode()),
        **extra,
    }


# --------------------------------------------------------------------------
# The conversation
# --------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """An empty box, and whatever is waiting in the panel."""
    conn = connect()
    try:
        return TEMPLATES.TemplateResponse(request, "chat.html", _ctx(
            request, conn, {"session": None, "messages": [], "run": None,
                            "greeting": greeting()}))
    finally:
        conn.close()


@app.get("/s/{session_id}", response_class=HTMLResponse)
def thread(request: Request, session_id: int):
    conn = connect()
    try:
        session = sessions.get(conn, session_id, mode())
        if session is None:
            return TEMPLATES.TemplateResponse(
                request, "missing.html", _ctx(request, conn, {}),
                status_code=404)

        # Opening a thread is reading it.
        sessions.mark_read(conn, session_id)
        run = None
        if session.claim_id:
            row = conn.execute(
                "SELECT * FROM runs WHERE claim_id = ? ORDER BY id DESC LIMIT 1",
                (session.claim_id,)).fetchone()
            run = dict(row) if row else None

        return TEMPLATES.TemplateResponse(request, "chat.html", _ctx(
            request, conn, {
                "session": session,
                "messages": sessions.history(conn, session_id),
                "run": run, "greeting": greeting(),
            }))
    finally:
        conn.close()


def _findings_text(conn, claim_id: int) -> str:
    """What was established, for the conversational model to lean on."""
    rows = conn.execute("""
        SELECT f.stance, f.text, f.reason, e.quoted_line, e.url, e.source_tier
        FROM findings f LEFT JOIN evidence e ON e.id = f.evidence_id
        WHERE f.claim_id = ? AND f.status = 'live'
    """, (claim_id,)).fetchall()
    out = []
    for r in rows:
        label = {"challenges": "NO LONGER TRUE",
                 "supports": "STILL TRUE"}.get(r["stance"], "COULD NOT CHECK")
        out.append(f"[{label}] {r['text']}")
        if r["quoted_line"]:
            out.append(f'   "{r["quoted_line"]}" — {r["url"]} ({r["source_tier"]})')
        if r["reason"]:
            out.append(f"   why: {r['reason']}")
    return "\n".join(out)


def _investigate(claim_text: str, session_id: int, run_mode: str) -> None:
    """Run a check on a worker thread and report back into the thread."""
    from falsifier import artifact
    from falsifier.pipeline import run as pipeline

    conn = db.connect()
    try:
        profile = "demo" if run_mode == "demo" else "quick"
        result = pipeline.investigate(claim_text, profile=profile, mode=run_mode)

        conn.execute("UPDATE sessions SET claim_id = ? WHERE id = ?",
                     (result.claim_id, session_id))
        conn.commit()

        for v in result.report.verdicts:
            label = {
                "challenges": "This bit does not hold up",
                "supports": "This bit checks out",
            }.get(v.stance, "I could not pin this one down")
            body = f"**{label}.** {v.statement}"
            if v.evidence:
                body += (f"\n\n> {v.evidence.quote}\n\n"
                         f"[{v.evidence.url}]({v.evidence.url}) — "
                         f"{v.evidence.source_tier} source")
            elif v.reason:
                body += f"\n\n{v.reason}"
            sessions.add(conn, session_id, "agent", body,
                         kind="finding", run_id=result.run_id)

        a = result.assessment
        if a is not None and a.usable:
            body = (f"**What this turns on:** {a.hinges_on}\n\n{a.body}"
                    if a.hinges_on else a.body)
            if a.inferred:
                body += ("\n\n*Worked out rather than read, so treat as "
                         "reasoning not evidence:*\n"
                         + "\n".join(f"- {i}" for i in a.inferred))
            if a.worth_finding_out:
                body += f"\n\n**Worth finding out:** {a.worth_finding_out}"
            sessions.add(conn, session_id, "agent", body,
                         kind="assessment", run_id=result.run_id)

        if not result.report.verdicts:
            sessions.add(conn, session_id, "agent",
                         "I came up empty on this one — nothing I found "
                         "speaks to it either way. Worth saying that is not "
                         "the same as it being fine. If you can tell me more "
                         "about your situation I can have another go.",
                         kind="text", run_id=result.run_id)

        artifact.write(result)
    except Exception as exc:  # noqa: BLE001 - say so in the thread, never 500
        sessions.add(conn, session_id, "agent",
                     f"Sorry — that one stopped partway through: {exc}. "
                     "Ask me again and I will have another go.", kind="text")
    finally:
        conn.close()


def _reply(message: str, session_id: int, run_mode: str) -> None:
    """Answer a follow-up, and start a check if it genuinely needs one."""
    from falsifier.pipeline import converse

    conn = db.connect()
    try:
        session = sessions.get(conn, session_id, run_mode)
        claim, findings, assessment = "", "", ""
        if session and session.claim_id:
            row = conn.execute("SELECT text FROM claims WHERE id = ?",
                               (session.claim_id,)).fetchone()
            claim = row["text"] if row else ""
            findings = _findings_text(conn, session.claim_id)
            run = conn.execute(
                "SELECT assessment FROM runs WHERE claim_id = ? "
                "ORDER BY id DESC LIMIT 1", (session.claim_id,)).fetchone()
            assessment = (run["assessment"] or "") if run else ""

        answer = converse.respond(
            message, claim=claim, findings=findings, assessment=assessment,
            messages=sessions.history(conn, session_id), conn=conn)
        sessions.add(conn, session_id, "agent", answer.text, kind="text")

        if answer.needs_check and answer.check_claim:
            threading.Thread(
                target=_investigate,
                args=(answer.check_claim, session_id, run_mode),
                daemon=True).start()
    except Exception as exc:  # noqa: BLE001
        sessions.add(conn, session_id, "agent",
                     f"I could not answer that: {exc}", kind="text")
    finally:
        conn.close()


@app.post("/say")
def say(message: str = Form(...), session_id: str = Form("")):
    """One entry point for both a new plan and a follow-up."""
    message = " ".join(message.split())[:2000]
    if len(message) < 3:
        return RedirectResponse("/", status_code=303)

    conn = connect()
    try:
        existing = session_id.strip().isdigit() and sessions.get(
            conn, int(session_id), mode())

        if existing:
            sid = int(session_id)
            sessions.add(conn, sid, "user", message)
            threading.Thread(target=_reply, args=(message, sid, mode()),
                             daemon=True).start()
            return RedirectResponse(f"/s/{sid}", status_code=303)

        # A new plan. The first thing said is the claim to check.
        if demo_mode():
            today = conn.execute(
                "SELECT count(*) FROM runs WHERE date(started_at) = date('now')"
            ).fetchone()[0]
            if today >= DEMO_RUNS_PER_DAY:
                sid = sessions.create(conn, "Busy", mode=mode())
                sessions.add(conn, sid, "user", message)
                sessions.add(conn, sid, "agent",
                             "The public demo has used its checks for today, "
                             "so I cannot run a live one. The example threads "
                             "in the panel show real results.", kind="text")
                return RedirectResponse(f"/s/{sid}", status_code=303)

        sid = sessions.create(conn, sessions.title_from(message), mode=mode())
        sessions.add(conn, sid, "user", message)
        threading.Thread(target=_investigate, args=(message, sid, mode()),
                         daemon=True).start()
        return RedirectResponse(f"/s/{sid}", status_code=303)
    finally:
        conn.close()


@app.post("/s/{session_id}/pin")
def pin(session_id: int):
    conn = connect()
    try:
        session = sessions.get(conn, session_id, mode())
        if session:
            sessions.set_pinned(conn, session_id, not session.pinned)
        return RedirectResponse(f"/s/{session_id}", status_code=303)
    finally:
        conn.close()


@app.get("/api/thread/{session_id}")
def thread_state(session_id: int, after: int = 0):
    """Polled while a check runs: new messages, and the funnel so far."""
    conn = connect()
    try:
        session = sessions.get(conn, session_id, mode())
        if session is None:
            return JSONResponse({"error": "not found"}, status_code=404)

        new = [
            {"id": m.id, "role": m.role, "kind": m.kind, "body": m.body,
             "created_at": m.created_at}
            for m in sessions.history(conn, session_id) if m.id > after
        ]
        progress = None
        if session.claim_id:
            row = conn.execute(
                "SELECT status, stage, n_hypotheses, n_searches, n_results, "
                "n_read FROM runs WHERE claim_id = ? ORDER BY id DESC LIMIT 1",
                (session.claim_id,)).fetchone()
            if row:
                progress = dict(row)
        # A thread with no claim yet is still starting its first check.
        working = progress is None or progress.get("status") == "running"
        return JSONResponse({"messages": new, "progress": progress,
                             "working": bool(working)})
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Looking inside the work
# --------------------------------------------------------------------------


@app.get("/funnel/{claim_id}", response_class=HTMLResponse)
def funnel(request: Request, claim_id: int):
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM claims WHERE id = ? AND mode = ?",
                           (claim_id, mode())).fetchone()
        if row is None:
            return TEMPLATES.TemplateResponse(
                request, "missing.html", _ctx(request, conn, {}),
                status_code=404)
        run = conn.execute(
            "SELECT * FROM runs WHERE claim_id = ? ORDER BY id DESC LIMIT 1",
            (claim_id,)).fetchone()
        rows = lambda sql, p=(): [dict(r) for r in conn.execute(sql, p)]  # noqa: E731
        return TEMPLATES.TemplateResponse(request, "funnel.html", _ctx(
            request, conn, {
                "claim": dict(row), "run": dict(run) if run else None,
                "session_id": sessions.for_claim(conn, claim_id),
                "hypotheses": rows("""
                    SELECT h.text, count(DISTINCT s.id) AS searches,
                           count(DISTINCT e.id) AS evidence
                    FROM hypotheses h
                    JOIN sub_claims sc ON sc.id = h.sub_claim_id
                    LEFT JOIN searches s ON s.hypothesis_id = h.id
                    LEFT JOIN evidence e ON e.hypothesis_id = h.id
                    WHERE sc.claim_id = ? GROUP BY h.id
                    ORDER BY evidence DESC, h.id""", (claim_id,)),
                "searches": rows("""
                    SELECT s.query, s.credits, s.from_cache, s.n_results
                    FROM searches s JOIN runs r ON r.id = s.run_id
                    WHERE r.claim_id = ? ORDER BY s.id""", (claim_id,)),
                "tiers": rows("""
                    SELECT tier, count(*) AS calls, sum(cost_usd) AS cost,
                           avg(latency_ms) AS latency FROM calls
                    WHERE run_id IN (SELECT id FROM runs WHERE claim_id = ?)
                    GROUP BY tier""", (claim_id,)),
            }))
    finally:
        conn.close()


@app.get("/numbers", response_class=HTMLResponse)
def numbers(request: Request):
    conn = connect()
    try:
        return TEMPLATES.TemplateResponse(request, "numbers.html", _ctx(
            request, conn, {"table": report.render(conn)}))
    finally:
        conn.close()


# --------------------------------------------------------------------------
# A page a judge can change, so the watching is inspectable
# --------------------------------------------------------------------------
#
# The hard part of evaluating this product is that its selling point only
# shows itself when the world changes, which a judge cannot wait for. So
# this serves a page under our own control, with a real date on it, that
# anyone can edit. Cite it, change it, re-check it: the retraction that
# follows runs through exactly the same machinery as a real one. Nothing
# here is simulated except who moved the date.

NOTICE_DEFAULT = "14 April 2026"
_notice = {"date": NOTICE_DEFAULT}


@app.get("/notice", response_class=HTMLResponse)
def notice(request: Request):
    """A mock exam-board notice, deliberately simple and quotable."""
    return TEMPLATES.TemplateResponse(request, "notice.html", {
        "date": _notice["date"], "changed": _notice["date"] != NOTICE_DEFAULT,
    })


@app.post("/notice")
def change_notice(date: str = Form(...)):
    _notice["date"] = " ".join(date.split())[:40] or NOTICE_DEFAULT
    return RedirectResponse("/notice", status_code=303)


@app.get("/try-the-watch", response_class=HTMLResponse)
def try_the_watch(request: Request):
    """Explains how to make the agent catch a change, in three steps."""
    conn = connect()
    try:
        return TEMPLATES.TemplateResponse(request, "trywatch.html", _ctx(
            request, conn, {"date": _notice["date"],
                            "changed": _notice["date"] != NOTICE_DEFAULT}))
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"ok": True, "mode": mode()}
