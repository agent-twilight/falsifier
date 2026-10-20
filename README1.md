> **Note, 18 October 2026.** This document describes the project's original
> framing, as a tool whose job is to prove you wrong. That framing was
> superseded: the method is still adversarial, but the product is an aide
> that keeps your plans current, and agreeing with you is a legitimate
> result. **[README.md](README.md) is the current description.** This file is
> kept for the design reasoning, which still holds.

# The Falsifier

**Nebius x NVIDIA Global AI Hackathon — Personal AI Track**
Deadline: 30 October 2026, 10:30pm IST

---

# Part 1 — What we're building and why

## The problem

People act on beliefs they never checked.

Not stupid beliefs. Reasonable ones, absorbed from a senior colleague, a forum post, a blog from 2023, or a friend who "went through the same thing." They feel settled. Nobody revisits them. And then a decision gets made on top of one, and the cost only shows up much later.

Three things make this worse than it sounds:

**1. Search engines are confirmation machines.** Type "is it good to work two years before applying to grad school" and relevance ranking hands you pages arguing yes, because those pages match your phrasing. To find the counter-evidence you'd have to already know what the counter-claim looks like, then search for *that* instead. Most people never make that leap, and the ones who do only make it for beliefs they already doubted.

**2. Assistants agree with you.** Every AI product on the market is built to be helpful, which in practice means it takes your framing and helps you execute it. Describe a plan and you get help with the plan. The assumption underneath goes unexamined by design.

**3. The cost is invisible and delayed.** You never find out about the fellowship you were eligible for, the requirement that changed, or the assumption that was false. There is no error message. The feedback loop for a bad belief can be years long, which is exactly why these beliefs survive.

## What exists today, and why it doesn't solve this

| Tool | What it does | Why it doesn't help |
|---|---|---|
| Search engines | Retrieve what you asked for | Confirmation-biased by construction |
| AI assistants | Execute your framing | Challenge inconsistently, from reasoning rather than evidence, depending on how the question was framed. No systematic coverage and no follow-up. |
| Fact-checkers | Verify public claims | Aimed at news, not your personal decisions |
| Advisors / mentors | Genuinely challenge you | Scarce, expensive, and they don't know your specifics |

The gap: **nothing systematically hunts for evidence that you specifically are wrong about something you specifically believe.**

## What the Falsifier is

A personal agent whose single job is to find the strongest available evidence that you're wrong.

You give it a claim, a plan, or a belief. It decomposes it into the parts that actually carry weight, invents dozens of ways each part could be false, hunts for evidence of each, grades what it finds by source quality, and returns only the objections that survived scrutiny — each one carrying the exact line it rests on and a link.

Then it keeps watching. Objections get re-verified over time. When one stops holding, it retracts it and tells you.

**It is not a contrarian.** It attacks claims, never you. And when forty search angles turn up nothing disconfirming, the honest answer — "I tried to find evidence against this and couldn't" — is a first-class output, not a failure.

---

# Part 2 — What it can actually do

### Core capabilities

**Investigate a claim.** The main loop. In → decomposition → falsification hypotheses → targeted search → triage → source grading → surviving objections → written counter-case.

**Extract claims from your writing.** Point it at a draft email, a plan, an application essay, a proposal. It pulls out the load-bearing assertions itself, so you don't have to know what your own assumptions are before using it.

**Grade sources, not just retrieve them.** Every piece of evidence is tagged: primary (the issuing body, official documentation, the changelog), secondary (reputable reporting, peer-reviewed work), or weak (marketing, affiliate content, undated blogs, anecdote). An official page beats a consultant's blog every time, and the agent says which it used.

**Detect staleness and conflict.** Flags undated sources. Flags sources older than the claim's natural half-life. When two sources disagree, surfaces the disagreement rather than silently picking one.

**Maintain a claim register.** Every claim you've ever submitted, its sub-claims, the objections raised, the evidence behind each, and its current status: live, retracted, superseded.

**Re-verify and retract.** Live objections get re-checked on a schedule set by how fast that kind of fact moves. When an objection stops holding, it retracts it. This is the agent correcting itself on the record.

**Run without you.** Daily loop. Silent unless something changed.

**Learn falsification routines.** Reusable procedures for attacking classes of claim — timeline claims, eligibility claims, cost claims, demand claims. Each one stores how to decompose that kind of claim, what counts as a primary source for it, and which query patterns actually surface disconfirming evidence. Built once, reused forever, refined as it runs.

**Show its work.** The funnel is visible: 50 hypotheses generated → 40 searches run → 412 results returned → 25 read in full → 2 objections survived. Including everything it discarded, and why.

### What it deliberately does not do

