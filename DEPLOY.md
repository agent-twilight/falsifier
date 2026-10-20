# Putting the demo online

Written for: you, following it once. Everything is a browser step except
the last one, which is mine.

The demo has to outlive the deadline, because judging happens after
30 October and your laptop will not be serving anything by then.

Host: **Render**, free plan. Chosen after Hugging Face restricted free
accounts to Static Spaces. Free terms change — if anything below does not
match what you see, stop and tell me rather than working around it.

---

## What you do

### 1. Sign up

Go to **render.com** and sign up with your GitHub account. Signing in with
GitHub matters, because Render needs to read the repository.

### 2. Create the service

Click **New +** → **Blueprint**.

Render will ask which repository. Pick **agent-twilight/falsifier**. It is
private, so you will be asked to grant access to that repo — that is
expected and it stays private.

Render reads `render.yaml` from the repo and proposes a service called
`falsifier` on the free plan. Approve it.

> If Blueprint is not offered, use **New +** → **Web Service** instead,
> pick the same repo, and choose **Docker** as the runtime. Render will
> find the `Dockerfile` by itself. Set the plan to **Free**.

### 3. Add the two keys

Render will prompt for the two values marked `sync: false`, or you can add
them afterwards under **Environment**:

| Name | Where to get it |
|---|---|
| `NEBIUS_API_KEY` | copy from your own `.env` file |
| `TAVILY_API_KEY` | copy from your own `.env` file |

Everything else — the base URL and the three model ids — is already in
`render.yaml`, so you do not need to type it.

**Do not add the Telegram keys.** Notifications are for your instance only;
the public demo has nobody to notify.

> These keys spend real money. The demo caps itself at 25 checks a day. If
> the site ever attracts unwanted traffic, delete the two keys in Render and
> it immediately loses the ability to run anything.

### 4. Tell me the URL

Render gives you something like `https://falsifier.onrender.com`. Paste it
to me. The first build takes a few minutes.

---

## How you check it worked

1. Open the URL. The top should say **"Public demo"**.
2. **Two worked examples should already be there.** They ship inside the
   image, so the page is never empty — this is what a judge sees first.
3. Click one, then **"see how this was checked"**. Every query and every
   angle tried should be listed, with the fruitless ones greyed out.
4. Type a claim of your own and press **Check this**. The numbers should
   climb for about a minute, then settle on an answer with sources.
5. Open it on your phone.

If anything is blank or broken, Render's **Logs** tab says why. Send me what
it says.

---

## Things worth knowing

**It sleeps.** A free Render service goes idle after about fifteen minutes
without visitors, and the next person waits roughly fifty seconds for it to
wake. **Open the link once shortly before you submit** so a judge does not
land on a cold start. If that wait turns out to be unacceptable, moving to a
paid plan or to Fly.io is a small change — the image is already
host-agnostic and reads its port from the environment.

**Nothing personal is on it.** The database inside the image was built by
`scripts/build_demo_db.py`, which copies only rows marked `mode='demo'` and
refuses to write the file at all if anything else gets in. The application
cannot open a personal claim in demo mode even if the id is guessed, and the
image hardcodes demo mode so a misconfigured service cannot escape it.

**Nothing a visitor types is kept.** Their check runs in the container's own
filesystem and vanishes when it restarts. For a stranger's claim that is the
right default.

**To update it**, push to GitHub. Render rebuilds automatically.

---

## If Render's free plan has also changed

The image is a plain Dockerfile that reads `$PORT`, so it runs unchanged on
Fly.io, Google Cloud Run, Railway or any VM. Only the signup differs. Tell me
what you are seeing and I will adjust.
