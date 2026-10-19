"""Falsification routines: how to attack a *kind* of claim.

One sentence: a claim about whether a product exists needs completely
different searching from a claim about what a university requires, so each
class of claim gets its own stored procedure.

This exists because of a real failure on 19 Oct. Asked whether any tool
already does what the Falsifier does, the pipeline applied its general
angles - authority, numbers, timing, definitions - and produced searches
like `plan "high-level objectives" site:gov` and `proactive alert
definition glossary`. Nine of sixty results were relevant. The attack
framework was built for factual claims and does not fit an existence claim,
where the right move is to go looking for the product.

A routine stores three things:
  - the angles worth attacking that class of claim from
  - where primary evidence lives for it
  - what the search should actually look like

They are data, not code, so new ones can be added without touching the
pipeline, and so the agent can show you which routine it used and why.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Routine:
    """A stored procedure for attacking one class of claim."""

    name: str
    description: str
    applies_when: str
    angles: list[tuple[str, str]]
    primary_sources: str
    query_guidance: str
    weak_sources: str = ""
    decompose_guidance: str = ""
    generated: bool = False


EXISTENCE = Routine(
    name="existence",
    description="Does this thing already exist? Has someone built it?",
    applies_when=(
        "the claim asserts that something does not exist, has not been done, "
        "is unoccupied, is novel, or that no tool/product/paper covers it"
    ),
    angles=[
        ("DIRECT_COMPETITOR", "a product doing exactly this already ships"),
        ("ADJACENT_CATEGORY", "it exists under a name the claimant does not use"),
        ("INCUMBENT_FEATURE", "a large existing product shipped this as a feature"),
        ("PARTIAL_OVERLAP", "two existing products together cover the gap"),
        ("PRIOR_ART", "a paper, patent or open-source project did it first"),
        ("FAILED_ATTEMPT", "somebody built it and it died, which is worse news"),
        ("TERMINOLOGY", "the field calls this something else entirely"),
        ("SCOPE", "it exists for a neighbouring audience or domain"),
    ],
    primary_sources=(
        "product pages and pricing pages, changelogs and release notes, "
        "app and plugin directories, startup directories and funding "
        "announcements, arXiv and patent filings, GitHub"
    ),
    weak_sources=(
        "listicles and 'best 10 apps' roundups, affiliate review sites, "
        "content farms, undated Medium posts, forum speculation"
    ),
    decompose_guidance=(
        "Do not decompose into assumptions. Enumerate the categories or "
        "domains where a counter-example would most plausibly be found, "
        "since an existence claim is settled by looking rather than by "
        "reasoning."
    ),
    query_guidance=(
        "Search the way a buyer would, not the way a researcher would. Use "
        "the words a product would use to sell itself, plus category words "
        "like app, tool, platform, alternative, vs, competitors, pricing, "
        "changelog. Never use site:gov, never search for definitions or "
        "glossaries, and never search for the absence of a thing - search "
        "for the thing. "
        "When the claim is about a tool that watches the world on the "
        "user's behalf, keep the inward/outward distinction sharp. INWARD "
        "is the user's own input played back to them: reminders, to-do "
        "lists, calendar alerts, habit streaks, deadline nudges. Every "
        "reminder app does this and NONE of it is relevant. OUTWARD is "
        "information arriving from outside the user's control that changes "
        "what they should do: a rule changed, a date moved, a competitor "
        "launched. Search only for outward. Use words like monitors, "
        "tracks changes, watches for updates, alerts when something "
        "changes, news monitoring, change detection - not reminder, "
        "to-do, scheduler, planner or task."
    ),
)

REQUIREMENT = Routine(
    name="requirement",
    description="Does this body actually require, permit or forbid this?",
    applies_when=(
        "the claim is about eligibility, rules, criteria, deadlines or "
        "policy set by a named institution"
    ),
    angles=[
        ("AUTHORITY", "the body that decides says otherwise"),
        ("TIMING", "the rule changed, or has not taken effect"),
        ("APPLICABILITY", "the rule exists but not for this case"),
        ("DEFINITION", "a key term is narrower than assumed"),
        ("EXCEPTION", "a documented carve-out applies"),
        ("CONFLICT", "two official sources disagree"),
    ],
    primary_sources=(
        "the issuing body's own site, official eligibility and criteria "
        "pages, published handbooks, FAQs and policy documents"
    ),
    weak_sources=(
        "coaching centres, admissions consultancies, forums, YouTube "
        "summaries, news reports of the rule rather than the rule itself"
    ),
    decompose_guidance=(
        "Break the claim into each separate condition the body imposes, so "
        "each can be checked against their own published wording."
    ),
    query_guidance=(
        "Go to the issuing body's own pages. Use their vocabulary: "
        "eligibility, requirements, criteria, admission, policy, handbook. "
        "Commentary and consultancy blogs are not evidence here."
    ),
)

EFFECT = Routine(
    name="effect",
    description="Does doing X actually produce outcome Y?",
    applies_when=(
        "the claim asserts a causal or statistical relationship: that "
        "something helps, improves, increases, strengthens or causes "
        "something else"
    ),
    angles=[
        ("NUMBERS", "the published figures contradict it"),
        ("CONFOUND", "something else explains the same observation"),
        ("SELECTION", "the evidence comes from an unrepresentative group"),
        ("MAGNITUDE", "real, but too small to matter"),
        ("SOURCE", "the belief traces to a party with an interest in it"),
        ("REVERSAL", "later or better evidence overturned the earlier result"),
        ("TRADE-OFF", "true, but it costs more than it gains"),
    ],
    primary_sources=(
        "published statistics and cohort profiles, peer-reviewed studies, "
        "meta-analyses, regulator or registry data"
    ),
    weak_sources=(
        "vendor-funded surveys, press releases about studies, anecdote, "
        "blogs summarising research they do not link to"
    ),
    decompose_guidance=(
        "Separate the claimed cause, the claimed effect, and the population "
        "it is claimed to hold for, so each can be checked independently."
    ),
    query_guidance=(
        "Search for the measurement, not the opinion. Use words like data, "
        "statistics, study, outcomes, profile, report, percentage. Seek the "
        "figures themselves rather than articles describing them."
    ),
)

ALL = (EXISTENCE, REQUIREMENT, EFFECT)
BY_NAME = {r.name: r for r in ALL}
DEFAULT = EFFECT
CLASSIFY_PROMPT = """Would any of these routines actually work for this claim?

