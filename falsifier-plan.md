# The Falsifier — Build Plan & Checklist Audit

**Track:** Personal AI · **Deadline:** 30 Oct 2026, 10:30pm IST · **Personal Deadline:** 15 Oct 2026, 10:30pm IST
---

## What it is

You give it something you believe or intend. It hunts for the strongest evidence that you're wrong, and produces a sourced counter-case.

**Why it's hard, and therefore interesting:** search engines are confirmation machines. Ask "is it good to work two years before an MS" and relevance ranking hands you pages arguing yes. Disconfirming evidence isn't just rarer — it's structurally unretrievable unless you first work out what the counter-claim would even look like, then hunt for that instead.

So the agent has to invent the opposition before it can search for it. That's the core IP.

---

## Architecture

### The pipeline, per claim

| # | Stage | Tier | Volume |
|---|---|---|---|
| 1 | Decompose claim into load-bearing sub-claims | Super | ~1 call |
| 2 | Generate ways each sub-claim could be false | Nano | ~50 calls |
| 3 | Generate search angles per hypothesis | Nano | ~10–15 calls |
| 4 | Retrieve | Tavily | ~40 searches |
| 5 | Triage: does this result bear on the hypothesis? | Nano | ~400 calls |
| 6 | Read survivors, grade source, extract the line | Super | ~25 calls |
| 7 | Which objections actually survive? | Ultra | 1–2 calls |
| 8 | Assemble artifact, store, schedule re-checks | — | — |

**Roughly 460 Nano : 26 Super : 2 Ultra per claim.** A naive build makes ~490 calls to the big model. That ratio is your README table and it *is* NVIDIA's commercial argument, demonstrated rather than described.

### Worked example

**Claim:** "Working two years before applying strengthens my Stanford application."

- **Decompose:** (a) the program values work experience, (b) two years is the right length, (c) my specific role counts as relevant, (d) delay carries no cost.
- **Falsify (b):** maybe the admitted cohort is mostly straight-from-undergrad. Maybe two years is below the threshold that counts. Maybe it only helps for professional programs, not research ones.
- **Search angles that actually disconfirm:** admitted-cohort composition on the official program page; class profile PDFs; the program's own FAQ on work experience. *Not* "is work experience good for grad school."
- **Grade:** official class profile beats an admissions-consultant blog every time. Undated pages get flagged.
- **Survive:** two objections hold, one dies for lack of evidence.

### Memory

Four stores. Each has to do work a settings page couldn't.

- **`/claims/`** — every claim, its sub-claims, objections, evidence lines, verdicts, timestamps, current status (live / retracted / superseded)
- **`/situation/`** — the narrow set of facts that determine *which* objections apply to you. Deliberately small.
- **`/skills/`** — falsification routines (below)
- **`/sources/`** — which domains have proved reliable or unreliable, learned over time

### Skills — closing track gap #1

A **falsification routine** is a stored procedure for attacking a *class* of claim:

- *Timeline claims* — decompose into duration, sequencing, and dependency; primary sources are official calendars and published deadlines
- *Eligibility claims* — decompose into each stated criterion; only the issuing body's page counts as primary
- *Cost and funding claims* — decompose into sticker, net, and hidden; primary sources are official fee schedules
- *Demand claims* ("people want X") — decompose into who, how many, willing to pay; beware vendor-funded surveys

Built once, reused on every future claim, refined as it learns which query patterns actually surface disconfirming evidence. This is the track's "reusable skills" bullet satisfied by the mechanism, not bolted on.

### Tasks, not answers — closing track gap #2

Three things it *does* rather than says:

1. **Produces the counter-case artifact** — a written, sourced document with each objection, the exact line it rests on, the link, source tier, date and confidence. The thing you'd otherwise have to assemble yourself.
2. **Extracts claims from your drafts** — point it at an email, a plan, a proposal. It pulls out the load-bearing assertions and works on them without you typing them in.
3. **Re-verifies and retracts** — live objections get re-checked on their own schedule. When one stops holding, it retracts it and tells you. Standing claims decay; the register stays honest.

### Always-on

The loop wakes daily. It re-checks live objections due for review, and stays silent unless something *changed*. Most days: nothing.

The change notification is the interesting one: *"the objection I raised on 6 October no longer holds — the source was updated."* That's an agent correcting itself, on the record.

---

## The interface

Four screens. This is a product, not a script.

1. **Claim register** — everything you've asserted, with status
2. **Counter-case view** — per claim: surviving objections, each with its evidence line, link, source tier, date, confidence
3. **The funnel** — 50 hypotheses → 40 searches → 412 results → 25 read → 2 survived. This is the rejection log and it's your best 30 seconds of video
4. **Source ledger** — what it trusts, what it doesn't, and why

