# Build steps

The whole project in small numbered steps, in build order. One line for what
each step does, one line for how we know it worked. Tick them off as we go —
this is the progress tracker across sessions.

A step is something verifiable in a few minutes. If a step turns out to be
bigger than that, split it rather than pushing through.

**Revised 16 Oct 2026** for the 14 days remaining. Two structural changes from
the original plan: Tavily fixtures come before the pipeline (step 12), and the
daily loop is deployed immediately after the pipeline gate rather than last,
because every earlier day is a day of real logs.

**The gate:** steps 1–27 must all be done before anything in Phase 4.
End-to-end working comes before polish.

| Phase | Target |
|---|---|
| 0–1 Setup and plumbing | 16–17 Oct |
| 2 Pipeline spine → **gate** | 18–21 Oct |
| 3 Loop deployed, **logs start** | 22–23 Oct |
| 4–5 Interface and skills | 24–26 Oct |
| 6 Measure and ship | 27–28 Oct |
| Submit | 29 Oct |

---

## Phase 0 — Setup

- [x] ~~**1. Git repo, licence, scaffolding, pushed to private GitHub repo.**~~
  *Done when:* `git log` shows commits, `git check-ignore -v .env` prints a rule, and `.env` is absent from `git ls-tree -r origin/main`.
- [ ] **2. Virtual environment and dependencies.** An isolated Python for this
  project, separate from Anaconda base.
  *Done when:* `.venv\Scripts\python.exe -c "import sys, fastapi; print(sys.prefix)"` prints a path ending in `falsifier\.venv`.
- [x] ~~**3. Keys, base URL and the three Nemotron model ids in `.env`.**~~
  *Done when:* all six values are filled and `.env` is still gitignored.
- [ ] **4. Confirm Zero Data Retention is ON** in the Nebius account. Opt-in;
  the default stores prompts. Must be on before any real claim goes through.
  *Done when:* the toggle shows enabled on the profile page.
- [ ] **5. Record per-token prices per tier, and the Tavily credit rate.**
  Basic and advanced searches bill differently; the rate decides whether 1000
  credits is ~25 runs or ~12.
  *Done when:* both are written into a config file the spend cap can read.

## Phase 1 — Plumbing

- [ ] **6. One Nemotron call that returns text.** The "is any of this real"
  test, and the first check of whether those model ids are correct.
  *Done when:* running one script prints a model reply in the terminal.
- [ ] **7. SQLite database and schema.** Tables for calls, claims, sub-claims,
  hypotheses, evidence, objections, sources.
  *Done when:* the file exists in `data/` and the table list prints.
- [ ] **8. The call wrapper.** A single function every model call goes through,
  logging model, input tokens, output tokens, latency and computed cost.
  *Done when:* one call through the wrapper produces one row with all fields filled.
- [ ] **9. Spend cap and per-run call ceiling inside the wrapper.** $29 against
  ~490 calls per claim; one retry bug could end the project.
  *Done when:* a deliberate over-limit test is refused with a clear error and no call is made.
- [ ] **10. Cost per claim, computed from real logged token counts.**
  *Done when:* a printed estimate for one full run exists and is affordable against $29.
- [ ] **11. One Tavily search returning results.**
  *Done when:* a script prints titles and URLs for one query.
- [ ] **12. Record-and-replay fixtures.** Save every real Tavily response to
  disk; replay from file in development. Credits are the binding constraint,
  so dev iteration must cost zero.
  *Done when:* the pipeline can run start to finish with the network off.
- [ ] **13. Query cache.** Never re-search a query already answered, even in
  live mode.
  *Done when:* the same query twice makes one network call.

## Phase 2 — Pipeline spine

One claim in, one sourced counter-case out. Built against replayed fixtures,
so iteration is free. Ugly is fine here; working is the only requirement.

- [ ] **14. Decompose a claim into load-bearing sub-claims** (Super).
  *Done when:* a typed claim prints 3–5 sub-claims that are genuinely what it rests on.
- [ ] **15. Generate falsification hypotheses per sub-claim** (Nano, ~50).
  *Done when:* they are ways the sub-claim could be *false*, not restatements of it.
- [ ] **16. Generate search angles per hypothesis** (Nano).
  *Done when:* the queries would surface disconfirming evidence, not the original claim.
- [ ] **17. Retrieve for each angle** (Tavily).
  *Done when:* results come back for every angle and are stored against their hypothesis.
- [ ] **18. Triage each result** (Nano, ~400). Does this bear on the hypothesis?
  *Done when:* survivors are a small fraction of results and the rejects look right on inspection.
- [ ] **19. Read survivors, grade the source, extract the exact line** (Super).
  *Done when:* each survivor has a quoted line, a live link, a source tier and a date or undated flag.
- [ ] **20. Enforce rule 1 in code.** No quoted line and live link, no objection.
  *Done when:* a fabricated objection with an empty evidence field is dropped automatically, proven by a test.
- [ ] **21. Decide which objections actually survive** (Ultra).
  *Done when:* some objections are rejected with a stated reason, not all passed through.
