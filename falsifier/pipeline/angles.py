"""Step 16: turn a hypothesis into search queries that could confirm it.

One sentence: the query must hunt for the counter-evidence, not for the
original belief.

This is where the project earns its keep. Typing "is work experience good
for grad school" returns pages agreeing, because relevance ranking matches
your phrasing. To find the disconfirming evidence you have to search for the
thing that would disprove you, which means searching for the hypothesis
rather than the claim.

Queries also aim at where primary sources live - the issuing body's own
pages, published statistics, official FAQs - rather than at commentary.

Runs on Nano: cheap, and there are a dozen or so per claim.
"""

from __future__ import annotations

import sqlite3

from falsifier import config
from falsifier.clients import nebius
from falsifier.pipeline import parsing

PROMPT = """Write web search queries that would find evidence FOR the \
following hypothesis.

Hypothesis: "{hypothesis}"
(This hypothesis, if true, would undermine the belief: "{claim}")

The queries must hunt for the hypothesis, NOT for the original belief. \
Searching for the belief returns pages that agree with it, which is useless \
here.

Aim at where authoritative evidence actually lives: the issuing body's own \
website, published statistics and class profiles, official FAQs and policy \
pages, regulatory filings. Not blogs, not forums, not consultancies.

Write {count} queries. Each should:
- read like something typed into a search box, not a sentence
- use the words the authoritative source would itself use
- attack from a different direction to the others

Do not invent document names or statistics.

Return only JSON: a list of strings."""


def angles(
    claim: str,
    hypothesis: str,
    *,
    count: int = 3,
    run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[str]:
    """Return search queries aimed at confirming `hypothesis`."""
    payload = parsing.complete_json(
        config.NANO,
        PROMPT.format(claim=claim, hypothesis=hypothesis, count=count),
        stage="query-angles",
        max_tokens=1500,
        run_id=run_id,
        conn=conn,
    )
    return parsing.as_list_of_strings(payload)
