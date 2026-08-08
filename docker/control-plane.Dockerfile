# syntax=docker/dockerfile:1
# Base images are digest-pinned; CI enforces this via scripts/check_base_image_pinning.py.
# Digest resolved from docker.io/library/python:3.12-slim. Renewal is tracked by Dependabot.

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
    PATH="/opt/venv/bin:$PATH"

# Non-root, no shell-writable home, no credential material baked in.
RUN useradd --system --uid 10001 --create-home --home-dir /home/planner planner
COPY --from=build /opt/venv /opt/venv
COPY --chown=planner:planner browser/selectors /app/browser/selectors

WORKDIR /app
USER 10001:10001

# Control plane listens on loopback inside the container network only; exposure is the
# deployment's responsibility (see docs/deployment.md).
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import planner_mcp; print(planner_mcp.CONTRACT_VERSION)" || exit 1

ENTRYPOINT ["python", "-c", "import planner_mcp, sys; sys.stdout.write(planner_mcp.CONTRACT_VERSION + '\\n')"]
