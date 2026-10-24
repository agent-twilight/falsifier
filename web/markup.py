"""The small subset of markdown the agent actually emits.

One sentence: escape everything, then allow back only bold, italic, links,
quotes and bullets.

A full markdown library would be a dependency for five marks. More
importantly, escaping first means nothing a model writes — or a stranger
types into the public demo — can inject markup, which a permissive parser
would happily let through.
"""

from __future__ import annotations

import html
import re

_QUOTE = re.compile(r"^&gt; ?(.*)$", re.M)
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)")
_LINK = re.compile(r"\[(.+?)\]\((https?://[^)\s]+)\)")
_BULLET = re.compile(r"^- (.*)$", re.M)
_LIST = re.compile(r"(?:<li>.*?</li>\n?)+", re.S)


def render(text: str) -> str:
    out = html.escape(text or "")
    out = _QUOTE.sub(r"<blockquote>\1</blockquote>", out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _ITALIC.sub(r"<em>\1</em>", out)
    out = _LINK.sub(r'<a href="\2" rel="noopener">\1</a>', out)
    out = _BULLET.sub(r"<li>\1</li>", out)
    out = _LIST.sub(lambda m: "<ul>" + m.group(0) + "</ul>", out)

    blocks = []
    for chunk in re.split(r"\n{2,}", out):
        chunk = chunk.strip()
        if not chunk:
            continue
        blocks.append(
            chunk if chunk.startswith("<")
            else "<p>" + chunk.replace("\n", "<br>") + "</p>"
        )
    return "".join(blocks)
