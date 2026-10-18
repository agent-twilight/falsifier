"""The written answer, as a document you can read away from the app.

One sentence: turns a finished run into a markdown file that leads with the
verdict, shows every quote and link, and states plainly what it could not
settle.

Three rules it follows, which are really the product's manners:

- The headline is the honest answer, including "this held up".
- Nothing is asserted without the quote underneath it.
- What it could not establish gets its own section, near the top, not a
  footnote. An unanswered question is more useful to you than a manufactured
  doubt.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from falsifier import config
from falsifier.pipeline import verdict as verdict_mod


def _source_line(ev) -> list[str]:
    """Quote, link, and an honest note about age."""
    if ev is None:
        return []
    age = "the source does not say when it was last updated"
    if getattr(ev, "published_date", None):
        age = f"published {ev.published_date}"
    return [
        "",
        f"> {ev.quote.strip()}",
        "",
        f"— [{ev.url}]({ev.url}) · **{ev.source_tier}** source · {age}",
    ]


def render(result) -> str:
    """Build the document for one completed run."""
    report = result.report
    now = datetime.now(timezone.utc)
    lines = [
        f"# {report.claim}",
        "",
        f"**{report.headline}**",
        "",
        f"Checked {now:%d %B %Y}. "
        f"{result.funnel.searches} searches, "
        f"{result.funnel.results} results read, "
        f"{result.funnel.quotes_verified} quotes verified against their source.",
        "",
    ]

    if report.ambiguities:
        lines += [
            "## What I need from you",
            "",
            "These were not specified, so parts of the answer may not apply "
            "to your situation:",
            "",
        ]
        lines += [f"- {a}" for a in report.ambiguities]
        lines.append("")

    if report.challenged:
        lines += ["## Where the claim runs into trouble", ""]
        for v in report.challenged:
            lines += [f"### {v.statement}", "", f"*On the assumption:* {v.sub_claim}"]
            lines += _source_line(v.evidence)
            lines += ["", f"Confidence: {v.confidence:.0%}", ""]

    if report.supported:
        lines += ["## Where the claim held up", ""]
        for v in report.supported:
            lines += [f"### {v.statement}", "", f"*On the assumption:* {v.sub_claim}"]
            lines += _source_line(v.evidence)
            lines += ["", f"Confidence: {v.confidence:.0%}", ""]

    if report.unverifiable:
        lines += ["## What could not be settled", ""]
        for v in report.unverifiable:
            lines += [
                f"### {v.sub_claim}",
                "",
                v.statement,
                "",
                f"**Why:** {v.reason or 'the sources retrieved did not settle it.'}",
                "",
            ]

    if not report.verdicts:
        lines += [
            "## Nothing was found",
            "",
            "No evidence was retrieved that bore on this claim either way. "
            "That is not the same as the claim being true.",
            "",
        ]

    lines += [
        "---",
        "",
        "## How this was produced",
        "",
        f"`{result.funnel.line()}`",
        "",
        f"- {result.funnel.quotes_rejected} candidate quotes were discarded "
        "because they could not be found word-for-word in the page they were "
        "attributed to.",
        f"- Cost: ${result.cost_usd:.4f} across the model tiers, "
        f"{result.credits} search credits.",
        "",
        "Every quote above was checked against the page it came from. A claim "
        "with no quote is reported as unsettled, never as a conclusion.",
    ]

    if result.failures:
        lines += ["", "### Problems during this run", ""]
        lines += [f"- {f}" for f in result.failures]

    return "\n".join(lines) + "\n"


def write(result, directory: Path | None = None) -> Path:
    """Save the document and return where it went."""
    target = Path(directory) if directory else config.DATA_DIR / "artifacts"
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = target / f"claim-{result.claim_id:04d}-{stamp}.md"
    path.write_text(render(result), encoding="utf-8")
    return path
