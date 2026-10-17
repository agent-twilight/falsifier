"""Prices, limits and budget caps, in one place.

Everything the spend cap needs in order to refuse a call *before* it is made.

Prices are US dollars per 1,000,000 tokens, recorded 16 Oct 2026. They are a
starting point, not gospel: verify against the Nebius pricing page, and let
measured cost from the `calls` table overrule them once real runs exist.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "falsifier.db"
FIXTURES_DIR = DATA_DIR / "fixtures"


# --------------------------------------------------------------------------
# Credentials. Read here so nothing else in the codebase touches os.getenv.
# Never log or print these.
# --------------------------------------------------------------------------
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "")
NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


@dataclass(frozen=True)
class Tier:
    """One model tier: which model, what it costs, how much it can read."""

    name: str
    model_id: str
    input_per_1m: float
    output_per_1m: float
    context_tokens: int

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        """Dollar cost of a single call with these token counts."""
        return (
            input_tokens * self.input_per_1m + output_tokens * self.output_per_1m
        ) / 1_000_000


NANO = Tier("nano", os.getenv("NEMOTRON_NANO", ""), 0.06, 0.24, 32_000)
SUPER = Tier("super", os.getenv("NEMOTRON_SUPER", ""), 0.30, 0.90, 256_000)
ULTRA = Tier("ultra", os.getenv("NEMOTRON_ULTRA", ""), 1.00, 3.00, 1_000_000)

TIERS = {tier.name: tier for tier in (NANO, SUPER, ULTRA)}

# Ultra cache reads bill at the full input price, so caching saves nothing
# at that tier. Do not assume a discount when estimating.
ULTRA_CACHE_READ_PER_1M = 1.00


# --------------------------------------------------------------------------
# Tavily. The binding constraint: ~25 runs a month, versus hundreds of claims
# affordable on Nebius. Protect searches, not tokens.
# --------------------------------------------------------------------------
TAVILY_CREDITS_BASIC = 1
TAVILY_CREDITS_ADVANCED = 2
TAVILY_MONTHLY_CREDITS = 1000
TAVILY_RATE_LIMIT_PER_MIN = 100

# Pinned deliberately. Tavily's auto_parameters can promote a search to
# advanced depth on its own, silently doubling the credit cost.
TAVILY_SEARCH_DEPTH = "basic"


# --------------------------------------------------------------------------
# Budget ceilings, enforced by the call wrapper in step 9.
# These are circuit breakers against a runaway retry loop, not spending plans.
# --------------------------------------------------------------------------
TOTAL_BUDGET_USD = 29.00
DAILY_SPEND_CAP_USD = 2.00
MAX_CALLS_PER_RUN = 600  # expected ~490
MAX_SEARCHES_PER_RUN = 45  # expected ~40

# Nano holds only 32K tokens and does the ~400 triage calls over retrieved
# page content, so it is where an overflow would actually bite. Truncate
# before the text reaches it.
TRIAGE_MAX_CHARS = 6_000


# --------------------------------------------------------------------------
# Reasoning behaviour. Measured 17 Oct 2026, see FEEDBACK.md.
#
# All three Nemotron 3 tiers are reasoning models. They emit a separate
# `reasoning` field, and those thinking tokens are billed as output. If
# max_tokens is too small the reasoning consumes the whole budget and
# `content` comes back as an EMPTY STRING with finish_reason "stop" - no
# error, no warning. That is a silent-failure trap, so never call these
# models with a tight token budget.
# --------------------------------------------------------------------------
MAX_TOKENS_FLOOR = 600

# "/no_think" as a system message suppresses most reasoning. The documented
# Nemotron 2 phrasing "detailed thinking off" does NOT work on Nemotron 3.
# Do not use reasoning_effort="none": it returns empty content silently.
NO_THINK_SYSTEM_PROMPT = "/no_think"

# Measured mean output tokens for a triage call: 190 with reasoning on,
# 108 with /no_think. A 43% saving across ~400 calls per claim. Answers
# matched on a 3-sample check, which is suggestive, not proof - validate on
# a larger sample before trusting /no_think for all triage.
TRIAGE_OUTPUT_TOKENS_THINKING = 190
TRIAGE_OUTPUT_TOKENS_NO_THINK = 108


def missing_credentials() -> list[str]:
    """Names of required settings that are still empty. Values never shown."""
    required = {
        "NEBIUS_API_KEY": NEBIUS_API_KEY,
        "NEBIUS_BASE_URL": NEBIUS_BASE_URL,
        "TAVILY_API_KEY": TAVILY_API_KEY,
        "NEMOTRON_NANO": NANO.model_id,
        "NEMOTRON_SUPER": SUPER.model_id,
        "NEMOTRON_ULTRA": ULTRA.model_id,
    }
    return [name for name, value in required.items() if not value]


def estimated_claim_cost() -> float:
    """Rough dollar cost of one full pipeline run, from the planned call mix.

    Superseded by measured cost as soon as the calls table has real rows.
    """
    # Output token counts revised upward on 17 Oct after measuring real
    # reasoning overhead. Triage is measured; the rest are still estimates.
    plan = [
        (NANO, 400, 1_000, 110),  # triage (measured, /no_think)
        (NANO, 50, 500, 400),  # falsification hypotheses
        (NANO, 12, 400, 300),  # search angles
        (SUPER, 25, 3_000, 500),  # read, grade, extract the line
        (SUPER, 1, 600, 800),  # decompose
        (ULTRA, 2, 8_000, 1_500),  # which objections survive
    ]
    return sum(tier.cost(tin, tout) * calls for tier, calls, tin, tout in plan)


if __name__ == "__main__":
    print("Config loaded from", PROJECT_ROOT / ".env")
    print()
    for tier in TIERS.values():
        print(
            f"  {tier.name:<6} {tier.model_id or '(not set)':<42}"
            f" ${tier.input_per_1m}/{tier.output_per_1m} per 1M"
            f"  ctx {tier.context_tokens:,}"
        )
    print()
    per_claim = estimated_claim_cost()
    print(f"  estimated cost per claim   ${per_claim:.4f}")
    print(f"  claims affordable on ${TOTAL_BUDGET_USD:.0f}   ~{TOTAL_BUDGET_USD / per_claim:.0f}")
    print(
        f"  claims affordable on Tavily ~{TAVILY_MONTHLY_CREDITS // MAX_SEARCHES_PER_RUN}"
        f" per month  <-- the real limit"
    )
    print()
    missing = missing_credentials()
    print("  missing settings:", ", ".join(missing) if missing else "none")
