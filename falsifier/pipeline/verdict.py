"""Step 21: decide what the evidence actually shows.

One sentence: weigh everything retrieved and return one of three honest
answers - the claim is challenged, the claim held up, or it cannot be
settled and here is why.

This is the stage that stops the tool being a contrarian. Attacking the
claim is the method; the verdict is the product. If forty angles were tried
and the claim survived, the right answer is to say so and show the evidence
that supports it. If the claim cannot be settled - because it is too vague,
or depends on something only the user knows, or nobody has published
anything either way - the right answer is to say that plainly rather than
manufacture a doubt.

Runs on Ultra: once or twice per claim, and it is the judgement that
everything else feeds into.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from falsifier import config
from falsifier.pipeline import parsing, read

CHALLENGED = "challenges"
SUPPORTED = "supports"
UNVERIFIABLE = "unverifiable"

# A verdict can be no stronger than the source under it. Seen on 19 Oct:
# a Reddit post, already graded "weak" by the system, was allowed to carry
# an objection at 80% confidence. Grading a source and then ignoring the
# grade is worse than not grading it, because it looks rigorous.
CONFIDENCE_CEILING = {"primary": 1.0, "secondary": 0.7, "weak": 0.35}

# Below this, an objection is not worth putting in front of someone as a
# reason to change their plans. It is reported as unsettled instead.
MIN_CONFIDENCE_TO_TAKE_A_SIDE = 0.4

PROMPT = """You investigated a claim by trying hard to disprove it. Now \
report honestly on what the evidence shows.

CLAIM: "{claim}"

ASSUMPTION EXAMINED: "{sub_claim}"

EVIDENCE RETRIEVED (every quote below is verified to appear in the page at \
the URL given):
{evidence}

{ambiguity_note}

Decide between exactly three verdicts.

CHALLENGES - the evidence genuinely undermines the assumption. Only choose \
this if a specific quote does real damage. Do not stretch weak evidence into \
an objection.

SUPPORTS - you tried to disprove it and it held. The evidence is consistent \
with the assumption, or actively backs it. This is a legitimate and useful \
result. Say so plainly rather than hedging, and point at the quote that \
supports it.

UNVERIFIABLE - the evidence does not settle it either way. Choose this when \
the sources are silent, when they conflict without resolution, when the \
claim depends on something only the user can tell you, or when the claim is \
too vague to check as written. Give a specific reason, and if the user \
could resolve it, say exactly what they would need to supply.

Rules:
- Never state a conclusion that no quote supports. If you want to say \
something the evidence does not show, the verdict is UNVERIFIABLE.
- Do not manufacture doubt. An assumption that survived scrutiny is a real \
finding.
- Quote only from the evidence above. Do not introduce outside knowledge.
- Address the claim, never the person who holds it.

