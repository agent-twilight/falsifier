"""Step 14: break a claim into the assumptions it actually rests on.

One sentence: given "working two years first strengthens my application",
work out the handful of things that must be true for that to hold.

This matters because you cannot attack a claim directly. "Is this true?" is
unanswerable. "Does the admitted cohort actually contain people with work
experience?" is checkable. Decomposition is what turns the first question
into the second.

Runs on Super: there are few of these calls and getting them wrong poisons
everything downstream.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from falsifier import config
from falsifier.clients import nebius
from falsifier.pipeline import parsing

PROMPT = """A claim rests on a small number of load-bearing assumptions. If any one of them is false, the claim collapses. Other assumptions are incidental and do not matter.

Claim: "{claim}"

FIRST, check whether the claim is specific enough to be checked against evidence at all. A claim that names no particular programme, body, place or time period usually cannot be falsified, because the answer differs between cases. List anything genuinely missing that a researcher would have to know before they could look this up. If nothing is missing, give an empty list.

SECOND, identify the load-bearing assumptions. Each must be:
- checkable against public documentary evidence
- specific enough that evidence would settle it
- genuinely load-bearing, not a restatement of the whole claim

Give between 3 and 5. Fewer is better than padding.

Do not invent statistics, documents or dates. You have not looked anything up yet.

Return only JSON, in this shape:
{{"ambiguities": ["..."],
  "assumptions": [{{"assumption": "...", "why_load_bearing": "..."}}]}}"""


@dataclass
class Decomposition:
    """What a claim rests on, and what is too vague to check."""

    sub_claims: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)

    @property
    def too_vague(self) -> bool:
        """True when the claim cannot honestly be researched as written."""
        return bool(self.ambiguities)


def decompose(
    claim: str,
    *,
    claim_id: int | None = None,
    run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> Decomposition:
    """Return the load-bearing sub-claims, plus anything too vague to check."""
    payload = parsing.complete_json(
        config.SUPER,
        PROMPT.format(claim=claim),
        stage="decompose",
        max_tokens=2500,
        run_id=run_id,
        conn=conn,
    )
    if not isinstance(payload, dict):
        payload = {"assumptions": payload, "ambiguities": []}

    sub_claims = parsing.as_list_of_strings(
        payload.get("assumptions", []), key="assumption"
    )
    ambiguities = parsing.as_list_of_strings(payload.get("ambiguities", []))
    if not sub_claims:
        raise parsing.ParseError("decomposition produced no sub-claims")

    if claim_id is not None and conn is not None:
        conn.executemany(
            "INSERT INTO sub_claims (claim_id, text, position) VALUES (?, ?, ?)",
            [(claim_id, text, i) for i, text in enumerate(sub_claims)],
        )
        conn.commit()
    return Decomposition(sub_claims=sub_claims, ambiguities=ambiguities)
