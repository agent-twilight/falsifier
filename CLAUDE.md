# The Falsifier

Context for Claude Code sessions in this folder. Full detail lives in
[README1.md](README1.md), [falsifier-plan.md](falsifier-plan.md) and
[hackathon-checklist.md](hackathon-checklist.md) — read those before any
significant design work. [STEPS.md](STEPS.md) is the progress tracker.

## How to work with me

These rules apply to every session in this folder.

- The user is new to building applications. Explain everything in plain
  language as you go.
- Work in small steps, one at a time. A step is something that can be verified
  in a few minutes. Never batch several steps together.
- **Before each step:** say what you are about to do, why, and what will exist
  when it is finished. Then wait for the user to say go.
- **After each step:** show what changed, explain any new concept in plain
  language, and run something that proves it works — output, a test, a printed
  result. Never claim done without demonstrating it.
- Then stop and wait. Do not begin the next step unprompted.
- Never write a file the user could not summarise in one sentence. If a file
  is doing something non-obvious, explain it before writing it.
- Commit to git after every step that works, with a clear message.
- When a step is finished, tick it **and strike it through** in [STEPS.md](STEPS.md)
  (`- [x] ~~**12. ...**~~`), so progress is visible at a glance across sessions.
- If the user seems confused, stop and explain rather than pressing on.

## What it is

A personal agent whose single job is to find the strongest available evidence
that the user is wrong. Give it a claim, plan or belief; it decomposes the
claim into its load-bearing parts, invents ways each part could be false,
searches for evidence of each, grades what it finds by source quality, and
returns only the objections that survived — each carrying the exact quoted
line it rests on and a live link. It then re-verifies objections over time and
retracts them when they stop holding.

The hard part: search engines are confirmation machines. The agent has to
invent the opposition before it can search for it. That is the core IP.

Two track requirements are deliberate build items, not side effects of the
pipeline — **reusable skills** (falsification routines per class of claim) and
**tasks not answers** (counter-case artifact, draft extraction, retraction).
They will not emerge on their own. Do not let them get dropped.

The app supports **two modes from the start**: the user's own instance, and a
clean public demo session carrying no personal data. Designed in on day one,
not retrofitted in late October.

**Always-on is a hard track requirement and stays in scope** — daily loop,
deployed, running unattended, silent on quiet days. What was scaled back is
only the *claim of duration* in the README: write what the logs actually show.
Deploy the loop as early as possible. Every earlier day is a day of real logs,
and logs that do not exist cannot be shown to a judge.

## Stack

- **Python 3.13**, FastAPI, SQLite
- **Nebius Token Factory** for inference — OpenAI-compatible API, so the
  `openai` client is used with a custom `base_url`
- **NVIDIA Nemotron** models across three tiers (Nano / Super / Ultra)
- **Tavily** for retrieval

## Environment — read before running anything

Anaconda is installed on this machine and the terminal opens in `(base)`.
**Never `pip install` into conda base.** This project uses a local venv:

```
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn web.main:app --reload
```

Call `.venv\Scripts\python.exe` by path rather than activating. Activation
scripts trip PowerShell's execution policy and interleave badly with conda.

Verify the right interpreter with:
`.venv\Scripts\python.exe -c "import sys; print(sys.prefix)"`
— must print a path ending in `falsifier\.venv`.

## Three rules enforced in code, not in prompts

These are correctness requirements, not style preferences. A language model
will fabricate a fluent objection to anything, so the guardrails have to live
outside the prompt.

1. **No objection ships without a retrieved, quoted line and a live link.**
   Empty evidence field means the objection is dropped, not softened.
2. **"I found nothing" is a first-class output.** When the search angles turn
   up no disconfirming evidence, say so prominently. An agent that always
   finds something is broken.
3. **It attacks claims, never the person.** "This plan assumes X; here is
   evidence X is false." Never a judgment about the user.

## Model tiering — the central technical argument

Per claim, roughly **460 Nano : 26 Super : 2 Ultra**:

| Stage | Tier | Volume |
|---|---|---|
| Decompose claim into sub-claims | Super | ~1 |
| Generate falsification hypotheses | Nano | ~50 |
| Generate search angles | Nano | ~10–15 |
| Retrieve | Tavily | ~40 |
| Triage: does this result bear on the hypothesis? | Nano | ~400 |
| Read survivors, grade source, extract the line | Super | ~25 |
| Which objections actually survive? | Ultra | 1–2 |

**Tier counts, latency and cost must be measured and logged, never estimated.**
The README table comparing this against a naive single-big-model build is a
primary judging differentiator. Instrument from the first call, not in October.

**Every model call goes through a single wrapper function** that logs model,
input tokens, output tokens, latency and computed cost to SQLite. Nothing
calls the client directly. The spend cap lives in that wrapper.

**Cost safety, enforced in code before the first full pipeline run:** a hard
per-run call ceiling and a daily spend cap. One runaway retry loop can end the
project, so the ceiling goes in before the first full run, not after.

**Balances as of 16 Oct 2026 — do not hard-plan around either number:**

- **Token Factory: $29.** Builders Program credits are pending and may roughly
  double this to ~$54. Treat $29 as the number that has to work.
- **Tavily: 1000 credits.** More requested, not granted. At ~40 searches per
  claim that is ~25 full runs on basic search, ~12 on advanced. Confirm which
  rate applies.

Real per-token prices are still unverified. Confirm them from the Token
Factory pricing page and compute actual cost per claim on the first real run,
from logged token counts rather than estimates.

**Tavily credits are the binding constraint, not Nebius credits.** Two rules
follow, both load-bearing:

- **Record once, replay free.** The first real Tavily response for a query is
  saved to disk; every later development run replays from that file. Dev
  iteration must cost zero credits. This also makes debugging sane, because
  the data stops moving underneath you.
- **The public demo serves pre-computed replays by default.** Live runs sit
  behind a hard daily cap, or a single curious visitor drains the balance.

## Privacy

- Zero Data Retention must be ON in the Nebius account (opt-in; the default
  stores prompts).
- Send the **minimum relevant slice** of memory per request, never the whole
  file. Most claims need three or four situational facts.
- The claim register is personal data. `data/` and `*.db` are gitignored and
  stay on this machine.

## Repo status

- GitHub repo is **private during the build**.
- ⚠️ **It must be flipped to Public before 29 Oct 2026.** A private repo on
  submission day is an invalid entry.
- MIT `LICENSE` is in place (hard requirement: licence visible on repo page).
- `README1.md` is the product document. GitHub only renders `README.md`, so
  this needs resolving before submission.

## Timeline

Deadline **30 Oct 2026, 10:30pm IST**. Work is task-driven, not date-driven,
but **the end-to-end pipeline working is the gate before any polish begins** —
no interface work, deployment, Docker, CI or migrations until a claim goes in
and a sourced counter-case comes out.
