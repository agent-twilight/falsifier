"""Getting structured data out of model replies.

One sentence: models return prose with JSON somewhere inside it, and this
digs the JSON out without crashing when they wrap it in markdown or add a
sentence of preamble.

Reasoning models are especially prone to this, since the habit of explaining
themselves carries into the answer.
"""

from __future__ import annotations

import json
import re
from typing import Any


class ParseError(ValueError):
    """The reply did not contain usable JSON."""


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Find and parse the first JSON array or object in a model reply."""
    if not text or not text.strip():
        raise ParseError("empty reply")

    candidates = [match.group(1) for match in _FENCE.finditer(text)]
    candidates.append(text)

    for candidate in candidates:
        candidate = candidate.strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        # Fall back to the outermost bracketed span.
        for opener, closer in (("[", "]"), ("{", "}")):
            start, end = candidate.find(opener), candidate.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(candidate[start : end + 1])
                except json.JSONDecodeError:
                    continue

    raise ParseError(f"no JSON found in reply: {text[:200]!r}")


def as_list_of_strings(value: Any, key: str | None = None) -> list[str]:
    """Normalise a parsed reply into a clean list of non-empty strings.

    Accepts a bare list, a list of dicts (taking `key`), or a dict wrapping
    a list, because models produce all three for the same prompt.
    """
    if isinstance(value, dict):
        for candidate in value.values():
            if isinstance(candidate, list):
                value = candidate
                break
    if not isinstance(value, list):
        raise ParseError(f"expected a list, got {type(value).__name__}")

    out = []
    for item in value:
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            if key and key in item:
                text = item[key]
            else:
                text = next(
                    (v for v in item.values() if isinstance(v, str) and v.strip()),
                    "",
                )
        else:
            continue
        text = str(text).strip()
        if text:
            out.append(text)
    return out