Claim: "{claim}"

{options}
- none: none of the above would work for this claim

A routine only fits if BOTH are true:
1. the claim is the shape the routine describes, AND
2. the routine's primary sources are genuinely the right places to look
   for THIS claim's subject matter.

Condition 2 is where most mistakes happen. A claim about whether training
from a late age leads to a professional dance career is shaped like a
cause-and-effect claim, but "peer-reviewed studies and regulator data" is
not where that answer lives. It lives with dance companies, vocational
schools and audition requirements. In that case answer "none", because a
routine that sends the search to the wrong sources is worse than no
routine.

Answer with the name only, in lower case, or "none"."""


GENERATE_PROMPT = """Write a falsification routine for the kind of claim \
below: a reusable procedure for checking claims of this type, which will be \
stored and used again for every future claim in the same domain.

Claim: "{claim}"

A routine captures how an experienced researcher in this domain would check \
such a claim. Who would they ask, what would they read, what would they \
ignore, and what are the usual ways a belief of this kind turns out wrong?

Give:

1. name - one lower-case word or hyphenated phrase for the CLASS of claim,
   not this specific claim. Not "ballet" but something like
   "training-pathway" if the class is really about how one trains for a
   demanding skill.
2. description - one line, what kind of claim this covers.
3. applies_when - when a future claim should use this routine.
4. angles - six to eight ways a claim of this kind typically turns out to
   be wrong. Each needs a short upper-case label and a one-line
   description. Make them specific to the domain rather than generic: for
   physical training, age windows and injury rates matter; for a legal
   domain, jurisdiction and commencement dates matter.
5. primary_sources - the kinds of source that are decisive here. Be
   concrete: name the types of organisation and document.
6. weak_sources - the kinds that look authoritative but are not, plus the
   usual noise.
7. decompose_guidance - how to break a claim of this kind into parts that
   can each be checked separately.
8. query_guidance - how to search in this domain: what vocabulary works,
   what to avoid, what a knowledgeable person would actually type.