---

## Three rules that must be enforced in code, not in prompts

1. **No objection without a retrieved, quoted line and a live link.** A language model will fabricate a fluent objection to anything. If the evidence field is empty, the objection does not ship.
2. **"I found nothing" is a first-class output.** When 40 angles turn up no disconfirming evidence, say so prominently. That's a genuinely valuable result and a great demo moment. An agent that always finds something is broken.
3. **It attacks claims, never the person.** "This plan assumes X; here's evidence X is false." Never a judgment about you. Anything else and you'll stop opening it by week two.

---

## Checklist coverage — honest audit

### §1 Hard requirements — all achievable
Nothing here is idea-dependent. Demo URL is clean: a stranger types any claim and watches it get falsified live, no personal data required.

### §2 Track bullets

| Bullet | Coverage | Note |
|---|---|---|
| Always-on | **Strong** | Daily re-verification with real silence discipline |
| Private | **Strong** | ZDR + minimum-slice prompts; claims stay local |
| Persistent memory | **Strong** | The claim register is the product |
| Reusable skills | **Moderate** | Falsification routines — needs deliberate building, won't emerge |
| Tools you choose | **Strong** | Tavily, scoped source policy |
| Tasks across workflows | **Moderate** | Artifacts + draft extraction, but it isn't running your day |
| NemoClaw / OpenShell / Hermes | **Weak** | Read-only agent, so the sandbox has thin justification. Optional anyway. |

### §3 Grand-prize signals

| Signal | Coverage |
|---|---|
| Real, measured tiering | **Strongest available** — 460:26:2 is architectural, not decorative |
| Numbers in the README | **Strong** — funnel volumes, cost/claim, latency, naive-baseline comparison |
| Tavily epistemic depth | **Strongest of every idea considered** — must defeat the search engine's confirmation bias, grade source tiers, flag undated pages, surface conflicts |
| Open-infrastructure story | **Moderate** — true but not special to this idea |
| Reference demo Nebius would show | **Strong** — an agent doing high-volume cheap reasoning to produce a small high-value output is exactly their pitch |

### §4 Product quality bar
All achievable. **The risk is "used daily."** It only generates logs if you actually feed it decisions. Mitigation: seed it from your existing written material (journal, plans, drafts) so it has a backlog from day one rather than waiting on you.

### §5 Design principles
Fits unusually well. The funnel *is* the rejection log. "Quote the source line" is rule #1. "Show the pattern, don't name the diagnosis" becomes "show the evidence, don't declare the verdict."

### §6 Privacy
The claim register is personal. ZDR on day one. Send the minimum slice — most claims need three or four situational facts, not your life.

### §7 Video
Strong. Opens with an AI telling its own user their plan is wrong, with sources. Funnel on screen. A real retraction with a real timestamp.

### §8 Prize stacking
Best Tavily case available — genuinely in contention for the $3,000, not decoration.

### Honest total
**Strong on every §3 item that decides the grand prize. Moderate on two §2 bullets that need deliberate work. Weak on the optional NVIDIA agent tooling.**

---

## Timeline

### Days 1–4 (16–19 Sep) — setup, in parallel with nothing else
- Nebius account, **ZDR toggled on**, credits claimed, Tavily key
- One Nemotron call returning text
- Record pricing per tier and compute your budget per claim — credits are finite and this design is call-heavy
- Repo created, MIT licence in place on day one
- Start `FEEDBACK.md` immediately (§8)

### Days 5–20 (20 Sep – 5 Oct) — end-to-end and ugly
Build in this order. Do not optimise anything.
1. Claim in → Super decompose → hypotheses (Nano) → queries (Nano)
2. Tavily retrieval → Nano triage → Super read
3. Ultra assembly → counter-case artifact written to disk
4. Store to claim register
5. Daily loop + one notification channel

**Milestone: by 5 Oct, one real claim of yours goes in and a sourced counter-case comes out.** Ugly is fine. Working is the only requirement.

### Day 20 onward — it runs on your real life, uninterrupted
Feed it live decisions and your existing written backlog. From here the logs accumulate whatever else happens.

### Days 21–38 (6–23 Oct) — make it good
- Tiering measurement and the cost table
- Falsification routines as first-class stored skills
- The four screens
- Failure handling: bad model output, dead links, Tavily timeouts, budget ceiling
- Draft extraction
- Re-verification and retraction

### Days 39–43 (24–28 Oct) — ship
Film, cut, README with numbers, repo cleanup, feedback write-up, demo deployed.

### Day 44 (29 Oct) — submit
One day of slack before the deadline, not zero.

---

## The one rule

End-to-end working by 5 October, then improve. Not: understand everything, then build.
