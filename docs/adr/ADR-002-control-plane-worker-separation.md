# Separate control plane from browser worker

- Status: Accepted
- Date: 2026-08-08

## Context
Browser automation has a large attack surface and heavyweight dependencies.

## Decision
Ship two processes/images: a FastMCP control plane and a FastAPI browser worker on an internal-only network.

## Consequences
One extra hop and a health contract, in exchange for isolation, independent hardening and testability.
