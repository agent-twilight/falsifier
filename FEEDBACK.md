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

## 2026-09-27 — Setup

**What I was trying to do:** Scaffold the project and identify the Token
Factory base URL and Nemotron model ids to put in `.env.example`.

**What happened:** Placeholder left blank pending account creation. Noting
here that the AI Studio → Token Factory rename means older docs, blog posts
and code samples circulating online carry a base URL that may no longer
resolve. If that is the case it is worth reporting as documentation feedback.

**Severity:** cosmetic (so far)
