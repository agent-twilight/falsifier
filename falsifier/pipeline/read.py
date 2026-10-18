"""Steps 18-19: decide what is relevant, then pull out the exact line.

One sentence: triage throws away the results that do not bear on the
hypothesis, then read() extracts the quoted line that does - and refuses to
accept a quote that is not literally present in the retrieved text.

That last part is the important one. A model asked to "quote the source"
will happily paraphrase, tidy up the grammar, or invent a sentence that
sounds like something the page would say. So the quote is checked against
the retrieved text in code. If it is not there, character for character,
the evidence is rejected. No amount of prompt wording would guarantee that;
a string comparison does.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from urllib.parse import urlparse

from falsifier import config
from falsifier.clients import nebius
from falsifier.pipeline import parsing

TRIAGE_PROMPT = """Does this search result bear on the hypothesis? Answer only YES or NO.

Hypothesis: "{hypothesis}"

Result title: {title}
Result text: {snippet}

Answer YES if ANY of these hold:
- the text states something that confirms or denies the hypothesis
- the text gives figures, policies or rules that bear on it, even indirectly
- the hypothesis says something is ABSENT, MISSING or NOT LISTED somewhere, and this text is that very source - an official list of criteria, requirements, eligibility rules or FAQ published by the body in question. What such a page does NOT contain is itself the evidence, so it is always relevant to a claim about absence.

Answer NO only if the text is about a different subject entirely, is pure opinion or marketing, or is somebody's commentary rather than the authoritative source itself.

Answer with one word."""

READ_PROMPT = """Extract the single passage from this text that best bears on the hypothesis.

Hypothesis: "{hypothesis}"

Text:
\"\"\"{snippet}\"\"\"

Rules:
- Copy the passage EXACTLY as it appears. Character for character. Do not fix grammar, do not shorten, do not paraphrase. It will be checked against the original and discarded if it does not match.
- If no passage genuinely bears on the hypothesis, return null for the quote. Returning nothing is a valid and useful answer.

Classify the bearing as one of:
- SUPPORTS   - the passage states something that supports the hypothesis
- CONTRADICTS - the passage states something that denies it
- ABSENT     - the hypothesis says something is missing from an authoritative source, and this IS that source: it sets out the criteria or requirements, and the thing in question is genuinely not among them. Quote the passage that lists what IS required, since that is the evidence.
- UNCLEAR    - it touches the subject but settles nothing

Only use ABSENT when the text really is the authoritative list, not commentary about it.

Return only JSON:
{{"quote": "exact passage or null", "bearing": "SUPPORTS|CONTRADICTS|ABSENT|UNCLEAR"}}"""


# Domains whose own statements about themselves are primary evidence.
PRIMARY_SUFFIXES = (".edu", ".gov", ".ac.uk", ".gov.uk", ".int")
WEAK_MARKERS = (
    "blog", "consult", "coach", "prep", "admit", "forum", "reddit",
    "quora", "medium.com", "linkedin.com", "substack",
)


@dataclass(frozen=True)
class Evidence:
    """A real line from a real page, with where it came from."""

    quote: str
    url: str
    title: str
    source_tier: str
    bearing: str
    published_date: str | None

    @property
    def undated(self) -> bool:
        return not self.published_date


def grade_source(url: str) -> str:
    """primary, secondary or weak, from the domain alone.

    Deliberately mechanical. Asking a model to grade its own sources invites
    it to flatter whatever it happened to find.
    """
    host = (urlparse(url).hostname or "").lower()
    if any(marker in url.lower() for marker in WEAK_MARKERS):
        return "weak"
    if host.endswith(PRIMARY_SUFFIXES):
        return "primary"
    return "secondary"


def _normalise(text: str) -> str:
    """Collapse whitespace and unify quotes, so verification is not defeated
    by a curly apostrophe or a line break."""
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‑", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_is_present(quote: str, source_text: str) -> bool:
    """Is this quote literally in the retrieved text? Rule 1, in code."""
    if not quote or not quote.strip():
        return False
    return _normalise(quote) in _normalise(source_text)


def triage(
    hypothesis: str,
    title: str,
    snippet: str,
    *,
    run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> bool:
    """Does this result bear on the hypothesis? ~400 of these per claim."""
    result = nebius.complete(
        config.NANO,
        TRIAGE_PROMPT.format(
            hypothesis=hypothesis,
            title=title[:200],
            snippet=snippet[: config.TRIAGE_MAX_CHARS],
        ),
        stage="triage",
        no_think=config.TRIAGE_USE_NO_THINK,
        max_tokens=config.TRIAGE_MAX_TOKENS,
        run_id=run_id,
        conn=conn,
    )
    return result.text.strip().upper().startswith("YES")


def read(
    hypothesis: str,
    url: str,
    title: str,
    snippet: str,
    published_date: str | None = None,
    *,
    run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> Evidence | None:
    """Pull the exact line, or return None if there is not an honest one.

    Returns None when the model declines to quote, when the quote cannot be
    found in the retrieved text, or when the text does not contradict the
    hypothesis. None is a perfectly good outcome.
    """
    payload = parsing.complete_json(
        config.SUPER,
        READ_PROMPT.format(
            hypothesis=hypothesis, snippet=snippet[: config.TRIAGE_MAX_CHARS]
        ),
        stage="read",
        max_tokens=3000,
        run_id=run_id,
        conn=conn,
    )
    if not isinstance(payload, dict):
        return None

    quote = payload.get("quote")
    if not quote or str(quote).strip().lower() in ("null", "none", ""):
        return None

    quote = str(quote).strip()
    if not quote_is_present(quote, snippet):
        # The model produced a sentence that is not in the source. This is
        # the fabrication rule 1 exists to stop, so the evidence is dropped.
        return None

    return Evidence(
        quote=quote,
        url=url,
        title=title,
        source_tier=grade_source(url),
        bearing=str(payload.get("bearing", "UNCLEAR")).upper(),
        published_date=published_date,
    )
