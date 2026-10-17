"""Smoke test: can we reach Token Factory, and are the model ids right?

Run it with:
    .venv\\Scripts\\python.exe scripts\\check_setup.py

Sends one tiny prompt to each tier through the normal call wrapper, so the
calls are logged like any other and the spend figures stay honest. Costs a
fraction of a cent. Each tier is tried independently, so one bad model id
does not hide the others.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Model output contains unicode (curly quotes, non-breaking hyphens).
# Windows consoles default to cp1252 and raise UnicodeEncodeError on it.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from falsifier import config  # noqa: E402
from falsifier.clients import nebius  # noqa: E402
from falsifier.memory import db  # noqa: E402

PROMPT = "Reply with exactly: OK"


def check_tier(tier: config.Tier) -> tuple[bool, float]:
    """Call one tier. Returns (succeeded, dollars spent)."""
    print(f"  {tier.name:<6} {tier.model_id}")
    try:
        result = nebius.complete(tier, PROMPT, stage="smoke-test", no_think=True)
    except nebius.ModelCallError as exc:
        print(f"         FAILED  {exc}\n")
        return False, 0.0

    reply = result.text.replace("\n", " ")
    print(f"         OK      {result.latency_ms} ms")
    print(f"         reply   {reply[:60]!r}")
    print(
        f"         tokens  {result.input_tokens} in / {result.output_tokens} out"
        f"   cost ${result.cost_usd:.6f}\n"
    )
    return True, result.cost_usd


def main() -> int:
    missing = config.missing_credentials()
    if missing:
        print("Missing settings in .env:", ", ".join(missing))
        return 1

    db.init_db()
    print(f"Token Factory at {config.NEBIUS_BASE_URL}\n")

    results = {tier.name: check_tier(tier) for tier in config.TIERS.values()}

    working = [name for name, (ok, _) in results.items() if ok]
    broken = [name for name, (ok, _) in results.items() if not ok]

    print(f"working    : {', '.join(working) if working else 'none'}")
    if broken:
        print(f"BROKEN     : {', '.join(broken)}")
    print(f"this run   : ${sum(cost for _, cost in results.values()):.6f}")
    print(f"today      : ${nebius.spend_today():.6f}")
    print(f"all time   : ${nebius.spend_total():.4f} of ${config.TOTAL_BUDGET_USD:.0f}")
    return 0 if not broken else 1


if __name__ == "__main__":
    raise SystemExit(main())
