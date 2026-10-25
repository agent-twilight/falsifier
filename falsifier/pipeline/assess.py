"""What a person actually wanted to know.

One sentence: after the cited findings, say the useful thing — what the
claim really hinges on, what can reasonably be inferred, and what the
person's options are.

Why this exists. The citation rule means a verdict needs an exact quoted
line, which stops fabrication. But applied alone it produced "cannot be
checked" on three out of four claims, because most interesting questions
have no single page that settles them. Told "staying in my role at Nvidia
could make me a multimillionaire", the pipeline correctly reported that
Nvidia does not publish compensation for that level — and stopped. That is
accurate and nearly useless. The person did not ask about Nvidia's payroll
disclosures. They asked whether their plan gets them where they want to go.

So this stage reasons past the citations, and says plainly that it is
reasoning. The separation is the point:

- **Findings** are quoted, linked, and checkable. Nothing fabricated.
- **This** is inference from them, labelled as inference, never dressed up
  as evidence.

A reader can take the findings as fact and weigh the reasoning themselves.
Collapsing the two would be dishonest; refusing to reason at all was
merely unhelpful.

Runs on Ultra, once per claim. It is the judgement the rest feeds into.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from falsifier import config
from falsifier.pipeline import parsing

PROMPT = """Someone told you what they are planning. You have checked it \
against sources. Now tell them the useful thing.

WHAT THEY SAID:
"{claim}"

WHAT YOU CHECKED, AND FOUND:
{findings}

EVIDENCE YOU RETRIEVED (every quote verified present at its URL):
{evidence}

---

Work out what they are actually trying to achieve. It is usually not the \
literal claim. Someone asking whether staying in a job makes them rich is \
asking how to get rich, and the job is one route they happen to be \
considering. Someone asking whether their revision plan is sound wants to \
pass the exam.

Then write them something worth reading. Cover, in whatever order serves \
them:

- **What this really turns on.** The one or two things that decide it,
  which may not be what they asked about.
- **What the sources settled**, briefly. Do not repeat them at length;
  they can read the findings.
- **What you can reasonably work out anyway**, where the sources are
  silent. Use comparable cases, published figures for similar situations,
  arithmetic. SAY you are inferring. "Nvidia does not publish this, but
  senior ML roles at comparable firms are widely reported at X to Y, so..."
  is useful. Pretending certainty is not.
- **What is in their control and what is not.** People systematically
  overweight the parts they cannot affect.
- **What would change the answer most.** The single fact worth going and
  finding out, or the single decision worth making differently.

Rules:

- Write to them the way a well-informed friend would, not the way a report would. Short sentences. Contractions are fine. No "the assumption cannot
  be verified", no "it is important to note", no bullet-point
  throat-clearing. If you would not say it out loud to a friend who asked,
  do not write it.
- Never invent a number and present it as fact. Inference must be visibly
  inference.
- Do not repeat that something is unverifiable. They already have that.
  Your job is what to do about it.
- No praise, no encouragement, no "great question". Be useful, not warm.
- Address the plan, never the person. Never imply anything about their
  ability or character.
- 150 to 300 words. Shorter if you have less to say.

Return only JSON:
{{"hinges_on": "one sentence: what actually decides this",
  "assessment": "the body, 150-300 words, plain prose",
  "inferred": ["each thing you worked out rather than read, one per line"],
  "worth_finding_out": "the single most valuable unknown, or null"}}"""


@dataclass
class Assessment:
    """Reasoning past the citations, labelled as reasoning."""

    hinges_on: str
    body: str
    inferred: list[str]
    worth_finding_out: str | None = None

    @property
    def usable(self) -> bool:
        return bool(self.body.strip())


def _format_findings(verdicts) -> str:
    if not verdicts:
        return "(nothing was concluded)"
    lines = []
    for v in verdicts:
        label = {"challenges": "NO LONGER TRUE", "supports": "STILL TRUE"}.get(
            v.stance, "COULD NOT CHECK"
        )
        lines.append(f"[{label}] {v.sub_claim}\n    {v.statement}")
        if v.reason:
            lines.append(f"    why: {v.reason}")
    return "\n".join(lines)


def _format_evidence(evidence) -> str:
    if not evidence:
        return "(nothing was retrieved)"
    return "\n\n".join(
        f'"{e.quote}"\n    {e.url} ({e.source_tier})' for e in evidence[:12]
    )


def assess(
    claim: str,
    verdicts,
    evidence,
    *,
    run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> Assessment | None:
    """Say the useful thing. Returns None if it has nothing to add."""
    payload = parsing.complete_json(
        config.ULTRA,
        PROMPT.format(
            claim=claim,
            findings=_format_findings(verdicts),
            evidence=_format_evidence(evidence),
        ),
        stage="assess",
        max_tokens=3000,
        run_id=run_id,
        conn=conn,
    )
    if not isinstance(payload, dict):
        return None

    body = str(payload.get("assessment", "")).strip()
    if not body:
        return None

    inferred = parsing.as_list_of_strings(payload.get("inferred", []) or [])
    worth = payload.get("worth_finding_out")
    worth = str(worth).strip() if worth and str(worth).lower() != "null" else None

    return Assessment(
        hinges_on=str(payload.get("hinges_on", "")).strip(),
        body=body,
        inferred=inferred,
        worth_finding_out=worth,
    )
