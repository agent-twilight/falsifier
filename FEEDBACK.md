# Feedback log — Nebius Token Factory, Nemotron, Tavily

Running log of what broke, with reproductions, written as it happens.
Targets the hackathon's **Most Valuable Feedback** prize ($100 × 10 winners).

Two rules that make this worth anything:

1. **Write the entry the day it happens.** Reconstructed-from-memory feedback
   is vague, and vague feedback wins nothing. Five minutes now beats an hour
   in late October.
2. **Always include a reproduction.** "The API was slow" is noise. "Nano tier,
   40 concurrent requests, p95 latency 8s, here is the script" is useful.

---

> ## ⚠️ Standing reminder: flip the GitHub repo to **Public** before 29 Oct 2026
>
> The repo is private during the build. A private repo on submission day is an
> invalid entry, regardless of how good the project is. Also set a phone alarm
> for 25 Oct — do not rely on remembering this.

---

## Template — copy this block for each entry

```
## YYYY-MM-DD — <service: Token Factory / Nemotron / Tavily / AI Cloud>

**What I was trying to do:**

**What happened:**

**What I expected:**

**Reproduction:**

**Workaround (if any):**

**Severity:** blocker / annoying / cosmetic
```

---

## Entries

## 2026-10-17 — Nemotron 3 on Token Factory: reasoning tokens and silent empty output

**What I was trying to do:** First smoke test of all three Nemotron 3 tiers
through the OpenAI-compatible endpoint, with `max_tokens=16` for a one-word
reply.

**What happened:** Nano and Super returned `content=""` — an empty string —
with `finish_reason="stop"`. No error, no warning. Ultra returned what looked
like leaked chain-of-thought in the content field.

The cause: all three tiers are reasoning models. They populate a separate
`reasoning` field, and those thinking tokens are billed as output tokens
against `max_tokens`. With a small budget the reasoning consumes it entirely
and the answer never gets generated.

**What I expected:** Either a non-empty answer, or `finish_reason="length"`
to signal truncation. An empty string with `finish_reason="stop"` is
indistinguishable from the model legitimately choosing to say nothing, which
makes this fail silently in production.

**Reproduction:**

```python
client.chat.completions.create(
    model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    messages=[{"role": "user", "content": "Reply with exactly: OK"}],
    max_tokens=16, temperature=0)
# -> choices[0].message.content == ""   finish_reason == "stop"
# -> choices[0].message.reasoning is populated
```

**Severity:** annoying — but a likely source of hard-to-diagnose bugs for
anyone porting existing OpenAI code, where `max_tokens=16` for a yes/no
answer is an ordinary thing to write.

---

## 2026-10-17 — `reasoning_effort="none"` returns empty output instead of an error

**What I was trying to do:** Suppress reasoning on Nano to cut output tokens
on high-volume triage calls.

**What happened:** `reasoning_effort="none"` returned 2 completion tokens and
empty content. It neither disabled reasoning nor rejected the parameter.
`reasoning_effort="low"` worked but still produced 421 output tokens.

**What I expected:** Either the parameter is supported and suppresses
reasoning, or it is rejected with a clear error. Silently returning nothing is
the worst of the three.

**Workaround:** a system message of `/no_think` works, and cut mean triage
output from 190 to 108 tokens. Note that the Nemotron 2 phrasing
`"detailed thinking off"` has **no effect** on Nemotron 3 — worth a
documentation note, since existing Nemotron code and tutorials use it.

**Reproduction:**

```python
# empty content, 2 tokens:
client.chat.completions.create(model=NANO, messages=[...],
                               max_tokens=500, reasoning_effort="none")
# works, content == "YES":
client.chat.completions.create(model=NANO, max_tokens=500, messages=[
    {"role": "system", "content": "/no_think"},
    {"role": "user", "content": "..."}])
```

**Severity:** annoying — silent empty output on an unsupported parameter
value.

---

## 2026-09-27 — Setup

**What I was trying to do:** Scaffold the project and identify the Token
Factory base URL and Nemotron model ids to put in `.env.example`.

**What happened:** Placeholder left blank pending account creation. Noting
here that the AI Studio → Token Factory rename means older docs, blog posts
and code samples circulating online carry a base URL that may no longer
resolve. If that is the case it is worth reporting as documentation feedback.

**Severity:** cosmetic (so far)
