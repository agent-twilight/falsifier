"""Talking back.

One sentence: answer a follow-up using what the thread already knows, and
work out when a question needs fresh searching instead of an answer.

A report is not a conversation. Most follow-ups do not need another forty
searches — "what did you mean by equity refresh?", "I'm in Bangalore not
California", "which of those matters most?" are all answerable from what is
already on the thread, in seconds and for a fraction of a cent.

But some genuinely need new evidence: "has the date changed since?", "what
about the Pune centre?". Those should trigger a real check rather than a
confident guess, and the distinction is made here.

Runs on Super: few calls, and getting it wrong either wastes a search
budget or fakes an answer.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from falsifier import config
from falsifier.pipeline import parsing

PROMPT = """You are helping someone think about a plan. You have already \
looked into it. They have asked a follow-up.

THE PLAN:
"{claim}"

WHAT YOU ESTABLISHED, WITH SOURCES:
{findings}

WHAT YOU REASONED (inference, not evidence):
{assessment}

THE CONVERSATION SO FAR:
{history}

THEIR MESSAGE:
"{message}"

---

First decide: can you answer this from what you already know, or does it \
need fresh evidence from the web?

It needs a NEW CHECK when they ask about something you have not looked at, \
when they ask whether something has changed since, or when they introduce a \
fact that changes which sources matter (a different city, a different \
programme, a different year).

It does NOT need a new check when they are asking what you meant, asking \
you to compare or prioritise what you already found, thinking aloud, or \
asking you to reason further from the same facts.

Then write your reply.

Rules:

- Write like a person talking. Short sentences. No "I understand your
  question", no "it is important to note", no restating what they just said
  back at them.
- Separate what you can prove from what you are working out. If you are
  inferring, say so in the sentence: "no one publishes this, but..."
- If they have told you something new about their situation, use it. If it
  changes an earlier answer, say that plainly.
- Never invent a figure and present it as established.
- If you are about to go and search, say what you are going to look for and
  why, in one line. Do not pad it.
- No praise. No "great question". No encouragement.
- Address the plan, never the person.
- Usually under 150 words. Length is not helpfulness.

Return only JSON:
{{"needs_check": true or false,
  "check_claim": "if needs_check, the precise claim to investigate, else null",
  "reply": "what you say to them"}}"""


@dataclass
class Reply:
    text: str
    needs_check: bool = False
    check_claim: str | None = None


def _format_history(messages, limit: int = 12) -> str:
    if not messages:
        return "(nothing yet)"
    recent = messages[-limit:]
    out = []
    for m in recent:
        who = "They" if m.role == "user" else "You"
        label = " (arrived unprompted)" if m.kind == "alert" else ""
        out.append(f"{who}{label}: {m.body[:600]}")
    return "\n\n".join(out)


def respond(
    message: str,
    *,
    claim: str = "",
    findings: str = "",
    assessment: str = "",
    messages=None,
    run_id: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> Reply:
    """Answer a follow-up, or decide it needs looking into."""
    payload = parsing.complete_json(
        config.SUPER,
        PROMPT.format(
            claim=claim or "(not yet stated)",
            findings=findings or "(nothing checked yet)",
            assessment=assessment or "(none yet)",
            history=_format_history(messages or []),
            message=message,
        ),
        stage="converse",
        max_tokens=2500,
        run_id=run_id,
        conn=conn,
    )
    if not isinstance(payload, dict):
        return Reply(text="I did not follow that. Could you put it another way?")

    text = str(payload.get("reply", "")).strip()
    needs = bool(payload.get("needs_check"))
    target = payload.get("check_claim")
    target = str(target).strip() if target and str(target).lower() != "null" else None

    # Asking for a check without saying what to check is not actionable.
    if needs and not target:
        needs = False

    return Reply(
        text=text or "I did not follow that. Could you put it another way?",
        needs_check=needs,
        check_claim=target,
    )
