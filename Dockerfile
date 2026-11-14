# syntax=docker/dockerfile:1
#
# Autonomous AI Code Reviewer & PR Assistant -- container image.
#
# Two stages:
#   builder  -- python:3.12-slim, compiles/downloads every pinned dependency from
#              requirements.lock into /wheels (this is the ONLY stage that needs
#              network access to PyPI).
#   runtime  -- python:3.12-slim, installs those wheels with --no-index, copies
#              the application, drops to uid 10001, serves uvicorn on :8000.
#
# Base tag tracks CPython 3.12 to match .python-version (3.12.13). Both stages
# use the SAME minor so the wheels built in stage 1 are installable in stage 2
# (cp310 ABI). Changing only one stage's base breaks the --no-index install.
#
# Zero environment variables are required at runtime: with no API key the app
# selects its local rule engine and /health still answers 200.

# ---------------------------------------------------------------------------
# Stage 1 -- build wheels
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# Compilers are only needed if a pin has no manylinux wheel for cp310; the layer
# lives in this stage and is discarded, so it costs image size nothing.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# requirements.lock is the single source of pinned truth (not requirements.txt).
# Copying it alone keeps this layer cached until the pins actually change.
COPY requirements.lock ./

# Build a wheel for every pin, plus the wheels they depend on.
RUN pip wheel --wheel-dir /wheels -r requirements.lock

# ---------------------------------------------------------------------------
# Stage 2 -- runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/app

# The wheelhouse and the lock file it came from: install is offline by
# construction (--no-index), so the build fails loudly instead of silently
# reaching PyPI for something the lock does not pin.
COPY --from=builder /wheels /wheels
COPY requirements.lock /opt/requirements.lock

RUN pip install --no-index --find-links=/wheels -r /opt/requirements.lock \
 && rm -rf /wheels

# Non-root runtime user. Fixed uid 10001 so bind mounts and Kubernetes
# runAsUser stay predictable across rebuilds.
RUN groupadd --gid 10001 appuser \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
 && mkdir -p /app \
 && chown appuser:appuser /app

WORKDIR /app

# Only what the process reads at runtime: the package, the CLI anchor, and the
# sample diff /test-review serves. Tests, docs, benchmarks and CI stay out.
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser reviewer.py ./reviewer.py
COPY --chown=appuser:appuser samples/ ./samples/

USER 10001:10001

EXPOSE 8000

# Probe /health with the interpreter already in the image -- no curl, no extra
# layer. urlopen raises on a non-2xx response, so a failing app exits non-zero.
HEALTHCHECK --start-period=10s --interval=30s --timeout=3s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

STOPSIGNAL SIGTERM

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