Return only JSON:
{{"verdict": "CHALLENGES|SUPPORTS|UNVERIFIABLE",
  "statement": "one or two sentences, plain language",
  "evidence_index": <number of the quote you relied on, or null>,
  "reason": "required for UNVERIFIABLE: why, and what would settle it",
  "confidence": 0.0 to 1.0}}"""


@dataclass
class Verdict:
    """One honest answer about one assumption."""

    stance: str
    statement: str
    evidence: read.Evidence | None = None
    reason: str | None = None
    confidence: float = 0.5
    sub_claim: str = ""

    @property
    def agrees(self) -> bool:
        return self.stance == SUPPORTED


@dataclass
class ClaimReport:
    """Everything concluded about one claim."""

    claim: str
    verdicts: list[Verdict] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)

    @property
    def challenged(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.stance == CHALLENGED]

    @property
    def supported(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.stance == SUPPORTED]

    @property
    def unverifiable(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.stance == UNVERIFIABLE]

    @property
    def headline(self) -> str:
        """What to tell the user in one line."""
        if self.challenged:
            n = len(self.challenged)
            return f"{n} objection{'s' if n > 1 else ''} survived scrutiny."
        if self.supported and not self.unverifiable:
            return "Tried to disprove this and could not. The claim held up."
        if self.supported:
            return (
                f"{len(self.supported)} part(s) held up; "
                f"{len(self.unverifiable)} could not be settled."
            )
        return "Could not settle this either way."


def _format_evidence(items: list[read.Evidence]) -> str:
    if not items:
        return "(nothing was retrieved that bore on this assumption)"
    lines = []
    for i, e in enumerate(items, 1):
        date = e.published_date or "no date shown on the page"
        lines.append(
            f'[{i}] "{e.quote}"\n'
            f"    url: {e.url}\n"
            f"    source quality: {e.source_tier}, {date}, "
            f"bearing: {e.bearing}"
        )
    return "\n\n".join(lines)


def judge(
    claim: str,
    sub_claim: str,
    evidence: list[read.Evidence],
    *,
    ambiguities: list[str] | None = None,
    run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> Verdict:
    """Weigh the evidence for one assumption and return one of three answers."""
    note = ""
    if ambiguities:
        note = (
            "THE USER HAS NOT SPECIFIED:\n"
            + "\n".join(f"- {a}" for a in ambiguities)
            + "\nIf the verdict turns on any of these, it is UNVERIFIABLE and "
            "you must say which detail is needed."
        )

    payload = parsing.complete_json(
        config.ULTRA,
        PROMPT.format(
            claim=claim,
            sub_claim=sub_claim,
            evidence=_format_evidence(evidence),
            ambiguity_note=note,
        ),
        stage="survive",
        max_tokens=3000,
        run_id=run_id,
        conn=conn,
    )
    # Models occasionally wrap the verdict in a list, or in a single-key
    # envelope. Unwrap rather than losing the whole sub-claim over shape.
    if isinstance(payload, list) and payload:
        payload = payload[0]
    if isinstance(payload, dict) and "verdict" not in payload and len(payload) == 1:
        inner = next(iter(payload.values()))
        if isinstance(inner, dict):
            payload = inner
    if not isinstance(payload, dict):
        raise parsing.ParseError("verdict was not an object")

    stance = {
        "CHALLENGES": CHALLENGED,
        "SUPPORTS": SUPPORTED,
        "UNVERIFIABLE": UNVERIFIABLE,
    }.get(str(payload.get("verdict", "")).upper(), UNVERIFIABLE)

    chosen = None
    index = payload.get("evidence_index")
    if isinstance(index, int) and 1 <= index <= len(evidence):
        chosen = evidence[index - 1]

    reason = payload.get("reason") or None

    # Rule 1, applied in code rather than trusted to the prompt: a verdict
    # that takes a side must point at a real quote. Without one it is
    # downgraded to unverifiable, never silently kept.
    if stance in (CHALLENGED, SUPPORTED) and chosen is None:
        stance = UNVERIFIABLE
        reason = reason or (
            "The model reached a conclusion without citing a retrieved quote, "
            "so it cannot be shown to you and was not accepted."
        )

    if stance == UNVERIFIABLE:
        chosen = None
        reason = reason or "The sources retrieved do not settle this either way."

    confidence = payload.get("confidence")
    try:
        confidence = min(1.0, max(0.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.5

    # Cap confidence at what the source can bear, then refuse to take a
    # side at all on evidence too weak to act on.
    if chosen is not None:
        ceiling = CONFIDENCE_CEILING.get(chosen.source_tier, 0.5)
        if confidence > ceiling:
            confidence = ceiling
        if (stance in (CHALLENGED, SUPPORTED)
                and confidence < MIN_CONFIDENCE_TO_TAKE_A_SIDE):
            reason = (
                f"The only evidence found was a {chosen.source_tier} source "
                f"({chosen.url}), which is not strong enough to {stance[:-1]} "
                "a claim you might act on."
            )
            stance = UNVERIFIABLE
            chosen = None

    return Verdict(
        stance=stance,
        statement=str(payload.get("statement", "")).strip() or "(no statement)",
        evidence=chosen,
        reason=reason,
        confidence=confidence,
        sub_claim=sub_claim,
    )
