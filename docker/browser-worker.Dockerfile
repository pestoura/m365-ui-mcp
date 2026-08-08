# syntax=docker/dockerfile:1
# Base image is digest-pinned; CI enforces this via scripts/check_base_image_pinning.py.
# The worker owns the Chromium session. It is never published: it listens on the internal
# compose network only (docs/deployment.md, docs/browser-worker.md).
#
# NOTE: the Playwright runtime image is added with EPIC-02 (P-011). Until then this image
# builds the worker package surface only and contains no browser binary and no profile.

FROM python:3.12-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36 AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install .

FROM python:3.12-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PLANNER_WORKER_PROFILE_DIR=/profile

# Non-root. The persistent Chromium profile is a mounted volume owned by this uid; it is
# never baked into the image and never committed to git.
RUN useradd --system --uid 10002 --create-home --home-dir /home/worker worker \
 && mkdir -p /profile && chown worker:worker /profile

COPY --from=build /opt/venv /opt/venv
COPY --chown=worker:worker browser/selectors /app/browser/selectors

WORKDIR /app
USER 10002:10002

# Internal network only — deliberately not published to the host.
EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import planner_mcp; print(planner_mcp.CONTRACT_VERSION)" || exit 1

ENTRYPOINT ["python", "-c", "import planner_mcp, sys; sys.stdout.write('worker ' + planner_mcp.CONTRACT_VERSION + '\\n')"]
