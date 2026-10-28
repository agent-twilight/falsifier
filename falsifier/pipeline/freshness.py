"""How old is this, and has it changed since we looked?

One sentence: ask the page itself when it last changed, remember a
fingerprint, and on re-check ask the server "anything new?" in a way that
costs almost nothing.

The honest position, stated plainly because it shapes everything here:

**The agent cannot know that a fact is current.** Nothing can. What it can
know, and state without hedging, is:

1. what the page said at the exact moment it looked  (always true)
2. when the server says the page last changed        (Last-Modified)
3. whether it has changed since                      (ETag, then the quote)

So the agent never claims "this is up to date". It says "as of 18 Oct the
page said X, and the server reports the page last changed on 14 Oct" - both
checkable - and then watches for change rather than inferring freshness.

Why this is cheap: a conditional request sends the stored ETag and the
server replies 304 Not Modified with no body. No Tavily credit, no model
call, almost no bandwidth. Re-verifying a hundred sources daily costs
effectively nothing, which is what makes the always-on loop affordable
against 22 Tavily runs a month.

Two different jobs, and only the first is cheap:

- RE-VERIFY an existing source: did our quote survive? Free, done here.
- RE-SEARCH for new developments: has something appeared that did not exist
  before? Costs Tavily credits, so it runs on a schedule, not daily.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

USER_AGENT = "Falsifier/0.1 (personal research agent; re-verification)"
TIMEOUT = 25


@dataclass(frozen=True)
class PageState:
    """What the server says about a page right now."""

    url: str
    status: int
    last_modified: datetime | None = None
    etag: str | None = None
    checked_at: datetime = None  # type: ignore[assignment]
    unchanged: bool = False
    error: str | None = None

    @property
    def reachable(self) -> bool:
        # 206 is a ranged GET, used when a server refuses HEAD.
        return self.error is None and self.status in (200, 206)

    @property
    def gone(self) -> bool:
        """The source has disappeared, which invalidates anything built on it."""
        return self.status in (404, 410)

    @property
    def age_days(self) -> float | None:
        """Days since the page last changed, per the server."""
        if not self.last_modified:
            return None
        now = self.checked_at or datetime.now(timezone.utc)
        return (now - self.last_modified).total_seconds() / 86400

    def describe(self) -> str:
        """A line a person can read, that does not overclaim."""
        if self.error:
            return f"could not check ({self.error})"
        if self.gone:
            return "the page is gone (404)"
        if self.last_modified:
            age = self.age_days or 0
            return (
                f"page last changed {self.last_modified:%d %b %Y} "
                f"({age:.0f} days ago), per the server"
            )
        return "the server does not say when this page last changed"


def _parse_http_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def check(url: str, *, known_etag: str | None = None) -> PageState:
    """Ask the server about a page, as cheaply as it will allow.

    With a known ETag this is a conditional request: a 304 reply means
    definitively unchanged, with no body transferred.
    """
    now = datetime.now(timezone.utc)
    headers = {"User-Agent": USER_AGENT}
    if known_etag:
        headers["If-None-Match"] = known_etag

    try:
        response = requests.head(
            url, headers=headers, timeout=TIMEOUT, allow_redirects=True
        )
        # Plenty of servers refuse HEAD: 405 Method Not Allowed, or 403, or
        # a 5xx from a framework that never wired it up. Treating that as
        # "could not check" means a source is never re-verified at all, so
        # fall back to a ranged GET, which every server answers.
        if response.status_code in (403, 405, 501) or response.status_code >= 500:
            response = requests.get(
                url,
                headers={**headers, "Range": "bytes=0-2047"},
                timeout=TIMEOUT,
                allow_redirects=True,
                stream=True,
            )
            response.close()
    except requests.RequestException as exc:
        return PageState(url, 0, checked_at=now, error=type(exc).__name__)

    lowered = {k.lower(): v for k, v in response.headers.items()}
    return PageState(
        url=url,
        status=response.status_code,
        last_modified=_parse_http_date(lowered.get("last-modified")),
        etag=lowered.get("etag") or known_etag,
        checked_at=now,
        unchanged=response.status_code == 304,
    )


def fingerprint(text: str) -> str:
    """A stable hash of retrieved text, for detecting substantive change."""
    normalised = " ".join(text.split()).lower()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:32]


# Formats whose text we can actually read. Anything else is fetched, but
# reported as unreadable rather than silently treated as empty.
READABLE_TYPES = ("text/html", "text/plain", "application/xhtml")


def fetch_text(url: str) -> tuple[str | None, PageState]:
    """Download a page's text, for checking whether a quote survives.

    Returns (None, state) when the document cannot be read as text - a PDF,
    an image, an office file. The caller must treat that as "could not
    check", never as "the quote is gone".
    """
    now = datetime.now(timezone.utc)
    try:
        response = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
        )
    except requests.RequestException as exc:
        return None, PageState(url, 0, checked_at=now, error=type(exc).__name__)

    lowered = {k.lower(): v for k, v in response.headers.items()}
    state = PageState(
        url=url,
        status=response.status_code,
        last_modified=_parse_http_date(lowered.get("last-modified")),
        etag=lowered.get("etag"),
        checked_at=now,
    )
    if response.status_code != 200:
        return None, state

    content_type = (lowered.get("content-type") or "").lower()
    if content_type and not any(t in content_type for t in READABLE_TYPES):
        return None, PageState(
            url=state.url, status=state.status,
            last_modified=state.last_modified, etag=state.etag,
            checked_at=state.checked_at,
            error=f"unreadable format: {content_type.split(';')[0]}",
        )

    # Strip tags crudely. Good enough to ask "is this sentence still here?",
    # which is all we need; it never has to render.
    import re

    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", response.text,
                  flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode every entity, not the four I thought of. Hand-picking them
    # left things like "&middot;" in quoted text, which looks like
    # gibberish to a reader and would be quoted verbatim in a message.
    import html as html_module

    text = html_module.unescape(text)
    # Block-level tags became nothing, so sentences from separate
    # paragraphs ran together. Put the boundaries back before collapsing.
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text, state


# How often to re-check, by how fast that kind of fact actually moves.
# Admissions criteria change between cycles; news changes hourly.
# Shortened 23 Oct. The first numbers were guesses, and far too cautious:
# a re-check costs nothing, because an unchanged page answers 304 with no
# body transferred. Waiting a fortnight buys no saving and lets a change
# sit undiscovered for a fortnight.
HALF_LIVES_DAYS = {
    "primary": 3,
    "secondary": 2,
    "weak": 7,
}


def next_check_days(source_tier: str, state: PageState | None = None) -> int:
    """How long until this is worth looking at again.

    A page that changed recently is checked sooner: churn predicts churn.
    """
    base = HALF_LIVES_DAYS.get(source_tier, 14)
    if state and state.age_days is not None and state.age_days < 30:
        return max(1, base // 2)
    return base
