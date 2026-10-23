# Demo video — shot list

Written for: you, filming. Under 3 minutes, public on YouTube, with audio.

The audio must explicitly say you used **Nebius Token Factory** and
**NVIDIA Nemotron** — that is a hard requirement, not a nicety.

**Before you record:** open [falsifier.onrender.com](https://falsifier.onrender.com)
once so the free host is awake. A cold start is fifty seconds of nothing.

---

## The shape

Three beats. Problem, product, proof. Do not explain the architecture
before the viewer cares about the problem.

| | Beat | Seconds | What is on screen |
|---|---|---|---|
| 1 | The problem | 0:00–0:25 | The front page |
| 2 | It works | 0:25–1:25 | A live check, funnel filling |
| 3 | The proof | 1:25–2:40 | Funnel detail, numbers, Telegram |
| 4 | Close | 2:40–2:55 | Front page again |

---

## Beat 1 — the problem (0:00–0:25)

**On screen:** the front page, the JEE paragraph visible.

**Say roughly:**

> You plan a hundred days of revision. Then the exam board moves the date,
> and nobody tells you. Every day of that plan is now built on something
> that is no longer true.
>
> This is the Falsifier. You tell it what you are planning. It checks
> whether that still holds up today, and then keeps watching. When
> something outside your control changes, it tells you.

**Do not** say "it tries to prove you wrong." That framing is gone.

---

## Beat 2 — it works (0:25–1:25)

**On screen:** type a claim into the box and press Check. Let the funnel
fill. Speed the footage up if you need to — say so on screen if you do.

Use a claim where the answer is interesting. The Stanford one is good
because the verdict is a precise distinction rather than a flat yes or no.

**Say roughly:**

> It is not searching for my claim. Searching for what you already believe
> returns pages agreeing with you. It invents the ways my plan could be out
> of date first, then hunts for those.
>
> Every one of these decisions is an NVIDIA Nemotron model running on
> Nebius Token Factory. The small one, Nemotron Nano, does hundreds of
> cheap judgements. The large one, Ultra, is used twice.

**Land on the answer.** Point at the quote and the link.

> It does not tell me I am wrong. It shows me the line it is relying on,
> from Stanford's own page, and I can click it.

---

## Beat 3 — the proof (1:25–2:40)

Three things, fast. This is where the marks are.

**a) The funnel** — click "see how this was checked".

> Here is everything it threw away. Six angles tried, six searches, twenty
> four pages, six quotes that survived being checked word for word against
> the page they came from. About a third of attempted quotes get discarded
> because the sentence was not actually there. That check is in code, not
> in a prompt.

**b) The numbers** — click "What it costs".

> Nine and a half cents a claim. Routing the same work entirely to the
> largest model would cost nine and a half times more. That is measured
> from logged calls, not estimated.

**c) Telegram** — your phone, the real message.

> And it keeps watching. When a source changes, it withdraws what it told
> me, with the date and the reason.

If you have a genuine retraction by filming day, use it. If not, say
plainly that this one was triggered deliberately to show the path — do
not imply a real source changed when it did not.

---

## Beat 4 — close (2:40–2:55)

> Open source, MIT licensed, running on Nemotron through Nebius Token
> Factory. The link is in the description and you can try your own claim.

---

## Things to get right

- **Say "Nebius Token Factory" and "NVIDIA Nemotron" out loud.** Required.
- **Show real timestamps.** Do not stage a fresh database.
- **Show one thing it could not answer.** Your own Nvidia claim is ideal:
  it refused to guess and named the four facts only you could supply. An
  agent that answers everything is not believable.
- **Under three minutes.** Hard limit.
- **Public on YouTube**, not unlisted.

## Things to avoid

- Slides. Show the product running.
- Narrating the code. Nobody is marking your file layout.
- Claiming it has run unattended for weeks. The log shows 19, 20 and 23
  October. Say "since the nineteenth" or say nothing.
- The word "objection". The product does not use it any more.
