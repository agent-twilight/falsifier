# Putting the demo online

Written for: you, following it once, on a Hugging Face account you have
just made. Everything here is a browser step or a single command.

The demo needs to outlive the deadline, because judging happens after
30 October and your laptop will not be serving anything by then.

---

## What you do

### 1. Create the Space

Go to **huggingface.co/new-space** and fill in:

| Field | Value |
|---|---|
| Owner | your username |
| Space name | `falsifier` |
| License | `mit` |
| SDK | **Docker** → *Blank* |
| Hardware | CPU basic (free) |
| Visibility | **Public** |

Click **Create Space**. It will show you an empty repository page.

### 2. Give it the two API keys

On the Space page: **Settings** → **Variables and secrets** → **New secret**,
twice:

| Name | Value |
|---|---|
| `NEBIUS_API_KEY` | the same value as in your `.env` |
| `TAVILY_API_KEY` | the same value as in your `.env` |

Then add these as **variables** (not secrets — they are not sensitive):

| Name | Value |
|---|---|
| `NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1/` |
| `NEMOTRON_NANO` | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` |
| `NEMOTRON_SUPER` | `nvidia/nemotron-3-super-120b-a12b` |
| `NEMOTRON_ULTRA` | `nvidia/Nemotron-3-Ultra-550b-a55b` |

Do **not** add the Telegram keys. Notifications are for your instance
only; the public demo has nobody to notify.

> These keys spend real money. The demo caps itself at 25 checks a day,
> but if the Space ever gets unwanted traffic, delete the secrets and it
> stops being able to run anything.

### 3. Tell me the Space URL

Paste it to me and I will push the code. It looks like
`https://huggingface.co/spaces/<your-username>/falsifier`.

---

## What I do

```
git remote add space https://huggingface.co/spaces/<you>/falsifier
git push space main
```

Hugging Face builds the image and starts it. First build takes a few
minutes; after that the site is at
`https://<your-username>-falsifier.hf.space`.

---

## How you check it worked

1. Open the URL. The page should say **"Public demo"** at the top.
2. Two worked examples should already be there — they ship inside the
   image, so the page is never empty.
3. Click into one, then **"see how this was checked"**. The funnel should
   show every query and every angle tried.
4. Type a claim of your own and press **Check this**. The numbers should
   climb for about a minute, then show an answer with sources.
5. Open it on your phone.

If the page is blank or shows an error, the Space's **Logs** tab says why.

---

## Things worth knowing

**It sleeps.** A free Space goes idle after about two days without
visitors, and the next person waits roughly thirty seconds for it to wake.
Before you submit, open it once so it is warm.

**Nothing personal is on it.** The database inside the image was built by
`scripts/build_demo_db.py`, which copies only rows marked `mode='demo'`
and refuses to write the file if anything else slipped in. The application
also cannot open a personal claim in demo mode even if the id is guessed.

**Nothing it writes is kept.** Checks run by visitors live in the
container's own filesystem and vanish when the Space restarts. That is
deliberate: it means a stranger's claim is never stored anywhere.

**To update it later**, after any change:

```
git push space main
```
