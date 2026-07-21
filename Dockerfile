# Manufacturing Reasoning Engine — API service image (docs/07 Phase 2, W4).
#
# Multi-stage so OR-Tools build wheels and pip tooling never bloat the runtime
# image. Provider-agnostic: no cloud SDKs, no provider env-var names. The
# application reads only MRE_* configuration; the deploy platform (deploy/azure
# or a swap) injects secrets and mounts the encrypted data volume.
#
# Targets:
#   runtime  (default, shipped) — lean, non-root, healthchecked API.
#   test     (CI only)          — FROM runtime + pinned dev deps + tests, so CI
#                                 exercises the exact shipped layers, not the
#                                 checkout (the stale-install false-green lesson).

# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — builder: resolve pinned deps into a venv, install the app wheel.
# Build tooling is confined here and never copied forward.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Isolated venv we copy wholesale into the runtime image.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dependencies first (pinned lockfile) — cached until the lock changes.
COPY requirements.lock ./
RUN pip install -r requirements.lock

# Then the application itself; deps are already installed, so --no-deps keeps
# the resolved set exactly the locked one.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-deps .

# ---------------------------------------------------------------------------
# Stage 2 — runtime: the shipped image. No compilers, no pip cache, non-root.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    MRE_DATA_ROOT=/data

# curl only, for the container HEALTHCHECK. Create an unprivileged user and the
# data root it owns (run registry / snapshots / evidence live under /data).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system mre \
    && useradd --system --gid mre --create-home --home-dir /home/mre mre \
    && mkdir -p /data \
    && chown -R mre:mre /data

COPY --from=builder /opt/venv /opt/venv

USER mre
WORKDIR /home/mre

# /data is mounted from an encryption-at-rest volume in compose / cloud.
VOLUME ["/data"]
EXPOSE 8000

# Liveness/readiness: hits the app's /health (data root writable, no solver).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Uvicorn via the app factory; MRE_DATA_ROOT points create_app at /data.
CMD ["uvicorn", "mre.api.app:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
# Stage 3 — test: image-as-shipped + dev deps + tests, for CI.
# FROM runtime, so every mre.* import resolves to the SHIPPED venv package.
# tests/ and tools/ are copied to a rootdir where pytest prepends them to
# sys.path (tests/__init__.py present; tools is a namespace package).
# ---------------------------------------------------------------------------
FROM runtime AS test

USER root
COPY requirements-dev.lock requirements.lock ./
RUN pip install -r requirements-dev.lock

WORKDIR /app
# Test rootdir: config + suites + generator + committed fixtures/data. src/ is
# deliberately NOT copied — `import mre` must resolve to the installed wheel.
COPY pyproject.toml plant_config.json ./
COPY tests ./tests
COPY tools ./tools
COPY sample_data ./sample_data
COPY sample_data_v2 ./sample_data_v2
# Spec text + the committed Glass Box dataset are test INPUTS: spec-derived
# tests read docs/ (test_remediation_catalog lints against docs/06) and the
# gate/sabotage tests read datasets/glass_box. Neither ships in the runtime
# image. (session 2.4b — the first real container build found these absent.)
COPY docs ./docs
COPY datasets ./datasets
RUN chown -R mre:mre /app

USER mre
ENV MRE_DATA_ROOT=/tmp/mre_test_data
# The fast suite (raw_data-dependent gauntlet tests skip when the gitignored
# extract is absent, as it is here). Override at `docker run` for other sets.
CMD ["pytest", "-q", "-m", "not slow"]
