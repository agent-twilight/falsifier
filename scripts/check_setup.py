"""Smoke test: can we actually reach Token Factory, and are the model ids right?

Run it with:
    .venv\\Scripts\\python.exe scripts\\check_setup.py

Sends one tiny prompt to each tier. Costs a fraction of a cent. Each tier is
tried independently so one bad model id does not hide the others.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI  # noqa: E402

from falsifier import config  # noqa: E402

PROMPT = "Reply with exactly: OK"


def check_tier(client: OpenAI, tier: config.Tier) -> tuple[bool, float]:
    """Call one tier. Returns (succeeded, dollars spent)."""
    print(f"  {tier.name:<6} {tier.model_id}")
    started = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=tier.model_id,
            messages=[{"role": "user", "content": PROMPT}],
            max_tokens=16,
            temperature=0,
        )
    except Exception as exc:  # noqa: BLE001 - we want the reason, whatever it is
        print(f"         FAILED  {type(exc).__name__}: {exc}\n")
        return False, 0.0

    elapsed = time.monotonic() - started
    usage = response.usage
    cost = tier.cost(usage.prompt_tokens, usage.completion_tokens)
    reply = (response.choices[0].message.content or "").strip().replace("\n", " ")

    print(f"         OK      {elapsed:.2f}s")
    print(f"         reply   {reply[:60]!r}")
    print(
        f"         tokens  {usage.prompt_tokens} in / "
        f"{usage.completion_tokens} out   cost ${cost:.6f}\n"
    )
    return True, cost


def main() -> int:
    missing = config.missing_credentials()
    if missing:
        print("Missing settings in .env:", ", ".join(missing))
        return 1

    print(f"Token Factory at {config.NEBIUS_BASE_URL}\n")
    client = OpenAI(api_key=config.NEBIUS_API_KEY, base_url=config.NEBIUS_BASE_URL)

    results = {tier.name: check_tier(client, tier) for tier in config.TIERS.values()}

    total = sum(cost for _, cost in results.values())
    working = [name for name, (ok, _) in results.items() if ok]
    broken = [name for name, (ok, _) in results.items() if not ok]

    print(f"working: {', '.join(working) if working else 'none'}")
    if broken:
        print(f"BROKEN : {', '.join(broken)}")
    print(f"spent  : ${total:.6f}")
    return 0 if not broken else 1


if __name__ == "__main__":
    raise SystemExit(main())
