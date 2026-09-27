# Nebius x NVIDIA Global AI Hackathon — Master Checklist

**Track:** Personal AI
**Deadline:** 30 October 2026, 10:30pm IST
**Personal Deadline:** 15 October 2026, 10:30pm IST

---

## 1. Hard requirements

Miss any of these and the submission is invalid, regardless of quality.

- [ ] Runs on **Nebius Token Factory** or **Nebius AI Cloud**
- [ ] Uses **at least one NVIDIA open source model** (Nemotron)
- [ ] **Working demo URL** — a hosted app or test build a judge can actually use
- [ ] **Demo video**, 3 minutes or less, public on YouTube, with audio
  - Audio must cover how you used Token Factory and the NVIDIA model
- [ ] **Public code repository** (GitHub / GitLab / Bitbucket)
  - [ ] Open source licence (Apache 2.0, MIT or MPL 2.0) visible at the top of the repo page
  - [ ] README with setup instructions and how to run it
  - [ ] README highlights where Nemotron was used, where Token Factory helped, and any other Nebius services
- [ ] **Project description**: what you built, why, and how it works
- [ ] **Track selected**: Personal AI
- [ ] **Written feedback** on Token Factory, AI Cloud and any NVIDIA tools used
- [ ] If any part of the project predates the submission period, a written explanation of what changed during it

---

## 2. What the Personal AI track explicitly asks for

Their words, turned into a spec. Aim to hit all of these, with one or two of them deep.

- [ ] **Always-on** — runs without you opening anything
- [ ] **Private** — your data stays under your control
- [ ] **Persistent memory** — carries state across sessions
- [ ] **Reusable skills** — procedures it can repeat, not just facts
- [ ] **Tools and information you choose** — scoped, deliberate access
- [ ] **Tasks across daily workflows** — it does things, not just answers
- [ ] Suggested tooling (optional but rewarded): **NemoClaw**, **OpenShell**, **Hermes Agent**, **Nebius Serverless**

---

## 3. What they want to see but haven't written down

This is inference, not stated policy. It's where the grand prize is decided.

- [ ] **Model tiering that's real and measured** — Nano for constant cheap decisions, Super for the middle, Ultra only for rare hard reasoning. This is NVIDIA's entire commercial argument for open models: competitive quality at a fraction of the cost.
- [ ] **Numbers in the README** — volume at each tier, cost per day, latency, and what the same workload would have cost on a single big model. Almost nobody submits an eval. This is the cheapest differentiator available.
- [ ] **Tavily doing epistemic work** — deciding when it doesn't know, forming its own queries, preferring primary sources, noticing when two sources disagree, flagging undated content. Not a single decorative `search()` call. ($3,000, one winner, thin field.)
- [ ] **A credible open-infrastructure story** — open weights, no lock-in, a real self-hosting exit. Stated precisely, not as a slogan.
- [ ] **Something a Nebius engineer would want to show a customer** — the reference demo they can point at.

---

## 4. Product quality bar

The Design criterion asks for a complete product, not a proof of concept. That means:

- [ ] A stranger can clone the repo and run it in **under 10 minutes** from the README
- [ ] **Fails gracefully** — model returns garbage, network drops, source unreachable. Degrades, doesn't crash.
- [ ] **A real interface**, not a terminal print loop
- [ ] **Runs unattended for weeks**, not started for the demo
- [ ] **Used daily by a real person** (you) for the whole build window, with logs to prove it
- [ ] **Scoped narrow enough to be finished.** Narrow and complete beats broad and half-built under this rubric.

---

## 5. Design principles

Agreed during planning. These are the ones easy to violate under time pressure.

- [ ] **Memory must do work a settings page couldn't.** A static profile is a form, not memory.
- [ ] **Show the pattern, don't name the diagnosis.** Surface evidence in the user's own words with timestamps; leave conclusions to them.
- [ ] **Silence is the hard skill.** Every notification spends goodwill. Most days it should say nothing.
- [ ] **Keep a rejection log** — everything considered and discarded, with reasons. Trust surface and best 30 seconds of video.
- [ ] **Send the minimum relevant slice**, not the whole memory file, on every request.
- [ ] **Quote the source line** behind every claim, with a link, so a wrong answer takes five seconds to dismiss.
- [ ] **Your instance and the public demo instance are the same product.** Design this on day one, not in late October.

---

## 6. Privacy setup

- [ ] **Turn on Zero Data Retention** on the Nebius account profile page — day one, before any real data goes in. It is opt-in; the default stores prompts for speculative decoding.
- [ ] Decide what's sent to the hosted model vs handled locally
- [ ] Strip names and identifiers from outbound prompts where reasoning doesn't need them
- [ ] Encrypt the memory file at rest; it's the densest description of you that exists
- [ ] Scope credentials to the minimum the agent actually needs

---

## 7. Video checklist

The video carries more weight than it should, and it's the piece most entrants neglect.

- [ ] Under 3 minutes, public on YouTube
- [ ] Audio covers Token Factory and Nemotron usage explicitly
- [ ] Shows the product running, not slides about the product
- [ ] Shows the **rejection log** — what it chose not to say
- [ ] Shows a moment where it was **wrong**, and what happened next
- [ ] Shows real timestamps from real use, not a staged session
- [ ] Shot and edited properly — this is a genuine advantage of yours, use it

---

## 8. Prize stacking

- [ ] **Best Use of Tavily** — $3,000, one winner, far thinner field than the main prizes. Requires genuine depth, not a bolt-on.
- [ ] **Most Valuable Feedback** — $100 × 10 winners. Keep a running log of what broke, with reproductions, from day one. Near-free if you write as you go.
- [ ] **City Winner Award** — no Indian city on the participating list, but the rules now say attendance isn't required and that submissions associated with a participating city are considered. Ambiguous. Worth one email to the hackathon manager.

---

## 9. Timeline

- [ ] **Days 1–5:** account created, ZDR on, credits claimed, a Nemotron call returning text, idea locked
- [ ] **Days 6–20:** end-to-end and ugly. Memory → reasoning → Tavily → action → notification. Working badly is the goal; working is not.
- [ ] **Day 20 onward:** it runs daily on your real life, uninterrupted, generating logs
- [ ] **Days 21–38:** make it good. Tiering, measurements, interface, failure handling.
- [ ] **Days 39–43:** film, cut, README, licence, repo cleanup
- [ ] **Day 44:** submit. Four days early, not at the deadline.

**The one rule:** end-to-end working by day 20, then improve. Not: understand everything, then build.

---

## Decided: the Falsifier

You give it something you believe or intend. It hunts for the strongest evidence that you're wrong, and produces a sourced counter-case. Full specification in [README1.md](README1.md) and [falsifier-plan.md](falsifier-plan.md); build order in [STEPS.md](STEPS.md).

Killed along the way, with reasons worth remembering:

- **Finance agent** — can't grade the output, affiliate-driven sources, can't demo real money
- **Eligibility agent** — profile is a form not a memory, too few real hits in six weeks
- **Assumption ledger** — assumptions are invisible to the person holding them, so capture fails
- **Craft model** — retention data isn't public for other channels, and view counts at small scale carry no signal

