"""Step 15: invent the opposition.

One sentence: for each assumption, generate concrete ways it could turn out
to be false — before any searching happens.

This is the core of the whole project. A search engine will hand you back
whatever you asked for, so asking "is my claim true?" returns agreement. The
only way to find disconfirming evidence is to work out what the counter-claim
would look like first, then go hunting for that instead.

The hard part is that models love to restate. "Work experience might not
help" is not a falsification hypothesis; it is the assumption with a "not"
bolted on, and nothing can be searched for. "The admitted cohort is majority
straight from undergraduate" is a falsification hypothesis: specific, factual,
and either true or false in a document somewhere.

Runs on Nano: ~50 of these per claim, each one cheap.
"""

from __future__ import annotations

import sqlite3

from falsifier import config
from falsifier.clients import nebius
from falsifier.memory import routines
from falsifier.pipeline import parsing

ANGLES = [
    ("AUTHORITY", "the body that actually decides says otherwise"),
    ("NUMBERS", "the actual figures contradict it"),
    ("APPLICABILITY", "true in general, but not for this specific case"),
    ("TIMING", "it was true once but has changed, or has not taken effect yet"),
    ("DEFINITION", "a key term means something narrower or different"),
    ("CONFOUND", "something else explains the same observation"),
    ("MAGNITUDE", "real but too small to matter"),
    ("SOURCE", "the belief traces to a party with an interest in it"),
    ("SELECTION", "the evidence comes from an unrepresentative group"),
    ("TRADE-OFF", "true, but it costs more than it gains"),
]

PROMPT = """You are trying to prove an assumption WRONG. Not to argue about it, and not to hedge it: to name the specific states of the world that, if true, would demolish it.

Overall claim: "{claim}"
Assumption under attack: "{sub_claim}"

Generate exactly one hypothesis for each of these angles, and no others:

{angle_list}

Give exactly {count} hypotheses - one per angle listed above. Do not add
extras.

TWO CRITICAL RULES.

RULE 1 - do not invent documents. Never name a specific report, PDF, memo, webpage, policy or date unless it was given to you above, and never invent a quotation. You do not know what documents exist; the search step finds that out. State the fact about the world, not a fabricated citation.

RULE 2 - do not invent numbers. Never state a specific statistic, percentage, count or weighting. You have not looked anything up, so any figure you produce is fiction, and a fabricated figure sends the search hunting for something that may not exist. Describe the SHAPE of the fact and let the search find the real value.

Bad:  "The 2022 policy memo 'Evaluation of Applicants' states work experience is not a factor."
      (invented document, title and quote - breaks rule 1)
Bad:  "Fewer than 3% of admitted students had prior full-time work experience."
      (invented statistic - breaks rule 2)
Good: "The share of admitted students with prior full-time work experience is much lower than assumed."
      (same attack, no fabrication, and the search can find the real number)

Bad:  "Work experience may not be valuable."
      (vague, unsearchable, just the assumption negated)
Good: "Most admitted students enrolled directly from undergraduate study."

Return only JSON, in this shape:
[{{"angle": "NUMBERS", "hypothesis": "..."}}]"""


def hypothesise(
    claim: str,
    sub_claim: str,
    *,
    routine: "routines.Routine | None" = None,
    count: int = 10,
    sub_claim_id: int | None = None,
    run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[str]:
    """Return concrete ways `sub_claim` could be false."""
    chosen = (routine.angles if routine else ANGLES)[:count]
    payload = parsing.complete_json(
        config.NANO,
        PROMPT.format(
            claim=claim,
            sub_claim=sub_claim,
            count=len(chosen),
            angle_list="\n".join(
                f"{i}. {name} - {desc}" for i, (name, desc) in enumerate(chosen, 1)
            ),
        ),
        stage="hypothesise",
        max_tokens=3000,
        run_id=run_id,
        conn=conn,
    )
    hypotheses = parsing.as_list_of_strings(payload, key="hypothesis")[:count]

    if sub_claim_id is not None and conn is not None:
        conn.executemany(
            "INSERT INTO hypotheses (sub_claim_id, run_id, text) VALUES (?, ?, ?)",
            [(sub_claim_id, run_id, text) for text in hypotheses],
        )
        conn.commit()
    return hypotheses
