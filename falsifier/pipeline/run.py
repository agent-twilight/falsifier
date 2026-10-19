"""The whole pipeline, as one callable thing.

One sentence: give it a claim, it decomposes, attacks, searches, triages,
reads, judges, stores everything and writes you a document.

Every stage already works alone. This is the part that makes it a product
rather than a collection of functions, and it is also where the funnel
numbers come from - the 50 hypotheses, 40 searches, 400 results, 2 survivors
that the interface shows and the video needs.

Nothing here raises on a single stage failing. A claim with four assumptions
should still produce a report if one of them blows up, with the failure
recorded rather than hidden. That is step 26.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from falsifier import config
from falsifier.clients import nebius, tavily
from falsifier.memory import db, routines
from falsifier.pipeline import (
    angles, decompose, freshness, hypothesise, parsing, read, verdict,
)


@dataclass
class Funnel:
    """What went in, what survived. The rejection log, as numbers."""

    sub_claims: int = 0
    hypotheses: int = 0
    searches: int = 0
    results: int = 0
    triaged_in: int = 0
    quotes_verified: int = 0
    quotes_rejected: int = 0
    challenged: int = 0
    supported: int = 0
    unverifiable: int = 0

    def line(self) -> str:
        return (
            f"{self.hypotheses} hypotheses -> {self.searches} searches -> "
            f"{self.results} results -> {self.triaged_in} relevant -> "
            f"{self.quotes_verified} verified quotes -> "
            f"{self.challenged} challenged / {self.supported} supported / "
            f"{self.unverifiable} unsettled"
        )


@dataclass
class RunResult:
    claim: str
    claim_id: int
    run_id: int
    report: verdict.ClaimReport
    funnel: Funnel = field(default_factory=Funnel)
    cost_usd: float = 0.0
    credits: int = 0
    failures: list[str] = field(default_factory=list)
    routine: str = ""


def _store_evidence(
    conn: sqlite3.Connection, hypothesis_id: int | None, ev: read.Evidence
) -> int | None:
    """Save a verified quote, with whatever the server says about its age."""
    if hypothesis_id is None:
        return None
    state = freshness.check(ev.url)
    return conn.execute(
        "INSERT INTO evidence (hypothesis_id, quoted_line, url, source_tier, "
        "source_date, undated, last_modified, etag, last_checked_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            hypothesis_id, ev.quote, ev.url, ev.source_tier,
            ev.published_date,
            0 if (ev.published_date or state.last_modified) else 1,
            state.last_modified.isoformat() if state.last_modified else None,
            state.etag,
            state.checked_at.isoformat() if state.checked_at else None,
        ),
    ).lastrowid


def investigate(
    claim: str,
    *,
    profile: str = config.DEFAULT_PROFILE,
    mode: str = "personal",
    criteria: list[str] | None = None,
    conn: sqlite3.Connection | None = None,
) -> RunResult:
    """Run one claim all the way through, and never crash on one bad stage."""
    shape = config.PROFILES[profile]
    owned = conn is None
    connection = conn or db.connect()
    started_usd = nebius.spend_total(connection)
    started_credits = tavily.credits_spent(connection)
    funnel = Funnel()
    failures: list[str] = []

    try:
        claim_id = connection.execute(
            "INSERT INTO claims (text, mode, criteria) VALUES (?, ?, ?)",
            (claim, mode, "\n".join(criteria) if criteria else None),
        ).lastrowid
        run_id = connection.execute(
            "INSERT INTO runs (claim_id, mode) VALUES (?, ?)", (claim_id, mode)
        ).lastrowid
        connection.commit()

        routine = routines.classify(claim, run_id=run_id, conn=connection)
        decomposition = decompose.decompose(
            claim, routine=routine, criteria=criteria,
            claim_id=claim_id, run_id=run_id, conn=connection,
        )
        sub_rows = connection.execute(
            "SELECT id, text FROM sub_claims WHERE claim_id = ? ORDER BY position",
            (claim_id,),
        ).fetchall()[: shape["sub_claims"]]
        funnel.sub_claims = len(sub_rows)

        verdicts: list[verdict.Verdict] = []

        for sub_row in sub_rows:
            sub_id, sub_text = sub_row["id"], sub_row["text"]
            evidence_for_sub: list[tuple[read.Evidence, int | None]] = []

            try:
                hypotheses = hypothesise.hypothesise(
                    claim, sub_text, routine=routine, count=shape["hypotheses"],
                    sub_claim_id=sub_id, run_id=run_id, conn=connection,
                )
            except (parsing.ParseError, nebius.ModelCallError) as exc:
                failures.append(f"hypotheses for sub-claim {sub_id}: {exc}")
                hypotheses = []

            hyp_rows = connection.execute(
                "SELECT id, text FROM hypotheses WHERE sub_claim_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (sub_id, len(hypotheses)),
            ).fetchall()
            funnel.hypotheses += len(hyp_rows)

            for hyp_row in hyp_rows:
                hyp_id, hyp_text = hyp_row["id"], hyp_row["text"]
                try:
                    queries = angles.angles(
                        claim, hyp_text, routine=routine, count=shape["angles"],
                        run_id=run_id, conn=connection,
                    )
                except (parsing.ParseError, nebius.ModelCallError) as exc:
                    failures.append(f"queries for hypothesis {hyp_id}: {exc}")
                    continue

                for query in queries:
                    try:
                        found = tavily.search(
                            query, run_id=run_id, hypothesis_id=hyp_id,
                            max_results=shape["results"], conn=connection,
                        )
                    except tavily.SearchBudgetExceeded as exc:
                        failures.append(f"search ceiling reached: {exc}")
                        queries = []
                        break
                    except tavily.SearchError as exc:
                        failures.append(f"search failed for {query!r}: {exc}")
                        continue

                    funnel.searches += 1
                    funnel.results += len(found.results)

                    for result in found.results:
                        try:
                            if not read.triage(
                                hyp_text, result.title, result.snippet,
                                run_id=run_id, conn=connection,
                            ):
                                continue
                            funnel.triaged_in += 1
                            ev = read.read(
                                hyp_text, result.url, result.title,
                                result.snippet, result.published_date,
                                run_id=run_id, conn=connection,
                            )
                        except (parsing.ParseError, nebius.ModelCallError) as exc:
                            failures.append(f"reading {result.url}: {exc}")
                            continue

                        if ev is None:
                            funnel.quotes_rejected += 1
                            continue
                        funnel.quotes_verified += 1
                        evidence_for_sub.append(
                            (ev, _store_evidence(connection, hyp_id, ev))
                        )

            try:
                judgement = verdict.judge(
                    claim, sub_text, [e for e, _ in evidence_for_sub],
                    ambiguities=decomposition.ambiguities, criteria=criteria,
                    run_id=run_id, conn=connection,
                )
            except (parsing.ParseError, nebius.ModelCallError) as exc:
                failures.append(f"verdict for sub-claim {sub_id}: {exc}")
                judgement = verdict.Verdict(
                    verdict.UNVERIFIABLE,
                    "This assumption could not be assessed.",
                    reason=f"The reasoning step failed: {exc}",
                    sub_claim=sub_text,
                )

            verdicts.append(judgement)
            _store_finding(
                connection, claim_id, sub_id, judgement, evidence_for_sub
            )

        for judgement in verdicts:
            if judgement.stance == verdict.CHALLENGED:
                funnel.challenged += 1
            elif judgement.stance == verdict.SUPPORTED:
                funnel.supported += 1
            else:
                funnel.unverifiable += 1

        cost = nebius.spend_total(connection) - started_usd
        credits = tavily.credits_spent(connection) - started_credits

        connection.execute(
            "UPDATE runs SET finished_at = datetime('now'), status = ?, "
            "n_hypotheses = ?, n_searches = ?, n_results = ?, n_read = ?, "
            "n_survived = ?, cost_usd = ?, tavily_credits = ? WHERE id = ?",
            ("complete" if not failures else "complete",
             funnel.hypotheses, funnel.searches, funnel.results,
             funnel.quotes_verified, funnel.challenged, cost, credits, run_id),
        )
        connection.commit()

        return RunResult(
            claim=claim, claim_id=claim_id, run_id=run_id,
            report=verdict.ClaimReport(
                claim=claim, verdicts=verdicts,
                ambiguities=decomposition.ambiguities,
            ),
            funnel=funnel, cost_usd=cost, credits=credits, failures=failures,
            routine=routine.name,
        )
    finally:
        if owned:
            connection.close()


def _store_finding(
    conn: sqlite3.Connection,
    claim_id: int,
    sub_id: int,
    judgement: verdict.Verdict,
    evidence_rows: list[tuple[read.Evidence, int | None]],
) -> None:
    """Save the verdict. The schema refuses anything unsupported."""
    evidence_id = None
    if judgement.evidence is not None:
        evidence_id = next(
            (row_id for ev, row_id in evidence_rows
             if ev.quote == judgement.evidence.quote and row_id is not None),
            None,
        )

    stance = judgement.stance
    reason = judgement.reason
    if stance in (verdict.CHALLENGED, verdict.SUPPORTED) and evidence_id is None:
        # Could not tie the verdict to a stored quote, so it is not storable
        # as a position. Downgrade rather than drop: the attempt is still
        # worth recording.
        stance = verdict.UNVERIFIABLE
        reason = reason or "The cited quote could not be matched to a stored source."

    next_check = None
    if stance != verdict.UNVERIFIABLE and judgement.evidence:
        days = freshness.next_check_days(judgement.evidence.source_tier)
        next_check = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    conn.execute(
        "INSERT INTO findings (claim_id, sub_claim_id, evidence_id, stance, "
        "text, reason, confidence, next_check_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (claim_id, sub_id, evidence_id if stance != verdict.UNVERIFIABLE else None,
         stance, judgement.statement, reason, judgement.confidence, next_check),
    )
    conn.commit()