- **It doesn't tell you what to do.** It supplies evidence; the decision stays yours.
- **It doesn't psychoanalyse you.** It attacks claims, not the person holding them.
- **It doesn't manufacture objections.** No evidence, no objection. Enforced in code.
- **It doesn't nag.** Silence is the default state.

---

## Worked example

**Input:** *"Working two years before applying to Stanford strengthens my application."*

**Decomposition** (what the claim actually rests on):
1. This program values work experience
2. Two years is a meaningful amount
3. My specific role counts as relevant experience
4. Delaying carries no offsetting cost

**Falsification hypotheses for #2** (a sample of ~50 generated):
- The admitted cohort is mostly straight from undergrad
- Two years is below whatever threshold actually counts
- The effect only holds for professional programs, not research ones
- Work experience substitutes for research output rather than adding to it

**Search angles designed to disconfirm:**
- The program's published class profile — cohort composition
- The program's own FAQ on work experience
- Admissions statistics PDFs

Not "is work experience good for grad school." That question returns the answer you already have.

**Grading:** an official class profile outranks an admissions-consultant blog. An undated page gets flagged.

**Output:** two objections survive with primary sources attached, one dies for lack of evidence, and the claim register records all of it with the date.

---

## Is this a gimmick?

Worth answering directly, because an agent that disagrees with you could easily be one.

**It would be a gimmick if:** it generated plausible-sounding objections from the model's own knowledge, always found something to object to, never showed sources, or attacked the person rather than the claim. Each of those is a real failure mode and each is cheap to fall into.

**Three rules, enforced in code rather than in prompts, are what make it a product:**

1. **No objection without a quoted retrieved line and a live link.** A language model will produce a fluent objection to literally anything. If the evidence field is empty, the objection does not ship.
2. **"Found nothing" is a prominent, first-class output.** An agent that always finds something is broken. When forty angles turn up no disconfirming evidence, that's a genuinely valuable result and it's displayed as one.
3. **Claims, never the person.** "This plan assumes X, and here's evidence X is false." Never a judgment about you.

**The test of usefulness:** would you rather have known? If the agent tells you a requirement changed, a deadline moved, a funding route you assumed existed doesn't, or a cohort statistic contradicts your plan — that's information you'd have paid for. If it tells you your plan is "risky" with no source, it's noise, and rule 1 stops it shipping.

---

# Part 3 — Requirement-by-requirement audit

Every line of the master checklist, and honestly how the Falsifier meets it.

## §1 Hard requirements

**Runs on Nebius Token Factory** — every model call goes through Token Factory via the OpenAI-compatible client. It's the only inference path in the system.

**Uses an NVIDIA open source model** — three Nemotron variants, each doing a distinct job. Not one model with a compliance label on it.

**Working demo URL** — a stranger types any claim and watches it get falsified live. No personal data required, so the public instance and your instance are the same product. Pre-computed example claims replay from cache to keep it fast and cheap; live runs are rate-limited.

**Demo video under 3 minutes** — covered in §7.

**Public repo, licence, README** — MIT committed on day one. README2 is the setup guide. This file is the explanation.

**Project description** — this document.

**Written feedback** — `FEEDBACK.md`, started day one and written as things break, not reconstructed at the end.

**Pre-existing work explanation** — not applicable; started from zero during the submission period.

## §2 Personal AI track bullets

| Bullet | Coverage | How |
|---|---|---|
| **Always-on** | Strong | Daily loop re-verifies live objections on schedules set by each claim's half-life. Runs whether or not you open anything. Silent unless something changed. |
| **Private** | Strong | ZDR enabled. Only the minimum relevant situational facts go out with each request — most claims need three or four, not your life story. Claim register stays local. |
| **Persistent memory** | Strong | The claim register *is* the product. It holds your assertions, the objections raised, the evidence, the verdicts and the timestamps. A settings page could not replace it. |
| **Reusable skills** | Moderate | Falsification routines: stored, reusable procedures for attacking classes of claim. **Needs deliberate building — this will not emerge on its own.** |
| **Tools and information you choose** | Strong | Tavily, under an explicit source policy you control — which domains count as primary, which are excluded. |
| **Tasks across daily workflows** | Moderate | It produces the counter-case artifact, extracts claims from your drafts, and maintains the register. But it is not running your calendar or your inbox. Honest assessment: partial. |
| **NemoClaw / OpenShell / Hermes** | Weak | A read-only agent has thin justification for a sandbox. These are optional, and forcing them in would cost build time for little gain. Revisit only if there's slack in week four. |

## §3 Grand-prize signals

**Model tiering that's real and measured** — *strongest available.* The tiering isn't a feature bolted on; it's the only reason the architecture is possible.

| Tier | Job | Calls per claim |
|---|---|---|
| Nano | Generate hypotheses, generate search angles, triage results | ~460 |
| Super | Decompose the claim, read and grade survivors | ~26 |
| Ultra | Decide which objections actually survive | ~2 |

