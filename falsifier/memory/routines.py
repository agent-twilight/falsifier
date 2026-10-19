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
    query_guidance=(
        "Search for the measurement, not the opinion. Use words like data, "
        "statistics, study, outcomes, profile, report, percentage. Seek the "
        "figures themselves rather than articles describing them."
    ),
)

ALL = (EXISTENCE, REQUIREMENT, EFFECT)
BY_NAME = {r.name: r for r in ALL}
DEFAULT = EFFECT

CLASSIFY_PROMPT = """Which kind of claim is this?

Claim: "{claim}"

{options}

Pick the single best fit. Answer with the name only, in lower case."""


def classify(claim: str, *, run_id=None, conn=None) -> Routine:
    """Choose the routine for this claim.

    Two routines that never route are just two prompt templates, so the
    choice is made explicitly and recorded.
    """
    from falsifier import config
    from falsifier.clients import nebius

    options = "\n".join(
        f"- {r.name}: {r.description} Use when {r.applies_when}." for r in ALL
    )
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
        for name, routine in BY_NAME.items():
            if name in word:
                return routine
    except Exception:  # noqa: BLE001 - a bad classification must not stop a run
        pass
    return DEFAULT


def seed(conn: sqlite3.Connection) -> None:
    """Record the routines in the register, so the agent can show its work."""
    conn.executemany(
        "INSERT OR REPLACE INTO sources (domain, tier, note) VALUES (?, ?, ?)",
        [(f"routine:{r.name}", "primary",
          f"{r.description} Primary sources: {r.primary_sources}") for r in ALL],
    )
    conn.commit()