- [ ] **22. "Found nothing" as a first-class output.**
  *Done when:* a claim with no disconfirming evidence produces a prominent "found nothing" result, never a weak invented objection.
- [ ] **23. Write the counter-case artifact to disk.**
  *Done when:* a readable document exists with each objection, its line, link, tier, date and confidence.
- [ ] **24. Store everything to the claim register.**
  *Done when:* the run survives a restart and can be read back from SQLite.
- [ ] **25. Record the funnel counts per run.** Hypotheses → searches →
  results → read → survived.
  *Done when:* the five numbers print at the end of a run and are stored.
- [ ] **26. Graceful failure on four paths.** Malformed model output, Tavily
  timeout, dead link, budget ceiling hit.
  *Done when:* each is simulated and the run degrades with a visible reason instead of crashing.
- [ ] **27. GATE — one real claim of yours, end to end.**
  *Done when:* you type a belief you actually hold and read a sourced counter-case you did not already know.

## Phase 3 — Running unattended

Brought forward deliberately. Always-on is a hard track requirement, and the
logs only exist for the days the loop has actually been running.

- [ ] **28. Re-verification schedule per objection**, set by how fast that kind
  of fact moves.
  *Done when:* objections carry a next-check date and the due ones can be listed.
- [ ] **29. Retraction.** When an objection stops holding, mark it retracted
  with the date and reason, preserving history.
  *Done when:* a forced re-check flips one objection to retracted.
- [ ] **30. Daily loop.** Wakes, re-checks what is due, stays silent unless
  something changed.
  *Done when:* it runs three consecutive days and says nothing on a day with no change.
- [ ] **31. One notification channel.**
  *Done when:* a real change reaches you outside the app.
- [ ] **32. GATE — deploy the loop and leave it running.** From here the logs
  accumulate on their own while everything else is built.
  *Done when:* it runs unattended, off your laptop, for a full day without you touching it.

## Phase 4 — Interface

- [ ] **33. FastAPI app running, with two modes from the start.** Personal
  instance and a clean public demo session with no personal data.
  *Done when:* both open in a browser and demo mode shows nothing personal.
- [ ] **34. Funnel screen.** The rejection log, visible. Best 30 seconds of the video.
- [ ] **35. Counter-case screen.** Surviving objections with line, link, tier,
  date, confidence. Source-quality info folded in here rather than its own screen.
- [ ] **36. Claim register screen.** Everything asserted, with status.
  *Done when (34–36):* a stranger can navigate all three without explanation.

## Phase 5 — Memory and reusable skills

Deliberate build items. These will not emerge from the pipeline on their own.

- [ ] **37. Situation store, small, plus minimum-slice selection.** Send three
  or four relevant facts per request, never the whole store.
  *Done when:* the logged prompt for a run contains only relevant facts, checked by eye.
- [ ] **38. Two falsification routines**, stored as data: decomposition
  pattern, primary-source rule, query patterns. Reduced from four.
  *Done when:* both are stored and readable outside the code.
- [ ] **39. Route a claim to its routine.** Two routines that never route are
  just two prompt templates — the routing is the capability.
  *Done when:* two claims of different classes visibly take different paths.

## Phase 6 — Measurement and ship

- [ ] **40. Tier table generated from SQLite**, not estimated. Volume, cost and
  latency per tier.
  *Done when:* the numbers come out of a query over real logged runs.
- [ ] **41. Naive baseline comparison.** What the same workload costs routed
  entirely to Ultra.
  *Done when:* one table shows both, with the multiple.
- [ ] **42. Seed the register from existing writing** and use it daily.
  *Done when:* the register holds real claims accumulating real timestamps.
- [ ] **43. Public demo hardening.** Pre-computed replays by default; live runs
  behind a hard daily cap.
  *Done when:* a stranger can use it without being able to drain the Tavily balance.
- [ ] **44. README rewrite for judges.** Resolve `README1.md` → `README.md` so
  GitHub renders it. Setup instructions, Nemotron and Token Factory usage, the
  numbers. State the actual logged run duration — do not overclaim it.
  *Done when:* a stranger clones and runs it in under 10 minutes, tested clean.
- [ ] **45. Demo video, under 3 minutes, public on YouTube.** Audio covers
  Token Factory and Nemotron. Shows the funnel and a real retraction.
- [ ] **46. Feedback write-up finalised** from `FEEDBACK.md`.
- [ ] **47. Flip the GitHub repo to Public.** A private repo on submission day
  is an invalid entry.
- [ ] **48. Submit**, with slack before the 30 Oct 10:30pm IST deadline.

---

## Cut from the original plan

Recorded as decisions, not omissions, so they can be reversed if time appears.

- **Draft extraction** (pull claims out of your own writing) — a real
  capability, but not a track requirement on its own.
- **Source ledger as its own screen** — folded into the counter-case view.
- **Learned source reliability over time** — tiers are graded per run, not
  accumulated across runs.
- **Falsification routines: four reduced to two.** Routing between them stays.
- **"Runs unattended for weeks" / "used daily for the whole build window"** —
  unreachable now. The loop still ships and still runs unattended; the README
  states the real number of days rather than a claim the logs cannot support.
