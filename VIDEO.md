# Demo video — final script

Under 3 minutes, public on YouTube, with audio. About 405 spoken words,
which lands near **2:45** at a normal pace.

**The one hard requirement:** say **Nebius Token Factory** and **NVIDIA
Nemotron** out loud. Not on a slide. Spoken. Both are in the script twice.

---

## Before you record

1. **Film the public URL**: `https://falsifier.onrender.com`. It is what
   judges will click, and a localhost address on screen invites the
   question of whether the deployed version actually works.
2. **Open it a few minutes early.** The free host sleeps after fifteen
   minutes idle and takes about fifty seconds to wake. Reload until it is
   snappy, then leave the tab open.
3. Open **See the watching work** and press **Put it back**, so the notice
   reads 14 April 2026 and no dot is showing in the panel.
4. Fill in the two brackets in beat 2 with one of the worked examples. The
   **Stanford degree** one is cleanest: the verdict is a precise
   distinction rather than a flat yes or no.
5. Do a silent run-through once. The message takes about **two seconds** —
   know what that pause feels like before you are recording.

---

## The script

### 1. The problem · 0:00–0:28 · *face to camera, or b-roll*

> I keep making plans. Career moves, startup ideas. And by the end of the
> month the company I was aiming at is laying people off, or some
> seventeen-year-old has already shipped my idea.
>
> My plans go out of date and nobody tells me.
>
> So I built something I can tell my plans to. It checks them against the
> world as it is today — and then keeps watching.

### 2. It checks, and it cites · 0:28–0:58 · *open a finished plan*

> This is The Falsifier. Here is a real plan of mine: **[your claim, one
> sentence]**.
>
> It came back with **[the verdict, a few words]**, at ninety per cent
> confidence, from Stanford's own admissions page.

*[point at the quoted line, then the link]*

> Everything it tells me carries the exact line it rests on, and a link.
> That quote is checked word for word against the live page — if the
> sentence is not really there, it gets thrown away. About a third are.

### 3. Under the hood · 0:58–1:28 · *click “see how I checked this”, then the numbers page*

> Here is everything it discarded getting there. The angles it tried, the
> searches it ran, the pages it read.
>
> Small **NVIDIA Nemotron** models make hundreds of cheap judgements, a
> bigger one reads the sources, the biggest one decides. All on **Nebius
> Token Factory**. That split is nine and a half times cheaper than
> putting everything through the largest model — measured from logged
> calls, not estimated.
>
> The whole project has cost me about twenty-five cents.

### 4. It comes to you · 1:28–2:10 · **the one that matters**

*[start on the side panel. Make sure the viewer sees there is no dot.]*

> But checking once is not the point. It re-checks every source behind my
> plans every few days — official pages every three.

*[click **See the watching work**, then open the notice]*

> Here is a test page one of my plans depends on. I am going to play the
> source. I will change the date and publish it, and I am not going to ask
> it anything. Normally it would find this on its own the next morning;
> here, publishing sets the check off straight away.

*[change the date, publish, then go back to the panel and stop talking
for about two seconds — let the dot appear on camera]*

> There. That conversation has a dot on it now, and I never typed
> anything. It came to me.

*[open the plan]*

> It says what it told me no longer holds, shows what the page says
> instead, and timestamps the correction. That is an AI correcting itself,
> on the record.

### 5. What it will not do · 2:10–2:20

> And when it cannot settle something, it says so — and names the one fact
> that would settle it.

### 6. Close · 2:20–2:45 · *back to the landing page*

> A month ago I had never built an app. Now it checks my plans against the
> real world, and tells me when the world moves.
>
> Open source, MIT, running on **NVIDIA Nemotron** through **Nebius Token
> Factory**. The demo is linked below — go and change the date yourself,
> and see whether it notices.

---

## If you run long

Cut in this order:

1. Beat 5, the unsettled line. One sentence, easy to lose.
2. The second half of beat 3 — keep the model names and the cost, drop
   "about twenty-five cents".
3. Tighten beat 1 to the first paragraph.

**Never cut beat 4.** It is the only thing in the video that no general
assistant does.

---

## Getting the facts right

These are all checkable from your repo, so the honest version costs
nothing and the other kind is a risk.

- **The schedule.** The daily loop re-checks each source on its own
  interval — **3 days** for an official page, 2 for news, 7 for a forum.
  Separately, once a week it searches for pages that did not exist before.
  Do **not** say "it checks weekly"; that understates it.
- **No Telegram in this cut.** The product does message your phone on a
  personal instance, but the public demo has nobody to notify, so the
  video shows the dot instead. Do not claim it texted you.
- **The demo responds in seconds** because publishing a change triggers
  the check immediately. Say so. The page says the same thing, so a judge
  comparing the two will find them consistent.
- **Only who moves the date is simulated.** The citation, the
  word-for-word check, the withdrawal and the message are the same code
  that runs against Stanford.
- **It has run on six days** between 19 and 28 October, with gaps where
  the laptop was off. Say "since the nineteenth" or say nothing. Never
  "for weeks" — the log is in the repo.
- **Cost is $0.27 on Nebius** plus 48 of 1000 free Tavily credits.
- **It is called The Falsifier**, not Falsify. That is what the site, the
  README and the repo all say.
- **It cannot prove nobody else has built this.** Do not claim the gap is
  empty.

## Things that will trip you up

- **Press "Put it back" between takes**, or the dot is already gone and
  the finding already withdrawn.
- **The dot clears the instant you open the thread.** Film the panel
  first, then open it.
- **Do not open the thread while waiting** for the message — that marks it
  read and the dot never appears on camera.
- **Do not put a terminal with your `.env` on screen.**
- Record the two-second pause in beat 4 rather than cutting it. The wait
  is the proof that you did not prompt it.
