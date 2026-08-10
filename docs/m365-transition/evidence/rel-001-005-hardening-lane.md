# REL-001..REL-005 — Hardening lane A

Status: **IMPLEMENTED_MOCK_ONLY / REPOSITORY-SIDE, GATES GREEN**

Scope: the five Phase 16 hardening items that can be completed with repository,
documentation and isolated evidence only. **No Microsoft 365 tenant was
contacted.** No live acceptance is claimed and no capability changes support
state as a result of this lane.

## Classification

| Item | Prior state | Action taken |
| --- | --- | --- |
| REL-001 Threat model for M365 scope | Planner-only STRIDE model (§4.1..§4.13); the Outlook/reserved surface, cross-application composites and mock-vs-live confusion were unmodelled | New §4.14 with `THR-130`..`THR-136`: premature public exposure of a reserved application, mock evidence presented as live, mailbox/calendar/contact content leakage, cross-application prompt injection, API-surface substitution, unauthorised outbound/write, and unattested live promotion. Each row carries controls, an honest status and residual risk. |
| REL-002 Trust-boundary review | Boundary table stopped at TB-5; the supply chain (already threat-modelled as TB-6) and the application-scope boundary were undocumented | `TB-6 / ARCH-057` (supply chain) and `TB-7 / ARCH-058` (application scope) added, plus `ARCH-059` stating the four application-boundary invariants: registry-derived public projection, separated implementation/live states, most-restrictive inheritance for composites, live evidence required for promotion. |
| REL-003 Privacy/retention for mailbox/calendar/contact content | `PRIV-060` covered Planner-era data classes only | `PRIV-066` declares seven M365 content classes with `none` retention; `PRIV-067` makes retention extension a precondition for new capabilities; `PRIV-068` forbids any content-derived cache/index/embedding; `PRIV-069` binds reserved applications to the strictest rule. |
| REL-004 Container hardening parity | `SEC-109` (resource limits) was `PLANNED`; parity was asserted piecemeal across unrelated tests | `mem_limit`/`pids_limit` added to both services; `SEC-109` is no longer PLANNED; new §9a parity matrix (13 controls × 2 services) machine-checked against `docker-compose.yml` and both Dockerfiles. |
| REL-005 Egress-control acceptance | Allowlist existed but permitted `graph.microsoft.com`, contradicting ADR-008 | New `API_SURFACE_DENIED` decision: Graph hosts and `api.office.com` are denied even though their parent suffix is allowlisted. Documented as `SEC-116`; accepted by a suite that includes the negative control proving the denied hosts *would* otherwise have been allowed. |

## Real defect found and fixed

Before this lane the browser egress policy returned
`MICROSOFT_M365_ALLOWLIST` for `https://graph.microsoft.com/v1.0/me`, because
`microsoft.com` is an allowed suffix. ADR-008 declares Graph a non-dependency
and the whole capability model is browser/UI-evidence based, so the policy
permitted the exact substrate substitution the architecture forbids. The
allowlist is now deny-first for API surfaces (`THR-134`, `SEC-116`).

## Files

- `docs/threat-model.md` (§4.14, `THR-130`..`THR-136`)
- `docs/architecture.md` (`TB-6`/`ARCH-057`, `TB-7`/`ARCH-058`, `ARCH-059`, index range)
- `docs/privacy-boundary.md` (`PRIV-066`..`PRIV-069`, index range)
- `docs/security.md` (`SEC-109` de-PLANNED, §9a parity matrix, `SEC-116`, index range)
- `docker-compose.yml` (`mem_limit`/`pids_limit` on both services)
- `src/m365_browser_worker/egress.py` (`API_SURFACE_DENIED`)
- `tests/test_rel_001_003_threat_privacy_model.py` (new, 13 tests)
- `tests/test_rel_004_container_hardening_parity.py` (new, 12 tests)
- `tests/test_rel_005_egress_control_acceptance.py` (new, 14 tests)

No feature module, no tool registration and no capability definition was
modified. The public projection remains exactly the 17 Planner `READ` tools.

## Validation

| Gate | Result |
| --- | --- |
| `compileall src tests scripts` | PASS |
| `ruff check .` | PASS |
| `mypy` | PASS |
| `scripts/check_docs.py` | PASS (0 errors, 0 warnings) |
| `scripts/check_contracts.py` | PASS |
| `scripts/check_policy_metadata.py` | PASS |
| `scripts/check_no_secrets.py` | PASS |
| `scripts/check_base_image_pinning.py` | PASS |
| `scripts/check_execution_index.py` | `EXECUTION_INDEX_OK items=115 active_out=0 max_out=6` |
| `scripts/isolated_acceptance.py` | PASS |
| `pytest` | 1147 passed (baseline on `main` @ 0bd47f7: 1108) |

Negative controls exercised: `test_denied_api_hosts_would_otherwise_have_been_allowed`
asserts each denied host matches an allowed suffix, so removing the deny list
turns the egress suite red rather than silently green; the parity suite fails if
either service loses a limit, a `cap_drop`, a tmpfs flag or a digest pin.

## Limitations

- All evidence is repository/mock/isolated. **No tenant, no browser session, no
  authenticated request.**
- REL-013..REL-016 (Outlook read-only, safe-write, outbound mail, calendar
  write live acceptance) are **not** attempted and remain blocked on live
  authenticated tenant evidence.
- Outlook stays `RESERVED`, `LIVE UNOBSERVED`, with zero public tools.
  XAPP-029 stays `DEFERRED`.
- `SEC-070`/`SEC-071` (service-to-service and control-plane caller
  authentication) remain `PLANNED`; this lane did not change them.
- The compose resource limits are declared, not runtime-measured: no container
  was started in this lane.