Return only JSON:
{{"name": "...", "description": "...", "applies_when": "...",
  "angles": [["LABEL", "description"]],
  "primary_sources": "...", "weak_sources": "...",
  "decompose_guidance": "...", "query_guidance": "..."}}"""


def _row_to_routine(row) -> Routine:
    return Routine(
        name=row["name"],
        description=row["description"],
        applies_when=row["applies_when"],
        angles=[tuple(a) for a in json.loads(row["angles"])],
        primary_sources=row["primary_sources"],
        weak_sources=row["weak_sources"],
        decompose_guidance=row["decompose_guidance"],
        query_guidance=row["query_guidance"],
        generated=bool(row["generated"]),
    )


def save(conn: sqlite3.Connection, routine: Routine) -> None:
    """Store a routine so the next claim in this domain reuses it."""
    conn.execute(
        "INSERT OR REPLACE INTO routines (name, description, applies_when, "
        "angles, primary_sources, weak_sources, decompose_guidance, "
        "query_guidance, generated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (routine.name, routine.description, routine.applies_when,
         json.dumps(routine.angles), routine.primary_sources,
         routine.weak_sources, routine.decompose_guidance,
         routine.query_guidance, 1 if routine.generated else 0),
    )
    conn.commit()


def available(conn: sqlite3.Connection | None = None) -> list[Routine]:
    """The three built in, plus every one the agent has written since."""
    found = list(ALL)
    if conn is None:
        return found
    known = {r.name for r in found}
    for row in conn.execute("SELECT * FROM routines ORDER BY name"):
        if row["name"] not in known:
            found.append(_row_to_routine(row))
    return found


def generate(
    claim: str, *, run_id=None, conn: sqlite3.Connection | None = None
) -> Routine | None:
    """Write a routine for a domain we have never seen, and keep it.

    This is the difference between a tool that handles three kinds of
    question and one that handles whatever is brought to it. A claim about
    becoming a ballet dancer has no stored routine, so the agent works out
    how someone who knows that world would check it, then remembers.
    """
    from falsifier import config
    from falsifier.pipeline import parsing

    payload = parsing.complete_json(
        config.SUPER,
        GENERATE_PROMPT.format(claim=claim),
        stage="generate-routine",
        max_tokens=3000,
        run_id=run_id,
        conn=conn,
    )
    if not isinstance(payload, dict):
        return None

    angles: list[tuple[str, str]] = []
    for item in payload.get("angles", []):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            angles.append((str(item[0]).strip().upper(), str(item[1]).strip()))
        elif isinstance(item, dict):
            label = item.get("label") or item.get("name") or ""
            desc = item.get("description") or item.get("desc") or ""
            if label and desc:
                angles.append((str(label).strip().upper(), str(desc).strip()))

    name = str(payload.get("name", "")).strip().lower().replace(" ", "-")
    name = "".join(c for c in name if c.isalnum() or c == "-")

    # A routine with two angles is not a routine, and an unnamed one cannot
    # be looked up again. Better to fall back than to store something
    # useless that every future claim in this domain will reuse.
    if not name or len(angles) < 3:
        return None
    if name in BY_NAME:
        name = f"{name}-2"

    routine = Routine(
        name=name,
        description=str(payload.get("description", "")).strip(),
        applies_when=str(payload.get("applies_when", "")).strip(),
        angles=angles,
        primary_sources=str(payload.get("primary_sources", "")).strip(),
        weak_sources=str(payload.get("weak_sources", "")).strip(),
        decompose_guidance=str(payload.get("decompose_guidance", "")).strip(),
        query_guidance=str(payload.get("query_guidance", "")).strip(),
        generated=True,
    )
    if conn is not None:
        save(conn, routine)
    return routine


def classify(
    claim: str, *, run_id=None, conn: sqlite3.Connection | None = None
) -> Routine:
    """Pick a routine for this claim, writing a new one if none fits.

    Routines that never route are just prompt templates, so the choice is
    made explicitly. And an unfamiliar domain gets a routine written for it
    rather than being forced through a generic one, which is how the
    agent's skills accumulate instead of staying fixed at three.
    """
    from falsifier import config
    from falsifier.clients import nebius

    known = available(conn)
    options = "\n".join(
        f"- {r.name}: {r.description} Use when {r.applies_when}" for r in known
    )

    chosen: Routine | None = None
    try:
        result = nebius.complete(
            config.NANO,
            CLASSIFY_PROMPT.format(claim=claim, options=options),
            stage="classify",
            no_think=True,
            max_tokens=600,
            run_id=run_id,
            conn=conn,
        )
        word = result.text.strip().lower().strip(".\"' ")
        if "none" not in word:
            for routine in known:
                if routine.name in word:
                    chosen = routine
                    break
    except Exception:  # noqa: BLE001 - a bad classification must not stop a run
        pass

    if chosen is None:
        try:
            chosen = generate(claim, run_id=run_id, conn=conn)
        except Exception:  # noqa: BLE001 - fall back rather than fail the run
            chosen = None

    chosen = chosen or DEFAULT
    if conn is not None:
        conn.execute(
            "UPDATE routines SET times_used = times_used + 1 WHERE name = ?",
            (chosen.name,),
        )
        conn.commit()
    return chosen


def seed(conn: sqlite3.Connection) -> None:
    """Write the three built-in routines into the register."""
    for routine in ALL:
        save(conn, routine)
