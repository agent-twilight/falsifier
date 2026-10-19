"""Who actually decides this, and where do they publish?

One sentence: before searching, work out which body is authoritative for
this claim and find its real domain, so evidence can be graded by who said
it rather than by how the URL happens to end.

Why this exists. Source grading used to be a domain-suffix rule: .edu and
.gov are primary, anything with "blog" in it is weak. That gets JEE exactly
wrong - jeemain.nta.nic.in is *the* authority on the JEE exam date and does
not end in .gov, so it was graded the same as a news site, while any .edu
page outranked it. The grader knew nothing about who decides anything.

It also matters for the monitoring loop, which needs a stable set of pages
to re-check. Searching fresh every week costs credits and can return
different pages each time; watching the exam board's own notifications page
costs nothing and is the page that would actually change.

Users will not name their sources. Someone says "I'm preparing for JEE in
April", and working out that NTA is authoritative, coaching blogs are
secondary and forums are noise is the agent's job, not theirs.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from urllib.parse import urlparse

from falsifier import config
from falsifier.clients import nebius
from falsifier.pipeline import freshness, parsing

PROMPT = """Who is authoritative on this claim, and where do they publish?

Claim: "{claim}"

Name the bodies whose own published statements would settle this. Think \
about who actually has the power to decide or change the thing in \
question: the examining board, the issuing authority, the regulator, the \
company that makes the product, the department that sets the rule.

For each, give the domain you believe they publish on. Give the \
organisation's real primary domain, not a guess at a full page URL. If you \
are not confident of the domain, say null rather than inventing one.

Also name source types that are SECONDARY for this claim (reputable but \
not deciding, such as national news or established reference sites) and \
NOISE (forums, coaching blogs, content farms, aggregators).

Return only JSON:
{{"authorities": [{{"name": "...", "domain": "example.ac.in or null",
                    "why": "what makes them the decider"}}],
  "secondary_types": ["..."],
  "noise_types": ["..."]}}"""


@dataclass(frozen=True)
class Authority:
    """A body whose own word settles the matter."""

    name: str
    domain: str | None
    why: str
    reachable: bool = False

    @property
    def usable(self) -> bool:
        return bool(self.domain) and self.reachable


def _clean_domain(value) -> str | None:
    """Normalise whatever the model returned into a bare hostname."""
    if not value or str(value).strip().lower() in ("null", "none", "unknown", ""):
        return None
    text = str(value).strip().lower()
    if "//" in text:
        text = urlparse(text).hostname or text
    text = text.split("/")[0].strip()
    return text[4:] if text.startswith("www.") else text or None


def identify(
    claim: str,
    *,
    verify: bool = True,
    run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[Authority]:
    """Work out who decides this, and check the domains actually exist.

    Verification matters: a model asked for a domain will produce a
    plausible-looking one whether or not it exists. An unreachable domain
    is kept but marked unusable, never silently trusted.
    """
    payload = parsing.complete_json(
        config.SUPER,
        PROMPT.format(claim=claim),
        stage="authority",
        max_tokens=2000,
        run_id=run_id,
        conn=conn,
    )
    if not isinstance(payload, dict):
        return []

    found: list[Authority] = []
    for item in payload.get("authorities", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        domain = _clean_domain(item.get("domain"))
        reachable = False
        if domain and verify:
            state = freshness.check(f"https://{domain}")
            reachable = state.status in (200, 301, 302, 304, 403)
        found.append(
            Authority(
                name=name,
                domain=domain,
                why=str(item.get("why", "")).strip(),
                reachable=reachable,
            )
        )
    return found


def store(
    conn: sqlite3.Connection, claim_id: int, authorities: list[Authority]
) -> None:
    """Record the watchlist for this claim, for grading and for monitoring."""
    conn.executemany(
        "INSERT OR REPLACE INTO claim_authorities "
        "(claim_id, name, domain, why, reachable) VALUES (?, ?, ?, ?, ?)",
        [(claim_id, a.name, a.domain, a.why, 1 if a.reachable else 0)
         for a in authorities],
    )
    conn.commit()


def load(conn: sqlite3.Connection, claim_id: int) -> list[Authority]:
    rows = conn.execute(
        "SELECT name, domain, why, reachable FROM claim_authorities "
        "WHERE claim_id = ?",
        (claim_id,),
    ).fetchall()
    return [
        Authority(r["name"], r["domain"], r["why"], bool(r["reachable"]))
        for r in rows
    ]


def domains(authorities: list[Authority]) -> set[str]:
    """Just the usable hostnames, for grading and for the watchlist."""
    return {a.domain for a in authorities if a.usable}
