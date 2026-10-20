# The public demo.
#
# The demo serves pre-computed worked examples and lets a visitor check a
# claim of their own. It carries no personal data: the database baked in
# here contains only rows marked mode='demo', and the application cannot
# read a personal row even if one existed.
#
# Nothing it writes needs to survive a restart, which is why a free tier
# with an ephemeral filesystem is enough. A visitor's claim is therefore
# never stored anywhere, which is the right default for a stranger.
#
# The port is taken from $PORT so this runs unchanged on Render, Fly, Cloud
# Run or anything else that assigns one. Falls back to 8000 locally.

FROM python:3.13-slim

RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    FALSIFIER_DEMO=1 \
    PORT=8000

WORKDIR $HOME/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=user falsifier/ ./falsifier/
COPY --chown=user web/ ./web/
COPY --chown=user scripts/ ./scripts/

# The pre-computed demo database, built by scripts/build_demo_db.py and
# committed deliberately. Without it the site opens on an empty page.
COPY --chown=user data/demo.db ./data/falsifier.db

USER user
EXPOSE 8000

CMD ["sh", "-c", "uvicorn web.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
