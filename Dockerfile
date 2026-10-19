# The public demo, for Hugging Face Spaces.
#
# The demo serves pre-computed example runs and lets a visitor check a
# claim of their own. It carries no personal data: the database baked in
# here contains only rows marked mode='demo', and the application cannot
# read a personal row even if one existed.
#
# Nothing it writes needs to survive a restart, which is why a free Space
# with an ephemeral filesystem is enough.

FROM python:3.13-slim

# Hugging Face Spaces run as uid 1000 and expect the app on port 7860.
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    FALSIFIER_DEMO=1

WORKDIR $HOME/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=user falsifier/ ./falsifier/
COPY --chown=user web/ ./web/
COPY --chown=user scripts/ ./scripts/

# The pre-computed demo database, built by scripts/build_demo_db.py and
# committed deliberately. Without it the Space opens on an empty page.
COPY --chown=user data/demo.db ./data/falsifier.db

USER user
EXPOSE 7860

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "7860"]
