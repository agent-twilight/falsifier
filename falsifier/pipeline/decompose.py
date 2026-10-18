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

from falsifier import config
from falsifier.clients import nebius
from falsifier.pipeline import parsing

PROMPT = """A claim rests on a small number of load-bearing assumptions. If \
any one of them is false, the claim collapses. Other assumptions are \
incidental and do not matter.

Claim: "{claim}"

Identify the load-bearing assumptions. Each one must be:
- something that could be checked against public documentary evidence
- specific enough that evidence would settle it
- genuinely load-bearing, not a restatement of the whole claim

Give between 3 and 5. Fewer is better than padding.

Return only JSON, in this shape:
[{{"assumption": "...", "why_load_bearing": "..."}}]"""


def decompose(
    claim: str,
    *,
    claim_id: int | None = None,
    run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[str]:
    """Return the load-bearing sub-claims, storing them if given a claim_id."""
    result = nebius.complete(
        config.SUPER,
        PROMPT.format(claim=claim),
        stage="decompose",
        max_tokens=2000,
        run_id=run_id,
        conn=conn,
    )
    sub_claims = parsing.as_list_of_strings(
        parsing.extract_json(result.text), key="assumption"
    )
    if not sub_claims:
        raise parsing.ParseError("decomposition produced no sub-claims")

    if claim_id is not None and conn is not None:
        conn.executemany(
            "INSERT INTO sub_claims (claim_id, text, position) VALUES (?, ?, ?)",
            [(claim_id, text, i) for i, text in enumerate(sub_claims)],
        )
        conn.commit()
    return sub_claims
