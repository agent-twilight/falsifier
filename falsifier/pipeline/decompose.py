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
from falsifier.memory import routines
from falsifier.pipeline import parsing

EXISTENCE_PROMPT = """This claim says something does not exist. You cannot prove that by reasoning, only by looking in the places where a counter-example would live and failing to find one.

Claim: "{claim}"
{criteria_block}
List the distinct CATEGORIES or DOMAINS where a counter-example would most plausibly be found. Each one becomes a separate hunt.

Think about: who else has this problem, what adjacent industries solve something similar, which incumbents could have shipped it as a feature, what the capability might be called in a field that is not the claimant's, and where early or failed attempts would be recorded.

Each category must be:
- a real place to go looking, not a restatement of the claim
- specific enough to search, for example "immigration and visa status tracking tools" rather than "other software"
- different from the others

Give between 3 and 5.

Also list anything about the claim that is genuinely too vague to search. If criteria were supplied above, treat those terms as already settled and do NOT ask for them again.

Return only JSON:
{{"ambiguities": ["..."],
  "assumptions": [{{"assumption": "No tool in <category> does this",
                    "why_load_bearing": "..."}}]}}"""


PROMPT = """A claim rests on a small number of load-bearing assumptions. If any one of them is false, the claim collapses. Other assumptions are incidental and do not matter.

Claim: "{claim}"
{criteria_block}
FIRST, check whether the claim is specific enough to be checked against evidence at all. A claim that names no particular programme, body, place or time period usually cannot be falsified, because the answer differs between cases. List anything genuinely missing that a researcher would have to know before they could look this up. If criteria were supplied above, those terms are already settled - do NOT ask for them again. If nothing is missing, give an empty list.

SECOND, identify the load-bearing assumptions.
{decompose_guidance}
Each must be:
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
    routine: "routines.Routine | None" = None,
    criteria: list[str] | None = None,
    claim_id: int | None = None,
    run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> Decomposition:
    """Return the load-bearing sub-claims, plus anything too vague to check."""
    criteria_block = ""
    if criteria:
        criteria_block = (
            "\nThe user has already defined what counts. A counter-example "
            "must satisfy ALL of these:\n"
            + "\n".join(f"- {c}" for c in criteria) + "\n"
        )
    use_existence = routine is not None and routine.name == "existence"
    template = EXISTENCE_PROMPT if use_existence else PROMPT
    fields = {"claim": claim, "criteria_block": criteria_block}
    if not use_existence:
        guidance = routine.decompose_guidance if routine else ""
        fields["decompose_guidance"] = (guidance + "\n") if guidance else ""
    payload = parsing.complete_json(
        config.SUPER,
        template.format(**fields),
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
