# The Falsifier

**Keeps your plans honest against a world that moves.**

You planned a hundred days of revision. Then the exam board postponed the
date, and nobody told you. Your whole plan is now built on something that is
no longer true.

Tell the Falsifier what you are planning or what you believe. It checks
whether that still holds up against how things are today, shows you the
evidence either way, and then keeps watching. When something outside your
control changes in a way that affects your plan, it tells you — unprompted,
on Telegram, with the source.

It is not a reminder app. It never tells you things you already know. "Study
chemistry today" is your own plan read back at you. "The exam date moved" is
information you could not have had.

**Try it: [falsifier.onrender.com](https://falsifier.onrender.com)** — type a
claim of your own and watch it work. It runs for real against live sources,
takes a minute or two, and shows every search it ran and every result it
threw away. Two worked examples are there already.

> On a free host it sleeps after fifteen minutes idle, so the first load may
> take about fifty seconds.

Built for the **Nebius x NVIDIA Global AI Hackathon**, Personal AI track.

---

## What it actually does

Give it a claim. It:

1. Works out **who is authoritative** on the subject — for a JEE claim, that
   the National Testing Agency decides, not a coaching blog — and verifies
   those domains resolve before trusting them.
2. Breaks the claim into the **assumptions it rests on**, and says which
   terms are too vague to check.
3. Invents **ways each assumption could be false**, before searching
   anything. This is the core of it: a search engine returns what you asked
   for, so asking "is my plan fine?" returns reassurance. You have to work
   out what the counter-evidence would look like first, then hunt for that.
4. **Searches for the counter-case**, grades every source by who published
   it, and flags anything undated.
5. Returns one of three honest answers, all cited:
   - **still true** — it tried to disprove this and could not
   - **no longer true** — with the exact line that contradicts it
   - **couldn't be checked** — and precisely why, including what you would
     need to supply
6. **Keeps watching.** Every cited source is re-checked daily, free. Once a
   week it searches again for developments that did not exist before. When a
   quoted line disappears from the page it rested on, the finding is
   **withdrawn** with the date and reason, and you get a message.

### A real example from the register

Claim: *"A bachelor's degree is required to apply to the Stanford MS in
Computer Science."*

Verdict: **no longer true as worded**, 90% confident, citing Stanford's own
admissions page:

> Applicants must hold, **or expect to hold before enrollment at Stanford**, a
> Bachelor's degree from a U.S. college or University accredited by a
> regional accrediting association.

Required *before enrollment*, not *to apply*. A final-year undergraduate can
apply. That distinction is the kind of thing that changes what you do.

---

## Why the architecture looks like this

Three model tiers, because the work genuinely has three difficulties.

| Stage | Tier | Calls per claim |
|---|---|---|
| Decompose the claim | Nemotron Super | 1 |
| Invent ways it could be false | Nemotron Nano | 50 |
| Write search queries | Nemotron Nano | 12 |
| Retrieve | Tavily | ~40 |
| Triage: does this result bear on it? | Nemotron Nano | 400 |
| Read survivors, grade source, extract the line | Nemotron Super | 25 |
| Weigh everything and decide | Nemotron Ultra | 2 |

**462 Nano : 26 Super : 2 Ultra.** Thousands of cheap decisions to produce
three sentences worth reading. That shape is only affordable because open
models make volume cheap — and it is the whole argument for them.

### The numbers, measured not estimated

Every model call goes through one wrapper that logs model, input tokens,
output tokens, latency and computed cost to SQLite. The table below is a
query over that log. Nothing in it is a guess.

```
stage         tier    calls    in tok  out tok      cost
decompose     super       1       336    1,318   $0.0013
hypothesise   nano       50    27,410   49,314   $0.0135
query-angles  nano       12     4,536    8,032   $0.0022
triage        nano      400   195,766  134,394   $0.0440
read          super      25    14,647   23,778   $0.0258
survive       ultra       2     1,947    2,201   $0.0086
------------------------------------------------------
TOTAL                   490   244,642  219,037   $0.0953

All-Ultra baseline, identical tokens:          $0.9018  (9.5x)
```

**$0.095 per claim.** Routing the same 490 calls to Ultra instead would cost
**9.5 times more** for identical work.

That multiple is computed from logged tokens, holding token counts fixed and
swapping only the model. Early estimates suggested ~20x; the measured figure
is 9.5x, and the measured figure is what is published here. An inflated
number is worse than a modest true one, because a judge can recompute it.

Nano is **94% of the calls and 63% of the cost**. Ultra is 0.4% of the calls
and 9% of the cost. Observed latency: 1.9s median for a Nano triage call,
8.6s for a Super read.

Across all development: **370 real calls, $0.17 spent, 2.2% failed** (and
failures are logged as calls, so per-tier volume is not quietly inflated).

### Where Nebius Token Factory and Nemotron are used

Every single inference call in this project goes through Token Factory via
its OpenAI-compatible endpoint. There is no other inference path. All three
Nemotron tiers do distinct work — this is not one model with a compliance
label on it.

Two findings worth reporting, both written up in
[FEEDBACK.md](FEEDBACK.md) with reproductions:

- All three Nemotron 3 tiers are **reasoning models**, and thinking tokens
  bill against `max_tokens`. A small budget means the reasoning consumes it
  and `content` comes back as an **empty string with
  `finish_reason="stop"`** — no error. That is indistinguishable from the
  model choosing to say nothing. The wrapper now refuses any call below a
  token floor.
- `reasoning_effort="none"` returns empty output rather than an error.
  A `/no_think` system message works instead, and cut triage output from
  190 to 108 tokens. The Nemotron 2 phrasing `"detailed thinking off"` has
  no effect on Nemotron 3.

---

## The rules that keep it honest

These are enforced in **code and in the database schema**, not in prompts. A
language model will produce a fluent objection to anything, so the guardrails
have to live somewhere a prompt cannot reach.

**1. No verdict without a quote that is really there.** When the model
extracts a supporting line, the code checks that line appears
character-for-character in the retrieved page, after normalising whitespace
and smart quotes. If it does not, the evidence is discarded. On real runs
**roughly a third of attempted quotes get thrown away** — which is why this
is a string comparison rather than an instruction.

**2. A verdict either cites a source or explains why it cannot.** The schema
enforces it:

```sql
CHECK (
    (stance IN ('challenges','supports') AND evidence_id IS NOT NULL)
    OR
    (stance = 'unverifiable' AND evidence_id IS NULL
     AND reason IS NOT NULL AND trim(reason) <> '')
)
```

There is no third option where it merely asserts something. A conclusion the
model reaches without pointing at a retrieved line is downgraded to
"couldn't be checked", never silently kept.

**3. A source can only speak as loudly as it deserves.** Confidence is capped
by source quality: a government or university page can reach full confidence,
a news site 70%, a forum post 35%. Below 40% it refuses to take a side and
names the weak source instead. Grading a source and then ignoring the grade
is worse than not grading it.

**4. It cannot claim a fact is current.** Nothing can. It reports what the
page said when it looked, and what the server says about when the page last
changed. Both are checkable.

---

## Running it

Needs Python 3.13, a Nebius Token Factory key, and a Tavily key.

```bash
git clone https://github.com/agent-twilight/falsifier
cd falsifier

python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt         # macOS/Linux

cp .env.example .env        # then fill in your keys
.venv/Scripts/python.exe -m falsifier.memory.db      # create the database
.venv/Scripts/python.exe scripts/check_setup.py      # verify the keys work
```

`check_setup.py` calls all three tiers and prints what each cost. It should
finish in a few seconds for well under a cent.

**The website:**

```bash
.venv/Scripts/python.exe -m uvicorn web.main:app --reload
# then open http://127.0.0.1:8000
```

**Check a claim from the command line:**

```bash
.venv/Scripts/python.exe -c "from falsifier.pipeline import run; from falsifier import artifact; print(artifact.write(run.investigate('your claim here')))"
```

**The daily watch:**

```bash
.venv/Scripts/python.exe -m falsifier.monitor
```

Most days it prints `Nothing changed. Said nothing.` That is the intended
outcome. On Windows, `scripts/run_monitor.cmd` is what Task Scheduler runs.

**Develop without spending search credits.** Every Tavily response is saved
to disk the first time. Set `FALSIFIER_OFFLINE=1` and the whole pipeline
replays from those files with no network and no credits — a missing fixture
is a loud error rather than a silent spend.

**Tests:**

```bash
.venv/Scripts/python.exe -m pytest tests -q      # 150 tests, ~20 seconds
```

They need no network and cost nothing.

---

## Privacy

Your claims are the densest description of you that exists, so:

- Zero Data Retention is enabled on the Nebius account.
- The register is a local SQLite file. `data/` is gitignored and never
  leaves the machine.
- The public demo runs the same code against a **separate database built by
  `scripts/build_demo_db.py`**, which copies only rows marked `mode='demo'`
  and refuses to write the file if anything else gets in. In demo mode a
  personal claim returns 404 even if its id is guessed.
- Nothing a demo visitor types is kept. The container forgets on restart.

---

## What it does not do

Stated plainly, because a tool that oversells itself is the problem it is
meant to solve.

- **It cannot prove a universal negative.** Asked whether a competitor
  exists, the best it can honestly say is "I looked in the obvious places and
  found nothing." It says exactly that rather than "the gap is real."
- **It only works where public documentary evidence exists.** It cannot check
  claims about your feelings, your private situation, or anything unwritten.
- **Re-checking a known page cannot find news that appeared elsewhere.** That
  needs a fresh search, which costs credits, so it runs weekly rather than
  daily. Within a week, something new may exist that it has not seen.
- **It has been running unattended since 19 October.** One scheduled run was
  missed on 20 October because the laptop was asleep; a logon trigger now
  covers that. The log in `logs/monitor.log` is the real record, and it is
  short.

---

## Layout

```
falsifier/
  clients/     nebius.py — the only door to a model, with the spend cap
               tavily.py — retrieval, cache and offline replay
  pipeline/    authority, decompose, hypothesise, angles, read, verdict,
               freshness, run
  memory/      db.py — schema, routines.py — reusable falsification routines
  monitor.py   the daily watch and the weekly hunt
  report.py    the cost table, from logged calls
web/           FastAPI app and templates
scripts/       setup check, demo database builder, Windows task scripts
tests/         150 tests
```

[DEPLOY.md](DEPLOY.md) covers putting the demo online.
[FEEDBACK.md](FEEDBACK.md) is the running log of what broke.
[STEPS.md](STEPS.md) is the build tracker.

MIT licensed.