Thousands of cheap calls to produce three sentences worth reading. That's a task whose *shape* changes when volume stops being the constraint — which is precisely NVIDIA's commercial argument for open models, demonstrated instead of described.

**Numbers in the README** — every model call goes through a single logging wrapper recording model, input tokens, output tokens, latency and computed cost to SQLite. Produces: per-tier volume, cost per claim, latency distribution, and the naive baseline (routing all ~490 calls to Ultra costs roughly 15× more for identical work).

**Tavily doing epistemic work** — *strongest case of any idea considered.* The agent has to defeat the search engine's own confirmation bias: invent the counter-claim first, then construct queries that would surface it. Then grade source tiers, flag undated pages, and surface conflicts rather than resolving them silently. This is grounding and fact-checking, not retrieval.

**Credible open-infrastructure story** — open weights, no lock-in, and a real self-hosting exit. Nano is small enough to run on your own hardware, which makes "you could leave" a true statement rather than a slogan. Stated precisely in the video: what leaves the machine, what doesn't, what ZDR covers.

**A demo Nebius would show a customer** — an agent doing high-volume cheap reasoning to produce a small, high-value output is their enterprise pitch in miniature.

## §4 Product quality bar

**Clone and run in under 10 minutes** — README2, `.env.example`, one `pip install`, SQLite (no database to stand up), one command to start.

**Fails gracefully** — model returns malformed output, Tavily times out, a source 404s, the budget ceiling hits. Each degrades with a visible reason rather than crashing. The funnel shows what failed.

**A real interface** — four views: claim register, counter-case detail, the funnel, the source ledger.

**Runs unattended for weeks** — hosted from day 20, not started for the demo.

**Used daily by a real person, with logs** — the main risk, addressed below.

**Scoped narrow enough to finish** — one pipeline, one interface, four screens, 40 days.

## §5 Design principles

**Memory does work a settings page couldn't** — the register holds reasoning and evidence with provenance, not preferences.

**Show the pattern, don't name the diagnosis** — becomes *show the evidence, don't declare the verdict.* It surfaces what it found; you decide what it means.

**Silence is the hard skill** — the daily loop notifies only on change. Most days, nothing.

**Rejection log** — the funnel is the rejection log, built into the product rather than added for the video.

**Minimum relevant slice** — the situational store is deliberately small and queried selectively.

**Quote the source line** — rule 1, enforced in code.

**Same product for you and for judges** — no personal data is needed to demonstrate it.

## §6 Privacy

- ZDR on before any real data goes in
- Only relevant situational facts leave the machine; the register stays local
- Identifiers stripped where the reasoning doesn't need them
- Credentials scoped to Tavily and Token Factory, nothing else
- The register is encrypted at rest

## §7 Video

Opens with an AI telling its own user their plan is wrong, with sources. Shows the funnel. Shows a real retraction with a real date. Audio explicitly covers Token Factory and Nemotron. Real timestamps throughout — nothing staged.

## §8 Prize stacking

- **Best Use of Tavily** — genuinely in contention; the epistemic work is the product, not decoration
- **Most Valuable Feedback** — `FEEDBACK.md` written as things break
- **City Winner Award** — no Indian city on the participating list, but the rules now say attendance isn't required and that submissions associated with a participating city are considered. Ambiguous. Worth one email to the hackathon manager.

## §9 Timeline

Spine-first build. Each step ends with something printed, so any evening can end with visible progress. End-to-end and ugly by day 20, then it runs on real claims while the polish happens around it.

---

# Part 4 — Known weaknesses

Written down so they get designed against rather than discovered in late October.

**Supply risk — the biggest one.** The product only generates logs if it's fed real claims. Some weeks there won't be a decision worth investigating. *Mitigation:* seed it on day one from writing that already exists — journal entries, plans, drafts — so there's a backlog rather than a wait.

**Fabrication.** The single most likely way this becomes a gimmick. Rule 1 is the defence and it must live in code, not in a prompt.

**Absence of evidence.** Not finding disconfirming evidence doesn't mean the claim is true. The output must say "no disconfirming evidence found," never "verified."

**Domain limits.** It works where public documentary evidence exists. It cannot falsify claims about your own feelings, private situations, or anything unwritten. Scope honestly rather than pretending otherwise.

**Cost blowout.** ~490 calls per claim. A retry bug eats $50 overnight. Hard per-run call ceiling and daily spend cap before the first full pipeline run.

**Tavily credits, not Nebius credits, are the binding constraint.** ~40 searches per claim. Find the actual allocation before designing around that number.

**Two track bullets are only partially met** — reusable skills and doing-tasks-not-answers. Both are build items, not side effects. If they're skipped under time pressure, the submission loses points on explicit track requirements.
