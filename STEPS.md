# Build steps

The whole project in small numbered steps, in build order. One line for what
each step does, one line for how we know it worked. Tick them off as we go —
this is the progress tracker across sessions.

A step is something verifiable in a few minutes. If a step turns out to be
bigger than that, split it rather than pushing through.

**The gate:** steps 1–27 must all be done before any step from Phase 5 onward.
End-to-end working comes before polish.

---

## Phase 0 — Setup

- [x] **1. Git repo, `.gitignore`, MIT licence, project scaffolding.** Version
  history and secrets protection in place before any code exists.
  *Done when:* `git log` shows a commit and `git check-ignore -v .env` prints a rule.
- [ ] **2. Virtual environment and dependencies.** An isolated Python for this
  project, separate from Anaconda base.
  *Done when:* `.venv\Scripts\python.exe -c "import sys, fastapi; print(sys.prefix)"` prints a path ending in `falsifier\.venv`.
- [ ] **3. Nebius account, Zero Data Retention ON, credits claimed.** ZDR is
  opt-in and must be set before any real data goes in.
  *Done when:* ZDR shows enabled on the profile page and the credit balance is visible.
- [ ] **4. Confirm Token Factory base URL and the three Nemotron model ids.**
  The rename from AI Studio means older docs may be wrong.
  *Done when:* all four values are written into `.env`.
- [ ] **5. Tavily account and key, and find the actual search allocation.**
  Tavily credits are the binding constraint, not Nebius credits.
  *Done when:* the key is in `.env` and the search quota number is written into CLAUDE.md.
- [ ] **6. Record real per-token prices per tier.** Needed before any
  cost-per-claim number means anything.
  *Done when:* prices for Nano, Super and Ultra are written into a config file.

## Phase 1 — Plumbing

- [ ] **7. One Nemotron call that returns text.** The "is any of this real"
  test. Ten lines, prints a response.
  *Done when:* running one script prints a model reply in the terminal.
- [ ] **8. SQLite database and schema.** Tables for calls, claims, sub-claims,
  hypotheses, evidence, objections, sources.
  *Done when:* the file exists in `data/` and the table list prints.
- [ ] **9. The call wrapper.** A single function every model call goes through,
  logging model, input tokens, output tokens, latency and computed cost.
  *Done when:* one call through the wrapper produces one row in the calls table with all fields filled.
- [ ] **10. Spend cap and per-run call ceiling inside the wrapper.** Total
  credits are $50; a retry bug could eat that overnight.
  *Done when:* a deliberate over-limit test is refused with a clear error, and no call is made.
- [ ] **11. Cost per claim computed from real prices.** Multiply logged token
  counts by confirmed prices.
  *Done when:* a printed estimate for one full pipeline run exists and is affordable against $50.
- [ ] **12. One Tavily search returning results.**
  *Done when:* a script prints titles and URLs for one query.
- [ ] **13. Tavily result cache.** Never re-search a query already answered.
  *Done when:* running the same query twice makes one network call and the second is served from cache.

## Phase 2 — Pipeline spine

One claim in, one sourced counter-case out. Ugly is fine here; working is the
only requirement.

- [ ] **14. Decompose a claim into load-bearing sub-claims** (Super).
  *Done when:* a typed claim prints 3–5 sub-claims that are genuinely what it rests on.
- [ ] **15. Generate falsification hypotheses per sub-claim** (Nano, ~50).
  *Done when:* the hypotheses are ways the sub-claim could be *false*, not restatements of it.
- [ ] **16. Generate search angles per hypothesis** (Nano).
  *Done when:* the queries would surface disconfirming evidence, not the original claim.
- [ ] **17. Retrieve for each angle** (Tavily).
  *Done when:* results come back for every angle and are stored against their hypothesis.
- [ ] **18. Triage each result** (Nano, ~400). Does this bear on the hypothesis?
  *Done when:* the survivor count is a small fraction of results and spot-checking the rejects looks right.
