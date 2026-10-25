"""Routes for the watch a judge can set off themselves.

Kept separate from the main app so the demo scaffolding does not clutter
the product. Imported by web.main, which passes in what it needs.

The daily watch runs on the owner's own machine against their own
database. There is none on the public demo, so telling a judge to change
a date and wait would be inviting them to wait for ever. The re-check
runs on demand instead, through exactly the same code.
"""

from __future__ import annotations

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from falsifier import watchdemo


def register(app, TEMPLATES, connect, mode, ctx):
    """Attach the routes. `ctx` builds the shared template context."""

    def notice_url(request: Request) -> str:
        return str(request.url_for("notice"))

    @app.get("/notice", response_class=HTMLResponse, name="notice")
    def notice(request: Request):
        """A mock examination notice, deliberately plain and quotable."""
        conn = connect()
        try:
            date = watchdemo.get_date(conn)
            return TEMPLATES.TemplateResponse(request, "notice.html", {
                "date": date,
                "changed": date != watchdemo.ORIGINAL_DATE,
            })
        finally:
            conn.close()

    @app.post("/notice")
    def change_notice(request: Request, date: str = Form(...)):
        conn = connect()
        try:
            watchdemo.set_date(conn, date)
        finally:
            conn.close()
        return RedirectResponse("/try-the-watch?changed=1", status_code=303)

    @app.get("/try-the-watch", response_class=HTMLResponse)
    def try_the_watch(request: Request, checked: str = "", changed: str = ""):
        conn = connect()
        try:
            finding_id = watchdemo.ensure(conn, notice_url(request), mode())
            row = conn.execute(
                "SELECT status, retracted_reason FROM findings WHERE id = ?",
                (finding_id,)).fetchone()
            return TEMPLATES.TemplateResponse(request, "trywatch.html", ctx(
                request, conn, {
                    "date": watchdemo.get_date(conn),
                    "original": watchdemo.ORIGINAL_DATE,
                    "withdrawn": row["status"] == "retracted",
                    "reason": row["retracted_reason"],
                    "session_id": watchdemo.session_for(conn, finding_id),
                    "checked": bool(checked), "changed": bool(changed),
                }))
        finally:
            conn.close()

    @app.post("/try-the-watch/check")
    def run_the_watch(request: Request):
        """Run the real re-verification now, rather than waiting for tomorrow."""
        from falsifier import monitor

        conn = connect()
        try:
            finding_id = watchdemo.ensure(conn, notice_url(request), mode())
            conn.execute(
                "UPDATE findings SET next_check_at = datetime('now', '-1 hour') "
                "WHERE id = ?", (finding_id,))
            conn.commit()
            # notify=False: a public demo has nobody to message.
            monitor.run_once(conn, include_research=False, notify=False)
        finally:
            conn.close()
        return RedirectResponse("/try-the-watch?checked=1", status_code=303)

    @app.post("/try-the-watch/reset")
    def reset_the_watch(request: Request):
        conn = connect()
        try:
            watchdemo.reset(conn, notice_url(request))
        finally:
            conn.close()
        return RedirectResponse("/try-the-watch", status_code=303)
