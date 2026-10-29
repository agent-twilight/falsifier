# Demo video — shot list

Written for: you, filming. Under 3 minutes, public on YouTube, with audio.

**The one hard requirement:** the audio must say **Nebius Token Factory**
and **NVIDIA Nemotron** out loud. Not on a slide. Spoken.

---

## Film on your own instance, not the public URL

`http://127.0.0.1:8000` — start it with `scripts\run_web.cmd`.

Three reasons:

- **Nothing is lost.** It writes to a file on your disk. The free host has
  no disk, so it resets when it sleeps or redeploys, which is what kept
  wiping your notifications.
- **Telegram actually fires.** The public demo has nobody to notify.
- **Your real plans are in it**, with real timestamps going back to 19 Oct.

Show the public URL at the end so judges know where to go.

## Before you press record

1. Start the server, open the site, let it settle.
2. Press **"Put it back"** on *See the watching work* so the notice reads
   **14 April 2026** and no dot is showing.
3. Have your phone on screen or beside you for the Telegram shot.
4. Decide which plan you open in beat 2 — the **Nvidia** one is the best,
   because the answer is genuinely useful and it admits what it cannot know.

---

## The shape

| | Beat | Time | On screen |
|---|---|---|---|
| 1 | The problem | 0:00–0:20 | Landing page |
| 2 | It checks | 0:20–0:55 | A finished plan |
| 3 | **It tells you** | 0:55–1:45 | Notice → dot → message |
| 4 | Show your working | 1:45–2:20 | Funnel, then numbers |
| 5 | What it won't do | 2:20–2:40 | An unsettled answer |
| 6 | Close | 2:40–2:55 | Landing page |

Beat 3 is the one that matters. Everything else is support.

---

## Beat 1 — the problem (0:00–0:20)

**On screen:** the landing page, the box empty.

> You plan a hundred days of revision. Then the exam board moves the date,
> and nobody tells you. Every day of that plan is now built on something
> that is no longer true.
>
> This is the Falsifier. You tell it what you are planning, it checks
> whether that still holds up — and then it keeps watching.

Do **not** say "it tries to prove you wrong." That framing is gone.

## Beat 2 — it checks, and it cites (0:20–0:55)

**On screen:** open the Nvidia plan. Scroll slowly through one finding.

> I told it I thought ten years at Nvidia could make me a multimillionaire.
> It did not just agree with me.

Point at the quote and the link.

> Everything it tells me carries the line it rests on and a link I can
> click. If it cannot find a real sentence on a real page, it does not get
> to make the claim — that is checked in code, not asked for politely.

Then the reasoning block, labelled *my reasoning, not evidence*:

> And where the sources run out, it says so and reasons anyway — here it
> works out that the equity grant is what actually decides this, not the
> salary. It is clear about which part is evidence and which part is
> thinking.

## Beat 3 — it comes to you (0:55–1:45) — **the important one**

**On screen:** the side panel, no dots. Then *See the watching work*.

> Here is the part no general assistant does. I am going to play the exam
> board.

Open the notice. Change the date. Publish.

> I have just changed the source it was relying on. I am not going to ask
> it anything.

**Cut back to the side panel.** Let the dot appear on camera. Wait for it.

> There. That conversation has a dot on it now, and I never typed
> anything.

Open the plan. Read the message, or let it sit on screen.

> It says what it told me no longer holds, shows what the page says
> instead, and timestamps the withdrawal. That is an AI correcting itself,
> on the record.

**Then the phone**, if you have a Telegram alert to show:

> And on my own machine it reaches me here, without me opening anything.

## Beat 4 — show your working (1:45–2:20)

**On screen:** click *see how I checked this*.

> Everything it threw away. Angles it tried, searches it ran, pages it
> read, quotes that survived being checked word for word against the page
> they came from. About a third get discarded because the sentence was not
> actually there.

**Then the numbers page.**

> Every one of those decisions is an NVIDIA Nemotron model running on
> Nebius Token Factory. Nemotron Nano does the hundreds of cheap
> judgements. Super reads the sources. Ultra decides, twice.
>
> Nine and a half cents a claim. Putting the same work entirely through
> the largest model would cost nine and a half times more — and that is
> measured from logged calls, not estimated.

Say those two product names clearly. This is the required bit.

## Beat 5 — what it will not do (2:20–2:40)

**On screen:** an answer where it refused to settle something.

> It is also willing to say it does not know. Here it will not guess at my
> compensation, and it tells me exactly which fact would settle it. An
> assistant that answers everything is not one you should trust.

## Beat 6 — close (2:40–2:55)

> Open source, MIT licensed, built on Nemotron through Nebius Token
> Factory. There is a live demo in the description where you can change
> the source yourself and watch it notice.

---

## Say these, they are required or near enough

- **"Nebius Token Factory"** and **"NVIDIA Nemotron"**, out loud
- Name the tiers doing different jobs — Nano, Super, Ultra
- The cost number and that it is measured

## Do not say these

- **"It has been running for weeks."** The log shows **six days**
  between 19 and 28 October, with gaps where the laptop was off. Say
  "since the nineteenth", or say nothing. The log is in the repo and a
  judge can open it.
- **"It proves you wrong."** Wrong product, wrong framing.
- **"The gap is real, nobody has built this."** It cannot prove a
  universal negative and the README says so.
- Anything about the dummy notice being a real exam board. Say plainly
  that you are playing the board, and that only *who moves the date* is
  simulated.

## Things that will trip you up

- **Press "Put it back" between takes**, or the dot is already gone and
  the finding already withdrawn.
- **The dot clears the moment you open the thread**, like any messaging
  app. Film the panel first, then open it.
- **Do not open the thread while waiting** for the dot — that marks it
  read.
- The message arrives in about **two seconds**. Do not cut away early,
  and do not leave a long silent pause either.
- **Nothing in the repo is private**, but your `.env` is not in it. Do not
  put a terminal with keys on screen.
