"""Is this something to check, or something to answer?

One sentence: work out whether the person stated a claim or asked a
question, because the two need completely different handling.

Asked "can you give me a roadmap to learning Python?", the checking
pipeline did what it was built to do: invented a sub-claim about whether
python.org hosts current install guides, searched for it, found noise and
reported it could not settle the matter. Every stage worked. It was
pointed at the wrong kind of input.

A question wants an answer. Searching forty angles for disconfirming
evidence against "can you give me a roadmap" is not just wasteful - it
spends the search budget, which is the one thing that runs out - it is
also actively worse than simply answering.

Runs on Nano with reasoning off: it is a one-word decision made before
anything expensive happens.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from falsifier import config
from falsifier.pipeline import parsing

CLAIM = "claim"
ASK = "ask"

CLASSIFY_PROMPT = """Someone has written to an assistant that checks \
whether plans and beliefs still hold up against current information.

They wrote: "{message}"

Is this a CLAIM or an ASK?

CLAIM - they have asserted something about the world that evidence could
confirm or contradict. Usually a plan they hold, a belief they are acting
on, or a statement of fact. "Two years of work experience strengthens my
application." "The exam is in April." "No tool does this yet." "Staying in
this job will make me rich." Note the last one: it is phrased as a belief
and the world can speak to it.

ASK - they want something produced or explained. A question, a request for
advice, a plan they want help building, a how-to. "Give me a roadmap to
learning Python." "Which Stanford programme suits me?" "How should I
revise?" "What do you think about X?"

If they assert something AND ask about it, treat it as a CLAIM; the check
will cover the question.

Answer with one word, claim or ask."""

ANSWER_PROMPT = """Someone asked you this:

"{message}"

{context}

Answer it properly, the way a knowledgeable friend would. Give them the \
actual thing they asked for - if they want a roadmap, write the roadmap; \
if they want a recommendation, recommend something and say why.

Rules:

- Be concrete and specific. Name real things: real libraries, real
  programmes, real steps in a real order. Vague advice is worthless.
- Write plainly. Short sentences. Contractions are fine. No "it is
  important to note", no preamble, no summarising the question back.
- This is your own knowledge, not something you looked up, so do not
  pretend otherwise. Do not cite URLs, do not quote pages, do not invent
  sources. If something may have changed recently or varies by case, say
  so in the sentence.
- No praise, no encouragement, no "great question".
- Structure it if that helps them, but do not pad it out. Length is not
  helpfulness.

Return only JSON:
{{"answer": "your answer, in markdown",
  "watchable": "one short phrase naming what in their situation could
                change and be worth watching, or null if nothing obvious"}}"""


@dataclass
class Answer:
    text: str
    watchable: str | None = None


def classify(
    message: str, *, run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> str:
    """CLAIM or ASK. Defaults to ASK, which is the cheaper mistake.

    Answering a claim as though it were a question costs one model call.
    Checking a question as though it were a claim costs forty searches out
    of a budget of about a thousand.
    """
    from falsifier.clients import nebius

    try:
        result = nebius.complete(
            config.NANO,
            CLASSIFY_PROMPT.format(message=message[:1200]),
            stage="intent",
            no_think=True,
            max_tokens=600,
            run_id=run_id,
            conn=conn,
        )
        return CLAIM if "claim" in result.text.strip().lower() else ASK
    except Exception:  # noqa: BLE001 - never block on the cheap decision
        return ASK


def answer(
    message: str, *, history: str = "", run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> Answer:
    """Answer a question directly. No searching, so no credits spent."""
    context = f"Earlier in the conversation:\n{history}\n" if history else ""
    payload = parsing.complete_json(
        config.SUPER,
        ANSWER_PROMPT.format(message=message[:2000], context=context),
        stage="answer",
        max_tokens=3000,
        run_id=run_id,
        conn=conn,
    )
    if not isinstance(payload, dict):
        return Answer(text="I did not follow that. Could you put it another way?")

    watchable = payload.get("watchable")
    watchable = (str(watchable).strip()
                 if watchable and str(watchable).strip().lower() != "null"
                 else None)
    return Answer(
        text=str(payload.get("answer", "")).strip()
             or "I did not follow that. Could you put it another way?",
        watchable=watchable,
    )
