"""Cost and tiering numbers, computed from logged calls rather than estimated.

One sentence: queries the `calls` and `searches` tables to produce the per-tier
volume, cost and latency table that goes in the README.

The point of this file is that nothing in it is a guess. Where real logged
calls exist for a pipeline stage, measured token counts are used. Where they
do not yet exist, the planned figure from config is used and is **labelled
as planned**, so the two can never be confused in the output.

This is also what answers the naive-baseline question honestly: what would
the same workload cost if every call went to Ultra instead? That multiple is
a headline claim, so it is computed from the same measured tokens rather
than asserted.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from falsifier import config
from falsifier.memory import db

# The planned call mix per claim. Used only where measurements are absent.
PLANNED_STAGES: list[tuple[str, config.Tier, int, int, int]] = [
    ("decompose", config.SUPER, 1, 600, 800),
    ("hypothesise", config.NANO, 50, 500, 400),
    ("query-angles", config.NANO, 12, 400, 300),
    ("triage", config.NANO, 400, 1_000, 190),
    ("read", config.SUPER, 25, 3_000, 500),
    ("survive", config.ULTRA, 2, 8_000, 1_500),
]


@dataclass
class StageCost:
    stage: str
    tier: config.Tier
    calls: int
    input_tokens: int
    output_tokens: int
    measured: bool

    @property
    def cost(self) -> float:
        return self.tier.cost(self.input_tokens, self.output_tokens)

    @property
    def ultra_cost(self) -> float:
        """What this stage would cost routed entirely to Ultra."""
        return config.ULTRA.cost(self.input_tokens, self.output_tokens)


def measured_stages(conn: sqlite3.Connection) -> dict[str, tuple[int, float, float, float]]:
    """Per stage: call count, mean input tokens, mean output tokens, mean latency.

    Smoke tests are excluded; they are not pipeline work.
    """
    rows = conn.execute(
        "SELECT stage, tier, count(*) AS n, "
        "       avg(input_tokens) AS ti, avg(output_tokens) AS to_, "
        "       avg(latency_ms) AS ms "
        "FROM calls WHERE ok = 1 AND stage NOT IN ('smoke-test', 'cap-demo') "
        "GROUP BY stage, tier"
    ).fetchall()
    return {r["stage"]: (r["n"], r["ti"], r["to_"], r["ms"]) for r in rows}


def per_claim(conn: sqlite3.Connection | None = None) -> list[StageCost]:
    """Cost of one full claim, stage by stage, measured where possible."""
    owned = conn is None
    connection = conn or db.connect()
    try:
        measured = measured_stages(connection)
        stages = []
        for name, tier, planned_calls, planned_in, planned_out in PLANNED_STAGES:
            if name in measured:
                _, mean_in, mean_out, _ = measured[name]
                stages.append(
                    StageCost(name, tier, planned_calls,
                              int(mean_in * planned_calls),
                              int(mean_out * planned_calls), measured=True)
                )
            else:
                stages.append(
                    StageCost(name, tier, planned_calls,
                              planned_in * planned_calls,
                              planned_out * planned_calls, measured=False)
                )
        return stages
    finally:
        if owned:
            connection.close()


def actual_spend(conn: sqlite3.Connection | None = None) -> dict[str, float | int]:
    """What has really been spent so far, across every logged call."""
    owned = conn is None
    connection = conn or db.connect()
    try:
        row = connection.execute(
            "SELECT count(*) AS calls, coalesce(sum(cost_usd), 0) AS usd, "
            "coalesce(sum(input_tokens), 0) AS ti, "
            "coalesce(sum(output_tokens), 0) AS to_, "
            "coalesce(sum(CASE WHEN ok = 0 THEN 1 ELSE 0 END), 0) AS failed "
            "FROM calls"
        ).fetchone()
        credits = connection.execute(
            "SELECT coalesce(sum(credits), 0) FROM searches WHERE from_cache = 0"
        ).fetchone()[0]
        replays = connection.execute(
            "SELECT count(*) FROM searches WHERE from_cache = 1"
        ).fetchone()[0]
        return {
            "calls": row["calls"], "usd": row["usd"], "failed": row["failed"],
            "input_tokens": row["ti"], "output_tokens": row["to_"],
            "tavily_credits": credits, "tavily_replays": replays,
        }
    finally:
        if owned:
            connection.close()


def render(conn: sqlite3.Connection | None = None) -> str:
    """The table, as text. Becomes the README table in step 40."""
    stages = per_claim(conn)
    lines = [
        "Cost of one claim, by pipeline stage",
        "",
        f"{'stage':<13} {'tier':<6} {'calls':>6} {'in tok':>9} {'out tok':>8} "
        f"{'cost':>9}  source",
        "-" * 72,
    ]
    for s in stages:
        lines.append(
            f"{s.stage:<13} {s.tier.name:<6} {s.calls:>6} {s.input_tokens:>9,} "
            f"{s.output_tokens:>8,} {'$%.4f' % s.cost:>9}  "
            f"{'measured' if s.measured else 'planned'}"
        )

    total = sum(s.cost for s in stages)
    ultra_total = sum(s.ultra_cost for s in stages)
    calls = sum(s.calls for s in stages)
    lines += [
        "-" * 72,
        f"{'TOTAL':<13} {'':<6} {calls:>6} "
        f"{sum(s.input_tokens for s in stages):>9,} "
        f"{sum(s.output_tokens for s in stages):>8,} {'$%.4f' % total:>9}",
        "",
        f"All-Ultra baseline, same tokens: ${ultra_total:.4f} "
        f"({ultra_total / total:.1f}x)",
        "",
    ]

    by_tier: dict[str, tuple[int, float]] = {}
    for s in stages:
        n, c = by_tier.get(s.tier.name, (0, 0.0))
        by_tier[s.tier.name] = (n + s.calls, c + s.cost)
    ratio = ":".join(str(by_tier.get(t, (0, 0))[0]) for t in ("nano", "super", "ultra"))
    lines.append(f"Calls per claim, nano:super:ultra = {ratio}")
    for tier_name, (n, c) in by_tier.items():
        lines.append(
            f"  {tier_name:<6} {n:>4} calls  ${c:.4f}  "
            f"{c / total * 100:>5.1f}% of cost"
        )

    spend = actual_spend(conn)
    lines += [
        "",
        "Actually spent so far",
        f"  model calls      {spend['calls']} ({spend['failed']} failed)",
        f"  tokens           {spend['input_tokens']:,} in / {spend['output_tokens']:,} out",
        f"  nebius           ${spend['usd']:.4f} of ${config.TOTAL_BUDGET_USD:.2f}",
        f"  tavily credits   {spend['tavily_credits']} of "
        f"{config.TAVILY_MONTHLY_CREDITS} ({spend['tavily_replays']} free replays)",
        "",
        f"Claims affordable: ~{int(config.TOTAL_BUDGET_USD / total)} on Nebius, "
        f"~{config.TAVILY_MONTHLY_CREDITS // config.MAX_SEARCHES_PER_RUN} on Tavily",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(render())