- [ ] **19. Read survivors, grade the source, extract the exact line** (Super).
  *Done when:* each survivor has a quoted line, a live link, a source tier and a date or an undated flag.
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
- [ ] **26. Graceful failure on all four paths.** Malformed model output, Tavily
  timeout, dead link, budget ceiling hit.
  *Done when:* each is simulated and the run degrades with a visible reason instead of crashing.
- [ ] **27. 🚩 GATE — one real claim of yours, end to end.**
  *Done when:* you type a belief you actually hold and read a sourced counter-case you did not already know.

## Phase 3 — Memory and reusable skills

Deliberate build items. These will not emerge from the pipeline on their own.

- [ ] **28. Situation store.** The small set of facts that determine which
  objections apply to you.
  *Done when:* facts can be added and read back.
- [ ] **29. Minimum-slice selection.** Send three or four relevant facts per
  request, never the whole store.
  *Done when:* the logged prompt for a run contains only relevant facts, checked by eye.
- [ ] **30. Source ledger.** Which domains have proved reliable, learned over time.
  *Done when:* tiers persist across runs and influence grading.
- [ ] **31. Falsification routines as stored skills.** One procedure per class
  of claim: timeline, eligibility, cost, demand.
  *Done when:* four routines are stored, each with its decomposition pattern, primary-source rule and query patterns.
- [ ] **32. Route a claim to its routine.**
  *Done when:* two claims of different classes visibly take different paths.

## Phase 4 — Tasks, not answers

- [ ] **33. Extract claims from a draft.** Point it at an email or plan; it
  pulls out the load-bearing assertions itself.
  *Done when:* a real draft of yours yields assertions you did not type in.
- [ ] **34. Re-verification schedule per objection**, set by how fast that kind
  of fact moves.
  *Done when:* objections carry a next-check date and the due ones can be listed.
- [ ] **35. Retraction.** When an objection stops holding, mark it retracted
  with the date and reason.
  *Done when:* a forced re-check flips one objection to retracted and the history is preserved.
- [ ] **36. Daily loop.** Wakes, re-checks what is due, stays silent unless
  something changed.
  *Done when:* it runs unattended for three consecutive days and says nothing on a day with no change.
- [ ] **37. One notification channel.**
  *Done when:* a real change reaches you outside the app.

## Phase 5 — Interface

- [ ] **38. FastAPI app running, with two modes from the start.** Personal
  instance and a clean public demo session with no personal data.
  *Done when:* both modes open in a browser and the demo mode shows nothing personal.
- [ ] **39. Claim register screen.** Everything asserted, with status.
- [ ] **40. Counter-case screen.** Per claim: surviving objections with line,
  link, tier, date, confidence.
- [ ] **41. Funnel screen.** The rejection log, visible. This is the best 30
  seconds of the video.
- [ ] **42. Source ledger screen.** What it trusts, what it doesn't, why.
  *Done when (39–42):* a stranger can navigate all four without explanation.

## Phase 6 — Measurement and ship

- [ ] **43. Tier table generated from SQLite**, not estimated. Volume, cost and
  latency per tier.
  *Done when:* the numbers come out of a query over real logged runs.
- [ ] **44. Naive baseline comparison.** What the same workload costs routed
  entirely to Ultra.
  *Done when:* a single table shows both, with the multiple.
- [ ] **45. Seed the backlog from existing writing** and use it daily.
  *Done when:* the register holds real claims accumulating real timestamps.
- [ ] **46. Deploy the demo URL.**
  *Done when:* someone else, on their own device, runs a claim through it.
- [ ] **47. README rewrite for judges.** Resolve `README1.md` → `README.md` so
  GitHub renders it; setup instructions, Nemotron and Token Factory usage, numbers.
  *Done when:* a stranger clones and runs it in under 10 minutes, tested on a clean machine.
- [ ] **48. Demo video, under 3 minutes, public on YouTube.** Audio covers
  Token Factory and Nemotron. Shows the funnel and a real retraction.
- [ ] **49. Feedback write-up finalised** from `FEEDBACK.md`.
- [ ] **50. ⚠️ Flip the GitHub repo to Public.** A private repo on submission
  day is an invalid entry.
- [ ] **51. Submit**, with slack before the 30 Oct 10:30pm IST deadline.
