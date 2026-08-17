"""FastAPI browser worker. Mock mode by default; live mode fails closed."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from m365_browser_worker.account_context import (
    AccountContext,
    live_account_context,
    unverified_account_context,
)
from m365_browser_worker.apps.planner import PlannerWorkerAdapter
from m365_browser_worker.auth_bootstrap import AuthBootstrapGuard
from m365_browser_worker.bootstrap_discovery import (
    DISCOVER_EMAIL_OPERATION,
    DISCOVER_PASSWORD_OPERATION,
    EMAIL_DISCOVERY_KEYS,
    PASSWORD_DISCOVERY_KEYS,
    DiscoveryError,
    KeyDiscovery,
    discover_key,
)
from m365_browser_worker.bootstrap_navigation import (
    AUTH_BEGIN_EMAIL_STAGE_OPERATION,
    AUTH_BEGIN_SIGNIN_OPERATION,
    AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
    MICROSOFT_AUTH_TARGET_CLASS,
    PLANNER_WEB_TARGET_CLASS,
    evaluate_microsoft_auth_target,
    is_loopback_peer,
)
from m365_browser_worker.collect_observation import (
    COLLECT_OBSERVATION_EMAIL_KEYS,
    COLLECT_OBSERVATION_FRAGMENT_IDS,
    COLLECT_OBSERVATION_PASSWORD_KEYS,
    collect_running_observation,
)
from m365_browser_worker.executor import ProfileSerializedExecutor
from m365_browser_worker.lifecycle import browser_lifespan
from m365_browser_worker.live_attestation_probe import (
    PLANNER_SURFACE_FRAGMENT_IDS,
    PROBE_PLANNER_SURFACE_OPERATION,
    LiveProbeError,
    probe_all_live_surface_fragments,
)
from m365_browser_worker.operator_signin import (
    validate_email_stage_input,
    validate_signin_input,
)
from m365_browser_worker.protocol import (
    WorkerOperation,
    WorkerRequestEnvelope,
    WorkerResponseEnvelope,
)
from m365_browser_worker.protocol_negotiation import (
    ProtocolNegotiationRequest,
    ProtocolNegotiationResponse,
    ProtocolNegotiator,
)
from m365_browser_worker.readiness import WorkerReadiness, evaluate_worker_readiness
from m365_browser_worker.session_broker import SessionCapabilityBroker
from m365_browser_worker.signin_surface import (
    AUTH_DIAGNOSE_OPERATION,
    AUTH_KMSI_OPERATION,
    AUTH_METHOD_SELECTION_OPERATION,
    AUTH_RESOLVE_OPERATION,
    SigninSurfaceKind,
)
from m365_browser_worker.worker_errors import project_worker_error
from m365_mcp.capability_registry import default_capability_registry
from planner_mcp.auth import AuthContext, AuthState
from planner_mcp.errors import (
    PlannerMcpError,
    PolicyDenied,
    ProtocolIncompatible,
    WorkerUnavailable,
)
from planner_mcp.logging_setup import configure_logging
from planner_mcp.ui_contract import full_contract_set_digest, load_status

from . import __version__, mock_data
from .browser import BrowserConfig, PersistentBrowser
from .observation import observe_signin_state


def _mode() -> str:
    return os.getenv("PLANNER_MODE", "mock").lower()


async def _operator_submit_surface_allowed(worker_browser: Any) -> bool:
    """AUTH-112 combined-form escape hatch for operator-submit (minimal, fail-closed).

    Returns True iff credentials may be applied, using the NARROWEST possible OR:

    * the pre-email sign-in surface was deterministically resolved to
      EMAIL_ENTRY (incumbent ``resolve-signin-surface`` latch), OR
    * the live Microsoft authentication page structurally proves the OBSERVED
      combined Entra ID form is uniquely present (exactly one of each fixed
      control id: ``#i0116``, ``#i0118``, ``#idSIButton9``), which means the
      combined-form submit path is safe and deterministic.

    Any detection error, a non-unique control, or an absent control returns
    False so the incumbent sequential EMAIL_ENTRY gate still applies (fail
    closed). The optical/textual EMAIL_ENTRY resolution is NEVER relaxed: when
    the combined form is not structurally proven, the caller must still resolve
    the textual EMAIL_ENTRY surface before submitting.
    """
    if worker_browser.signin_surface_resolved():
        return True
    try:
        page = worker_browser._require_single_auth_page()
    except Exception:  # noqa: BLE001 - fail closed: no page -> no combined proof
        return False
    try:
        from m365_browser_worker.operator_signin import (
            detect_combined_signin_form,
        )
    except Exception:  # noqa: BLE001 - import failure must not widen the gate
        return False
    try:
        return bool(await detect_combined_signin_form(page))
    except Exception:  # noqa: BLE001 - detection failure -> fall through to gate
        return False


def _is_mock() -> bool:
    return _mode() != "live"


def create_app(
    browser: PersistentBrowser | None = None,
    *,
    profile_viability_provider: Callable[[], bool] | None = None,
    auth_state_provider: Callable[[], AuthState] | None = None,
    account_context_provider: Callable[[], AccountContext] | None = None,
    live_reader: Callable[[], Any] | None = None,
    live_read_path_provider: Callable[[], bool] | None = None,
    broker: SessionCapabilityBroker | None = None,
    executor: ProfileSerializedExecutor | None = None,
    protocol_negotiator: ProtocolNegotiator | None = None,
    broker_viability_provider: Callable[[], bool] | None = None,
    protocol_compatibility_provider: Callable[[], bool] | None = None,
    lock_viability_provider: Callable[[], bool] | None = None,
) -> FastAPI:
    """Build the worker app with separate liveness and live-readiness semantics."""
    configure_logging(os.getenv("PLANNER_LOG_LEVEL", "INFO"))
    worker_browser = browser or PersistentBrowser(BrowserConfig.from_env())
    profile_executor = executor or ProfileSerializedExecutor()
    worker_protocol = protocol_negotiator or ProtocolNegotiator()
    profile_usable = profile_viability_provider or (lambda: False)
    current_auth_state = auth_state_provider or (
        lambda: AuthState.AUTHENTICATED if _is_mock() else AuthState.UNKNOWN
    )
    current_account_context = account_context_provider or unverified_account_context
    session_broker = broker or SessionCapabilityBroker(
        browser=worker_browser,
        registry=default_capability_registry(),
        auth_state_provider=lambda: live_auth_state(),
        account_context_provider=lambda: live_account_context(worker_browser),
        live_read_path_provider=live_read_path_provider
        or (
            lambda: (
                worker_browser.started
                and worker_browser.is_dedicated_persistent_profile()
                and worker_browser.planner_web_surface_present()
            )
        ),
    )
    broker_viable = broker_viability_provider or (lambda: session_broker.viable)
    protocol_compatible = protocol_compatibility_provider or (lambda: worker_protocol.compatible)
    lock_viable = lock_viability_provider or (lambda: profile_executor.viable)
    auth_bootstrap_guard = AuthBootstrapGuard(
        browser_started_provider=lambda: worker_browser.started,
        dedicated_profile_provider=worker_browser.is_dedicated_persistent_profile,
        approved_auth_origin_provider=worker_browser.auth_origin_approved,
        fully_attested_provider=lambda: load_status().attested,
        strict_live_guard=worker_browser.ensure_live_allowed,
        # OPERATION-SPECIFIC: only ``auth_bootstrap_open_planner_web`` may be
        # admitted from the fixed Planner Web surface, because AUTH-116 reuses
        # the restored Planner Web tab of the dedicated persistent profile. The
        # predicate is the existing closed single-page classification; it adds
        # no auth origin and relaxes no other operation.
        planner_web_bootstrap_source_provider=getattr(
            worker_browser, "planner_web_surface_present", lambda: False
        ),
    )
    app = FastAPI(
        title="planner-browser-worker",
        version=__version__,
        lifespan=browser_lifespan(worker_browser),
    )
    # Internal ownership only; no generic executor/browser endpoint is exposed.
    app.state.profile_executor = profile_executor
    app.state.protocol_negotiator = worker_protocol
    # In-memory observation context. Maintained separately from the worker's
    # contract-attested auth signal; ambiguous UNKNOWN readings never corrupt a
    # previously established (e.g. AUTHENTICATED) context.
    app.state.observation_context = AuthContext()

    @app.exception_handler(RequestValidationError)
    async def sanitized_validation_error(
        _request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        """Never echo malformed request values back across the worker boundary."""
        return JSONResponse(
            status_code=422,
            content={
                "error": "INVALID_REQUEST",
                "message": "Request validation failed",
            },
        )

    def current_readiness() -> WorkerReadiness:
        ui = load_status()
        return evaluate_worker_readiness(
            browser_started=worker_browser.started,
            profile_usable=profile_usable(),
            auth_state=current_auth_state(),
            ui_contract_attested=ui.attested,
            broker_viable=broker_viable(),
            protocol_compatible=protocol_compatible(),
            lock_viable=lock_viable(),
        )

    def live_guard(operation: str) -> None:
        if _is_mock():
            return
        try:
            worker_browser.ensure_live_allowed(operation)
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

    def capability_guard(capability: str) -> None:
        if _is_mock():
            return
        try:
            session_broker.authorize(application="planner", capability=capability)
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

    def planner_live_reader() -> Any:
        """Return the authenticated live Planner Web page, or None fail-closed.

        Only the dedicated persistent professional profile positioned on the fixed
        Planner Web surface is ever returned. No other page (neutral placeholder,
        auth interstitial, unrelated tab) is accepted, so a read can only ever act
        on the verified board context.
        """
        if live_reader is not None:
            # Injected read path (e.g. tests or an alternate browser harness):
            # the caller is responsible for returning a verified page or None.
            return live_reader()
        if (
            not worker_browser.started
            or not worker_browser.is_dedicated_persistent_profile()
            or not worker_browser.planner_web_surface_present()
        ):
            return None
        for candidate in worker_browser._context.pages:
            if str(candidate.url) and worker_browser.planner_web_surface_present():
                return candidate
        return None

    planner_adapter = PlannerWorkerAdapter(
        is_mock=_is_mock,
        capability_guard=capability_guard,
        data_provider=mock_data,
        live_reader=planner_live_reader,
    )
    app.state.planner_adapter = planner_adapter

    @app.get("/livez")
    async def livez() -> dict[str, object]:
        return {"alive": True, "version": __version__}

    @app.get("/readyz")
    async def readyz() -> JSONResponse:
        readiness = current_readiness()
        return JSONResponse(
            status_code=200 if readiness.ready else 503,
            content=readiness.to_dict(),
        )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        ui = load_status()
        readiness = current_readiness()
        return {
            "ok": True,
            "mode": _mode(),
            "version": __version__,
            "ui_contract_version": ui.version,
            # Full-set digest: the EXACT value the live attestation observation
            # collector binds (contract_set.digest() over every fragment). This
            # must match what /auth/bootstrap/collect-observation reports, so
            # observations never fail with CONTRACT_SET_DIGEST_MISMATCH.
            "ui_contract_set_digest": full_contract_set_digest(),
            "ui_contract_attested": ui.attested,
            "live_ready": readiness.ready,
        }

    @app.get("/protocol")
    async def protocol_status() -> dict[str, object]:
        return worker_protocol.snapshot()

    @app.post("/protocol/negotiate", response_model=ProtocolNegotiationResponse)
    async def protocol_negotiate(
        request: ProtocolNegotiationRequest,
    ) -> ProtocolNegotiationResponse:
        return worker_protocol.negotiate(request.supported_versions)

    def bootstrap_guard(operation: str) -> None:
        if _is_mock():
            return
        try:
            auth_bootstrap_guard.guard(operation)
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

    def begin_signin_guard(operation: str) -> None:
        """Dedicated fail-closed guard for the begin-signin endpoint ONLY.

        This is intentionally separate from ``AuthBootstrapGuard`` and the
        ``/auth/bootstrap/navigate`` path. It requires:

        * a started live browser (mock short-circuits via ``_is_mock``);
        * the dedicated persistent professional profile;
        * the present page set to be a permitted begin-signin source
          (Planner Web host, neutral placeholder, or an approved Microsoft
          authentication origin) via ``PersistentBrowser.begin_signin_source_permitted``;
        * the fixed Microsoft auth target to pass the closed egress policy.

        It does NOT relax ``AuthBootstrapGuard`` or the ``/auth/status`` /
        ``/auth/start`` / ``/auth/resume`` behavior. Any failure fails closed
        with ``503``.
        """
        if _is_mock():
            return
        if not worker_browser.started:
            raise HTTPException(
                status_code=503,
                detail=WorkerUnavailable(
                    "begin sign-in requires a started live browser",
                    operation=operation,
                ).to_dict(),
            )
        if not worker_browser.is_dedicated_persistent_profile():
            raise HTTPException(
                status_code=503,
                detail=PolicyDenied(
                    "begin sign-in requires the dedicated persistent professional browser profile",
                    operation=operation,
                ).to_dict(),
            )
        if not worker_browser.begin_signin_source_permitted():
            raise HTTPException(
                status_code=503,
                detail=PolicyDenied(
                    "begin sign-in requires the dedicated professional profile to "
                    "be positioned on Planner Web, a neutral placeholder, or an "
                    "approved Microsoft authentication origin",
                    operation=operation,
                ).to_dict(),
            )
        target_decision = evaluate_microsoft_auth_target()
        if not target_decision.allowed:
            raise HTTPException(
                status_code=503,
                detail=PolicyDenied(
                    "begin sign-in Microsoft auth target denied by closed egress policy",
                    operation=operation,
                    reason=target_decision.reason,
                ).to_dict(),
            )

    def live_auth_state() -> AuthState:
        # Derive the LIVE auth state from trusted runtime attestation evidence
        # rather than a hardcoded constant. ``bootstrap_guard`` already ran
        # first (fail-closed), so reaching here means the narrowly-scoped
        # authentication bootstrap path is permitted. Once ``common.auth`` is
        # legitimately attested (PR/evidence based, mirrored by the guard's own
        # auth-attested provider) the professional session is AUTHENTICATED;
        # before attestation the bootstrap state remains UNKNOWN.
        if worker_browser.common_auth_attested():
            return AuthState.AUTHENTICATED
        return AuthState.UNKNOWN

    @app.get("/auth/status")
    async def auth_status() -> dict[str, Any]:
        if _is_mock():
            return {"state": AuthState.AUTHENTICATED.value, "mode": "mock"}
        # Narrowed pre-attestation guard: authentication bootstrap may proceed
        # only on the dedicated professional profile at an approved auth origin.
        bootstrap_guard("auth_status")
        return {"state": live_auth_state().value, "mode": "live"}

    @app.get("/auth/start")
    async def auth_start() -> dict[str, Any]:
        if _is_mock():
            expires = (datetime.now(UTC) + timedelta(seconds=120)).isoformat()
            return {
                "state": AuthState.MFA_REQUIRED.value,
                "mfa": {
                    "mfa_number": "42",
                    "operation_id": "mock-op-1",
                    "service": "microsoft-entra-id",
                    "description": "Sign in to Microsoft Planner",
                    "expires_at": expires,
                    "approval_channel": "microsoft_authenticator",
                },
            }
        bootstrap_guard("auth_start")
        return {"state": live_auth_state().value}

    @app.get("/auth/resume")
    async def auth_resume() -> dict[str, Any]:
        if _is_mock():
            return {"state": AuthState.AUTHENTICATED.value, "mode": "mock"}
        bootstrap_guard("auth_resume")
        return {"state": live_auth_state().value}

    @app.post("/auth/bootstrap/navigate")
    async def auth_bootstrap_navigate(request: Request) -> dict[str, Any]:
        """OPERATOR-ONLY loopback navigation to the FIXED Planner Web target.

        Security shape (see docs/authentication-and-mfa.md AUTH-094):

        * NOT an MCP tool, absent from every tool/capability/agent-card catalog,
          absent from the typed ``/operations`` dispatcher and never proxied by
          the control plane;
        * admission is a SOCKET-level loopback check on ``request.client.host``.
          ``X-Forwarded-For``/``X-Real-IP``/``Forwarded`` are never consulted, so
          a container on the Docker network cannot spoof loopback;
        * takes NO parameters: any query string and any non-empty body are
          rejected. The destination is a fixed production constant;
        * reuses the narrow ``AuthBootstrapGuard`` (browser started + dedicated
          persistent professional profile + neutral/approved origin) and the
          closed egress policy; both fail closed;
        * returns only a sanitized closed state. No URL, DOM, page text, cookie,
          token, UPN, tenant id, Planner/mailbox data or browser handle.
        """
        client = request.client
        if not is_loopback_peer(client.host if client else None):
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "Resource not available"},
            )
        if request.url.query:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No parameters are accepted"},
            )
        if await request.body():
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No request body is accepted"},
            )

        bootstrap_guard(AUTH_BOOTSTRAP_NAVIGATE_OPERATION)

        if _is_mock():
            return {
                "ok": True,
                "target_class": PLANNER_WEB_TARGET_CLASS,
                "auth_state": AuthState.UNKNOWN.value,
            }

        try:
            await worker_browser.navigate_auth_bootstrap()
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

        return {
            "ok": True,
            "target_class": PLANNER_WEB_TARGET_CLASS,
            "auth_state": live_auth_state().value,
        }

    @app.post("/auth/bootstrap/begin-signin")
    async def auth_bootstrap_begin_signin(request: Request) -> dict[str, Any]:
        """OPERATOR-ONLY loopback begin-signin to the FIXED Microsoft auth target.

        Second step of the two-step operator flow. Security shape (see
        docs/authentication-and-mfa.md AUTH-096):

        * NOT an MCP tool, absent from every tool/capability/agent-card catalog,
          absent from the typed ``/operations`` dispatcher and never proxied by
          the control plane;
        * admission is a SOCKET-level loopback check on ``request.client.host``.
          ``X-Forwarded-For``/``X-Real-IP``/``Forwarded`` are never consulted, so
          a container on the Docker network cannot spoof loopback;
        * takes NO parameters: any query string and any non-empty body are
          rejected. The destination is a fixed production constant;
        * uses a DEDICATED begin-signin guard (browser started + dedicated
          persistent professional profile + permitted source class), NOT the
          generic ``AuthBootstrapGuard`` and NOT the ``/auth/bootstrap/navigate``
          path. The existing ``auth_status``/``auth_start``/``auth_resume`` and
          navigate behavior is unchanged;
        * requires BOTH existing browser egress ALLOW on the fixed Microsoft auth
          target and existing auth-origin approval for that target. There is no
          URL input, so Graph/API/non-HTTPS targets are impossible;
        * navigates exactly once, no retry. No DOM/content exposure;
        * AUTH-113 landing gate: returns success ONLY after the navigated page
          has actually established an approved Microsoft authentication origin.
          A page still on ``about:blank`` / a neutral placeholder / a
          non-approved origin (aborted or blocked redirect, offline target, or a
          stale dedicated page) fails closed with ``503 POLICY_DENIED``
          and is NEVER reported as ``target_class:microsoft_auth``;
        * returns only ``{ok:true, target_class:"microsoft_auth", auth_state}``.
          No URL, DOM, page text, cookie, token, UPN, tenant id, Planner/mailbox
          data or browser handle.
        """
        client = request.client
        if not is_loopback_peer(client.host if client else None):
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "Resource not available"},
            )
        if request.url.query:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No parameters are accepted"},
            )
        if await request.body():
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No request body is accepted"},
            )

        begin_signin_guard(AUTH_BEGIN_SIGNIN_OPERATION)

        if _is_mock():
            return {
                "ok": True,
                "target_class": MICROSOFT_AUTH_TARGET_CLASS,
                "auth_state": AuthState.UNKNOWN.value,
            }

        try:
            await worker_browser.begin_auth_signin()
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

        return {
            "ok": True,
            "target_class": MICROSOFT_AUTH_TARGET_CLASS,
            "auth_state": live_auth_state().value,
        }

    def begin_email_stage_guard(operation: str) -> None:
        """Dedicated fail-closed guard for the pre-attestation email stage (AUTH-106).

        This is intentionally separate from ``AuthBootstrapGuard``, the
        ``/auth/bootstrap/navigate`` path, the ``begin_signin_guard``, and the
        full-attestation ``submit_operator_signin`` gate. It is the minimal
        headless-safe primitive that breaks the attestation bootstrap deadlock
        left after the GUI/noVNC/X11 handoff was removed (PR #614): it must run
        BEFORE ``common.auth`` is attested, so it does NOT require attestation.
        It requires ONLY:

        * a started live browser (mock short-circuits via ``_is_mock``);
        * the dedicated persistent professional profile;
        * the live context positioned on an approved Microsoft authentication
          origin (or no page yet) via ``PersistentBrowser.auth_origin_approved``;
        * the email field only — no password, no sign-in submit.

        It NEVER relaxes ``AuthBootstrapGuard`` or the
        ``/auth/status`` / ``/auth/start`` / ``/auth/resume`` behavior, and it
        does NOT widen the path to ``submit_operator_signin`` (which still
        requires full attestation). Any failure fails closed with ``503``.
        """
        if _is_mock():
            return
        if not worker_browser.started:
            raise HTTPException(
                status_code=503,
                detail=WorkerUnavailable(
                    "email stage requires a started live browser",
                    operation=operation,
                ).to_dict(),
            )
        if not worker_browser.is_dedicated_persistent_profile():
            raise HTTPException(
                status_code=503,
                detail=PolicyDenied(
                    "email stage requires the dedicated persistent professional "
                    "browser profile",
                    operation=operation,
                ).to_dict(),
            )
        if not worker_browser.auth_origin_approved():
            raise HTTPException(
                status_code=503,
                detail=PolicyDenied(
                    "email stage requires the page to be on an approved "
                    "Microsoft authentication origin",
                    operation=operation,
                ).to_dict(),
            )

    @app.post("/auth/bootstrap/begin-email")
    async def auth_bootstrap_begin_email(request: Request) -> dict[str, Any]:
        """OPERATOR-ONLY loopback pre-attestation email stage (AUTH-106).

        Minimal headless-safe replacement for the removed GUI/noVNC/X11 handoff.
        It fills ONLY the operator's professional email field and clicks ONLY the
        Microsoft "Next" control to advance the live Microsoft authentication page
        to the password step, so the four ``common.auth`` progression selectors
        become observable for attestation. Security shape:

        * NOT an MCP tool; absent from every tool/capability/agent-card catalog,
          the typed ``/operations`` dispatcher and the control-plane worker client;
        * SOCKET-level loopback admission only (``127.0.0.1``/``::1``); proxy
          headers are never consulted; a Docker-network peer gets ``404``;
        * accepts EXACTLY the closed ``{email}`` contract
          (``validate_email_stage_input``). Any extra/unknown key (including
          ``password``), or a missing key, is rejected with ``400`` and never
          reaches the browser;
        * does NOT require ``common.auth`` to be attested — this is intentional,
          so attestation can actually be collected. It does NOT widen the
          attested ``submit_operator_signin`` path (which still requires full
          attestation before any password is typed);
        * the browser applies ONLY the email field and clicks ONLY Next via
          fail-closed ``common_auth_locator_plan`` resolution; it never types the
          password and never clicks Sign in. No URL/selector/Graph surface is
          reachable;
        * no MFA automation; the human still completes MFA in Microsoft
          Authenticator. Returns only ``{ok, auth_state}``. No email value, URL,
          DOM, cookie, token, UPN, tenant id or browser handle is ever returned.
        """
        client = request.client
        if not is_loopback_peer(client.host if client else None):
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "Resource not available"},
            )
        if request.url.query:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No parameters are accepted"},
            )

        try:
            raw = await request.json()
        except Exception:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "Body must be a JSON object"},
            ) from None
        try:
            stage = validate_email_stage_input(raw)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": str(exc)},
            ) from exc

        begin_email_stage_guard(AUTH_BEGIN_EMAIL_STAGE_OPERATION)

        if _is_mock():
            return {"ok": True, "auth_state": AuthState.UNKNOWN.value}

        try:
            await worker_browser.begin_email_stage(stage.email)
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

        # The email stage only advances to the password step; it is not
        # authentication. The human still completes MFA in Microsoft Authenticator.
        return {"ok": True, "auth_state": AuthState.UNKNOWN.value}

    def resolve_surface_guard(operation: str) -> None:
        """Dedicated fail-closed guard for the operator sign-in surface resolver (AUTH-109).

        Mirrors ``begin_email_stage_guard``: it is intentionally separate from
        ``AuthBootstrapGuard``, the ``/auth/bootstrap/navigate`` path, the
        ``begin_signin_guard``, and the full-attestation ``submit_operator_signin``
        gate. It runs BEFORE ``common.auth`` is attested (so the email surface can
        be reached for attestation) and requires ONLY:

        * a started live browser (mock short-circuits via ``_is_mock``);
        * the dedicated persistent professional profile;
        * the live context positioned on an approved Microsoft authentication
          origin (or no page yet) via ``PersistentBrowser.auth_origin_approved``;
        * exactly one open auth page (enforced by the browser primitive).

        It NEVER relaxes the other guards and does NOT widen the path to
        ``submit_operator_signin``. Any failure fails closed with ``503``.
        """
        if _is_mock():
            return
        if not worker_browser.started:
            raise HTTPException(
                status_code=503,
                detail=WorkerUnavailable(
                    "sign-in surface resolution requires a started live browser",
                    operation=operation,
                ).to_dict(),
            )
        if not worker_browser.is_dedicated_persistent_profile():
            raise HTTPException(
                status_code=503,
                detail=PolicyDenied(
                    "sign-in surface resolution requires the dedicated persistent "
                    "professional browser profile",
                    operation=operation,
                ).to_dict(),
            )
        if not worker_browser.auth_origin_approved():
            raise HTTPException(
                status_code=503,
                detail=PolicyDenied(
                    "sign-in surface resolution requires the page to be on an "
                    "approved Microsoft authentication origin",
                    operation=operation,
                ).to_dict(),
            )

    @app.post("/auth/bootstrap/resolve-signin-surface")
    async def auth_bootstrap_resolve_signin_surface(request: Request) -> dict[str, Any]:
        """OPERATOR-ONLY loopback deterministic pre-email surface resolver (AUTH-109).

        Minimal headless-safe resolver for the intermediate Microsoft Entra ID
        sign-in surface (account chooser / "use another account" prompt) that can
        appear BEFORE the email-entry field, blocking the ``begin-email`` and
        ``discover-email`` paths. It forces the email-entry surface by clicking
        ONLY the fixed "use another account" control, never selecting a cached
        identity. Security shape:

        * NOT an MCP tool; absent from every tool/capability/agent-card catalog,
          the typed ``/operations`` dispatcher and the control-plane worker client;
        * SOCKET-level loopback admission only (``127.0.0.1``/``::1``); proxy
          headers are never consulted; a Docker-network peer gets ``404``;
        * POST only with NO body and NO parameters; any body or query string is
          rejected with ``400`` and never reaches the browser;
        * does NOT require ``common.auth`` to be attested — this is intentional,
          so the email surface can be reached for attestation. It does NOT widen
          the attested ``submit_operator_signin`` path (which still requires full
          attestation before any credential is typed);
        * the browser applies ONLY the fixed "use another account" action and
          never types, never selects a cached account, never clicks Sign in, and
          never navigates by URL/selector. No URL/selector/Graph surface is
          reachable;
        * fails closed on any non-deterministic surface (pick-an-account,
          stay-signed-in, consent, method selection, error, ambiguous, unknown):
          it never guesses a surface or selects an identity;
        * returns only ``{ok, auth_state, surface}`` where ``surface`` is one of
          the closed ``EMAIL_ENTRY`` / ``ACCOUNT_CHOOSER`` /
          ``USE_ANOTHER_ACCOUNT_PROMPT`` terminal classifications. No URL, DOM,
          page text, cookie, token, UPN, tenant id, account identifier or browser
          handle is ever returned.
        """
        client = request.client
        if not is_loopback_peer(client.host if client else None):
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "Resource not available"},
            )
        if request.url.query:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No parameters are accepted"},
            )
        if await request.body():
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No request body is accepted"},
            )

        resolve_surface_guard(AUTH_RESOLVE_OPERATION)

        if _is_mock():
            return {
                "ok": True,
                "auth_state": AuthState.UNKNOWN.value,
                "surface": SigninSurfaceKind.UNKNOWN.value,
            }

        try:
            await worker_browser.resolve_signin_surface()
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

        # A successful resolution leaves the page on (or advanceable to) the
        # email-entry surface. The human still completes sign-in + MFA in
        # Microsoft Authenticator. Report the closed post-resolution classification.
        return {
            "ok": True,
            "auth_state": AuthState.UNKNOWN.value,
            "surface": SigninSurfaceKind.EMAIL_ENTRY.value,
        }

    @app.post("/auth/bootstrap/resolve-kmsi-surface")
    async def auth_bootstrap_resolve_kmsi_surface(request: Request) -> dict[str, Any]:
        """OPERATOR-ONLY loopback deterministic KMSI surface resolver (AUTH-114).

        Dismisses the credential-free, MFA-free post-password Microsoft
        ``Stay signed in?`` (KMSI) interstitial that can block the post-sign-in
        progression. Security shape (identical family to AUTH-109):

        * NOT an MCP tool; absent from every tool/capability/agent-card catalog,
          the typed ``/operations`` dispatcher and the control-plane worker client;
        * SOCKET-level loopback admission only (``127.0.0.1``/``::1``); proxy
          headers are never consulted; a Docker-network peer gets ``404``;
        * POST only with NO body and NO parameters; any body or query string is
          rejected with ``400`` and never reaches the browser;
        * the browser applies ONLY the fixed KMSI decline control, matched from a
          CLOSED exact-label set and ONLY when strictly unique. It never types a
          credential, never selects a cached identity, never clicks Sign in, and
          never navigates by URL/selector;
        * fails closed with ``503 POLICY_DENIED`` on any non-KMSI surface or an
          absent/ambiguous control, carrying only the sanitized closed
          terminal-surface enum;
        * returns only ``{ok, surface}``. No URL, DOM, page text, cookie, token,
          UPN, tenant id, account identifier or browser handle is ever returned.
        """
        client = request.client
        if not is_loopback_peer(client.host if client else None):
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "Resource not available"},
            )
        if request.url.query:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No parameters are accepted"},
            )
        if await request.body():
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No request body is accepted"},
            )

        resolve_surface_guard(AUTH_KMSI_OPERATION)

        if _is_mock():
            return {"ok": True, "surface": SigninSurfaceKind.UNKNOWN.value}

        try:
            surface = await worker_browser.resolve_kmsi_surface()
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

        return {"ok": True, "surface": surface.value}

    @app.post("/auth/bootstrap/resolve-method-selection-surface")
    async def auth_bootstrap_resolve_method_selection_surface(
        request: Request,
    ) -> dict[str, Any]:
        """OPERATOR-ONLY loopback deterministic METHOD_SELECTION surface resolver
        (AUTH-115).

        Resolves the credential-free, MFA-free Microsoft Entra ID method-
        selection interstitial that can block progression with a verification-
        method chooser, by clicking ONLY the fixed Microsoft Authenticator
        approval control (matched from a CLOSED exact-label set and ONLY when
        strictly unique across the entire closed label set AND both button/link
        roles). Security shape (identical family to AUTH-114):

        * NOT an MCP tool; absent from every tool/capability/agent-card catalog,
          the typed ``/operations`` dispatcher and the control-plane worker client;
        * SOCKET-level loopback admission only (``127.0.0.1``/``::1``); proxy
          headers are never consulted; a Docker-network peer gets ``404``;
        * POST only with NO body and NO parameters; any body or query string is
          rejected with ``400`` and never reaches the browser;
        * the browser applies ONLY the fixed Microsoft Authenticator approval
          control, matched from a CLOSED exact-label set and ONLY when the global
          candidate count across the entire closed set equals exactly one. It
          never types a credential, never selects a cached identity, never clicks
          Sign in, and never navigates by URL/selector;
        * fails closed with ``503 POLICY_DENIED`` on any non-METHOD_SELECTION
          surface or an absent/ambiguous control, carrying only the sanitized
          closed terminal-surface enum;
        * returns only ``{ok, surface}``. No URL, DOM, page text, cookie, token,
          UPN, tenant id, account identifier or browser handle is ever returned.
        """
        client = request.client
        if not is_loopback_peer(client.host if client else None):
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "Resource not available"},
            )
        if request.url.query:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No parameters are accepted"},
            )
        if await request.body():
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No request body is accepted"},
            )

        resolve_surface_guard(AUTH_METHOD_SELECTION_OPERATION)

        if _is_mock():
            return {"ok": True, "surface": SigninSurfaceKind.UNKNOWN.value}

        try:
            surface = await worker_browser.resolve_method_selection_surface()
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

        return {"ok": True, "surface": surface.value}

    @app.get("/auth/bootstrap/diagnose-signin-surface")
    async def auth_bootstrap_diagnose_signin_surface(request: Request) -> dict[str, Any]:
        """OPERATOR-ONLY loopback READ-ONLY pre-email surface classifier (AUTH-109-diagnose).

        Deterministic, non-mutating twin of ``/auth/bootstrap/resolve-signin-surface``.
        It reads the bounded visible body text exactly once and returns ONLY the
        closed surface classification (``surface`` + ``email_entry_present``). It
        NEVER clicks, selects an identity, types, navigates, or otherwise changes
        the page. It exists so an operator run can report the exact closed surface
        kind when the mutating resolver would fail closed — without guessing and
        without acting. Security shape:

        * NOT an MCP tool; absent from every tool/capability/agent-card catalog,
          the typed ``/operations`` dispatcher and the control-plane worker client;
        * SOCKET-level loopback admission only (``127.0.0.1``/``::1``); proxy
          headers are never consulted; a Docker-network peer gets ``404``;
        * GET only with NO body and NO parameters; any query string is rejected
          with ``400`` and never reaches the browser;
        * the same guard chain as the resolver (started live browser, dedicated
          persistent professional profile, approved Microsoft authentication
          origin, exactly one open auth page) — any failure fails closed with
          ``503`` and never reads the page;
        * returns only ``{ok, surface, email_entry_present}`` where ``surface`` is
          one of the closed ``SigninSurfaceKind`` values. No URL, DOM, page text,
          cookie, token, UPN, tenant id, account identifier or browser handle is
          ever returned; the resolver's fixed-action transition is NOT exposed.
        """
        client = request.client
        if not is_loopback_peer(client.host if client else None):
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "Resource not available"},
            )
        if request.url.query:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No parameters are accepted"},
            )

        resolve_surface_guard(AUTH_DIAGNOSE_OPERATION)

        if _is_mock():
            return {
                "ok": True,
                "surface": SigninSurfaceKind.UNKNOWN.value,
                "email_entry_present": False,
            }

        try:
            classification = await worker_browser.diagnose_signin_surface()
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

        return {
            "ok": True,
            "surface": classification.kind.value,
            "email_entry_present": classification.email_entry_present,
        }

    @app.post("/auth/bootstrap/operator-submit")
    async def auth_bootstrap_operator_submit(request: Request) -> dict[str, Any]:
        """OPERATOR-ONLY loopback encrypted-store sign-in submit (AUTH-101).

        Third step of the operator flow: apply the two memory-only sign-in fields
        to the already-open Microsoft authentication page. Hardened shape:

        * NOT an MCP tool; absent from every tool/capability/agent-card catalog,
          the typed ``/operations`` dispatcher and the control-plane worker client.
        * SOCKET-level loopback admission only (``127.0.0.1``/``::1``); proxy
          headers are never consulted; a Docker-network peer gets ``404``.
        * The caller is the operator-local ``scripts/operator_auth_login.py`` which
          decrypts two already-provisioned systemd-creds secrets, keeps them
          memory-only, and forwards them through a local stdin/IPC path. The
          worker never reads the encrypted store, never prints values, and never
          places them in argv/env/log/state.
        * The route accepts exactly the closed ``{email, password}`` contract
          (``validate_signin_input``). Any extra/unknown key, or a missing key, is
          rejected with ``400`` and never reaches the browser.
        * No URL/selector/Graph field is accepted. The browser applies ONLY the two
          ``common.auth`` sign-in selectors, resolved from the attested UIContract
          store (no locator guessing). A non-attested ``common.auth`` fails closed
          and types nothing.
        * AUTH-112 surface gate: the pre-email sign-in surface MUST have been
          deterministically resolved to ``EMAIL_ENTRY`` via the operator-only
          ``POST /auth/bootstrap/resolve-signin-surface`` route immediately before
          this one. A direct submit after ``begin-signin`` (which can recreate the
          account chooser) is refused with ``503 SIGNIN_SURFACE_NOT_RESOLVED`` and
          types nothing — this is the canonical fix for the email NO_MATCH bug.
        * There is no submit click: automation never satisfies MFA. The human
          completes MFA in Microsoft Authenticator; the browser observes the state.
        * Returns only ``{ok, auth_state}``. No value, URL, DOM, cookie, token,
          UPN, tenant id or browser handle is ever returned.
        """
        client = request.client
        if not is_loopback_peer(client.host if client else None):
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "Resource not available"},
            )
        if request.url.query:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No parameters are accepted"},
            )

        try:
            raw = await request.json()
        except Exception:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "Body must be a JSON object"},
            ) from None
        try:
            signin = validate_signin_input(raw)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": str(exc)},
            ) from exc

        if not _is_mock() and not worker_browser.common_auth_attested():
            # Fail closed before any browser interaction: the two memory-only
            # fields must never be applied when the common.auth UIContract
            # fragment is not attested. (Route docstring contract.)
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "NOT_ATTESTED",
                    "message": "common.auth UIContract not attested; operator submit refused",
                },
            )

        if not _is_mock() and not await _operator_submit_surface_allowed(worker_browser):
            # AUTH-112: the pre-email sign-in surface MUST have been
            # deterministically resolved to EMAIL_ENTRY before credentials are
            # applied, OR the live Microsoft page MUST structurally prove the
            # OBSERVED combined Entra ID form (exactly one of each fixed control
            # id #i0116 / #i0118 / #idSIButton9). The combined-form structural
            # gate is the minimal fix for the production blocker where the live
            # combined form was rejected before detect_combined_signin_form ran.
            # This is the server-side enforcement of the conductor's
            # resolve->submit ordering; it fails closed on ANY other surface so
            # a direct operator-submit after begin-signin (account-chooser
            # recreation) cannot cause an email NO_MATCH. (Route docstring.)
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "SIGNIN_SURFACE_NOT_RESOLVED",
                    "message": "pre-email sign-in surface not resolved to EMAIL_ENTRY"
                    " and combined Entra ID form not structurally present;"
                    " run resolve-signin-surface first",
                },
            )

        if _is_mock():
            # Mock mode has no live page to fill; report the closed admission only.
            return {"ok": True, "auth_state": AuthState.UNKNOWN.value}

        try:
            await worker_browser.submit_operator_signin(signin)
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

        # Submission is not authentication: the human still completes MFA in
        # Microsoft Authenticator, so the closed state remains UNKNOWN.
        return {"ok": True, "auth_state": AuthState.UNKNOWN.value}

    @app.get("/auth/bootstrap/observe")
    async def auth_bootstrap_observe(request: Request) -> dict[str, Any]:
        """OPERATOR-ONLY loopback live sign-in observation (AUTH-103).

        Reuses the existing safe state machine to read the live sign-in surface
        and expose ONLY a sanitized state. Security shape:

        * NOT an MCP tool, absent from every tool/capability/agent-card catalog,
          the typed ``/operations`` dispatcher and the control-plane worker client;
        * admission is a SOCKET-level loopback check on ``request.client.host``.
          ``X-Forwarded-For``/``X-Real-IP``/``Forwarded`` are never consulted, so
          a Docker-network peer gets ``404``;
        * GET only: takes NO parameters. Any query string is rejected and no
          request body is processed (GET carries none). There is no
          URL/search/selector input;
        * the visible body text is read internally through the narrow
          ``PersistentBrowser.read_visible_body_bounded`` primitive, which only
          fires when the browser is started + dedicated persistent professional
          profile + approved Microsoft authentication origin + exactly one auth
          page. The text is consumed internally for classification and is never
          logged or returned;
        * the existing ``classify_live`` / ``advance_live_auth_state`` logic is
          reused. An ambiguous number match returns ``mfa_number: null`` and the
          state machine never guesses a value; an ambiguous ``UNKNOWN`` reading
          never corrupts the in-memory observation ``AuthContext``;
        * if the live surface has transitioned back to the fixed Planner Web
          surface after sign-in, the endpoint reports ``AUTHENTICATED`` from that
          live surface transition rather than contract attestation;
        * returns only ``{state, mfa_number, mfa_ambiguous}``. No URL, page text,
          DOM, selector, cookie, token, UPN, tenant id or account identifier.
        """
        client = request.client
        if not is_loopback_peer(client.host if client else None):
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "Resource not available"},
            )
        if request.url.query:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No parameters are accepted"},
            )
        if _is_mock():
            # Mock mode has no live page to observe; report the closed admission
            # only without a real surface reading.
            return {
                "state": AuthState.UNKNOWN.value,
                "mfa_number": None,
                "mfa_ambiguous": False,
            }

        context = app.state.observation_context
        try:
            result = await observe_signin_state(worker_browser, context)
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

        return {
            "state": result.state.value,
            "mfa_number": result.mfa_number,
            "mfa_ambiguous": result.mfa_ambiguous,
        }

    def discovery_guard(operation: str) -> Any | None:
        """Fail-closed operator-only discovery preconditions.

        Live mode ONLY. Returns the single open authentication page when every
        precondition holds, otherwise raises a sanitized ``503``:

        * started live browser (mock short-circuits via ``_is_mock``);
        * the dedicated persistent professional profile;
        * an approved Microsoft authentication origin;
        * exactly one open authentication page.

        Precondition failures never leak exception text or selector values.
        """
        if not worker_browser.started:
            raise HTTPException(
                status_code=503,
                detail=WorkerUnavailable(
                    "bootstrap discovery requires a started live browser",
                    operation=operation,
                ).to_dict(),
            )
        if not worker_browser.is_dedicated_persistent_profile():
            raise HTTPException(
                status_code=503,
                detail=PolicyDenied(
                    "bootstrap discovery requires the dedicated persistent "
                    "professional browser profile",
                    operation=operation,
                ).to_dict(),
            )
        if not worker_browser.auth_origin_approved():
            raise HTTPException(
                status_code=503,
                detail=PolicyDenied(
                    "bootstrap discovery requires the page to be on an approved "
                    "Microsoft authentication origin",
                    operation=operation,
                ).to_dict(),
            )
        try:
            return worker_browser._require_single_auth_page()
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

    async def _discover_route(
        request: Request, *, operation: str, keys: tuple[str, ...]
    ) -> dict[str, Any]:
        """Fixed, read-only bootstrap discovery for one hard-coded key scope.

        OPERATOR-ONLY loopback admission only (same socket-level decision as the
        other bootstrap routes). No query string, no request body, no
        caller-supplied selector/stage/url/js. Probes ONLY the fixed keys in
        ``keys`` (email route: email input + next button; password route:
        password input + sign-in button). Returns a sanitized per-key semantic
        result (NO_MATCH / UNIQUE_MATCH / AMBIGUOUS) and, for UNIQUE_MATCH only,
        a value-free structural digest. Never fills/clicks/types/navigates.
        """
        client = request.client
        if not is_loopback_peer(client.host if client else None):
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "Resource not available"},
            )
        if request.url.query:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No parameters are accepted"},
            )

        if _is_mock():
            # Mock mode has no live page to probe; return the fixed closed scope
            # without performing or fabricating any discovery.
            return {"ok": True, "mode": "mock", "scope": list(keys)}

        page = discovery_guard(operation)
        try:
            discoveries: list[KeyDiscovery] = [
                await discover_key(page, selector_key) for selector_key in keys
            ]
        except DiscoveryError as exc:
            raise HTTPException(
                status_code=503,
                detail={"error": "DISCOVERY_FAILED", "message": exc.reason},
            ) from None

        return {
            "ok": True,
            "keys": [discovery.to_dict() for discovery in discoveries],
        }

    @app.get("/auth/bootstrap/discover-email")
    async def auth_bootstrap_discover_email(request: Request) -> dict[str, Any]:
        """OPERATOR-ONLY loopback read-only discovery of the email sign-in keys.

        Fixed scope: ``auth.login_email_input`` and ``auth.login_next_button``.
        Security shape (see the sibling bootstrap routes):

        * NOT an MCP tool, absent from every tool/capability/agent-card catalog,
          the typed ``/operations`` dispatcher and the control-plane worker client;
        * SOCKET-level loopback admission only; proxy headers are never consulted;
        * GET only: any query string is rejected and no request body is processed;
        * the fixed hard-coded key scope is the ONLY thing probed. No
          caller-supplied selector/stage/url/js is accepted;
        * reuses ``common_auth_locator_plan`` (UNVERIFIED_LIVE plans allowed, no
          attestation gate) and the ``locator_runtime`` primitives to resolve and
          count declared candidates only. It NEVER fills, clicks, types, evaluates
          scripts, or navigates;
        * returns only ``{ok, keys:[{selector_key, result, structural_digest?}]}``.
          No locator strategy/value/name, raw counts, DOM/page text, URL, cookie,
          token, UPN, tenant id, or account identifier is ever returned.
        """
        return await _discover_route(
            request,
            operation=DISCOVER_EMAIL_OPERATION,
            keys=EMAIL_DISCOVERY_KEYS,
        )

    @app.get("/auth/bootstrap/discover-password")
    async def auth_bootstrap_discover_password(request: Request) -> dict[str, Any]:
        """OPERATOR-ONLY loopback read-only discovery of the password sign-in keys.

        Fixed scope: ``auth.login_password_input`` and
        ``auth.login_signin_button``. Identical hardened shape to the email
        discovery route (loopback admission, no parameters, fixed key scope,
        reuse of ``common_auth_locator_plan`` + ``locator_runtime``, read-only,
        sanitized per-key results with a value-free structural digest on
        UNIQUE_MATCH only).
        """
        return await _discover_route(
            request,
            operation=DISCOVER_PASSWORD_OPERATION,
            keys=PASSWORD_DISCOVERY_KEYS,
        )

    @app.get("/auth/bootstrap/collect-observation")
    async def auth_bootstrap_collect_observation(request: Request) -> dict[str, Any]:
        """OPERATOR-ONLY loopback read-only 4-key LIVE_UI attestation observation (AUTH-105).

        Minimal primitive that closes the evidence gap documented in
        references/common_auth_four_selector_gate.md: produce a COMPLETE
        AttestationObservation (source=LIVE_UI, current contract_set_digest/campaign
        binding, selector order exactly matching the fragment) from the ALREADY-RUNNING
        dedicated professional browser context, observing EXACTLY the four common.auth
        progression selectors and emitting per-selector result + structural_digest only.

        Security shape (mirrors the sibling bootstrap routes):

        * NOT an MCP tool, absent from every tool/capability/agent-card catalog, the
          typed ``/operations`` dispatcher and the control-plane worker client;
        * SOCKET-level loopback admission only (``127.0.0.1``/``::1``); proxy headers
          are never consulted, so a Docker-network peer gets ``404``;
        * GET only: takes NO parameters. Any query string is rejected and no request
          body is processed. The fixed key scope (4 common.auth selectors, fragment
          order) is the ONLY thing probed — no caller-supplied selector/stage/url/js;
        * reuses ``collect_structural_observation`` exactly, so the produced
          ``AttestationObservation`` is byte-compatible with
          ``scripts/collect_live_attestation_observation.py`` and consumable by
          ``attest_ui_contract.py evaluate``;
        * the injected live probe counts declared candidates via
          ``locator_runtime.build_locator`` only — NO wait, NO fill, NO click, NO
          navigate, NO ``page.evaluate``, and no DOM/URL/value/credential is ever read
          or returned;
        * it NEVER weakens the fail-closed evaluator or the attestation gate: the
          observation is emitted at ``target_level=DISCOVERY`` with ``source=LIVE_UI``,
          so evaluation can only ever yield REVIEW_REQUIRED; it promotes nothing;
        * fails closed (503, no exception text) when the running context is unusable or
          any selector cannot be deterministically counted.
        """
        client = request.client
        if not is_loopback_peer(client.host if client else None):
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "Resource not available"},
            )
        if request.url.query:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No parameters are accepted"},
            )

        if _is_mock():
            # Mock mode has no live context to observe; report the fixed closed scope
            # without performing or fabricating any observation.
            return {
                "ok": True,
                "mode": "mock",
                "fragment_ids": list(COLLECT_OBSERVATION_FRAGMENT_IDS),
                "target_level": "DISCOVERY",
                "source": "LIVE_UI",
                "scope": {
                    "common.auth.email": list(COLLECT_OBSERVATION_EMAIL_KEYS),
                    "common.auth.password": list(COLLECT_OBSERVATION_PASSWORD_KEYS),
                },
            }

        observations: list[dict[str, Any]] = []
        try:
            for fragment_id in COLLECT_OBSERVATION_FRAGMENT_IDS:
                observation = await collect_running_observation(
                    worker_browser,
                    fragment_id=fragment_id,
                    level="DISCOVERY",
                )
                observations.append(observation.canonical_payload())
        except DiscoveryError as exc:
            raise HTTPException(
                status_code=503,
                detail={"error": "OBSERVATION_FAILED", "message": exc.reason},
            ) from None

        return {
            "ok": True,
            "observations": observations,
        }

    @app.get("/auth/bootstrap/probe-planner-surface")
    async def auth_bootstrap_probe_planner_surface(request: Request) -> dict[str, Any]:
        """OPERATOR-ONLY loopback read-only live UI-attestation probe (UI-AUTH-001).

        Minimal primitive that reuses the ALREADY-RUNNING dedicated professional
        browser context to collect sanitized UI-attestation evidence for the
        ``planner.plan-surface`` and ``planner.task-surface`` UIContract fragments
        WITHOUT opening a second persistent Chromium context and WITHOUT
        destroying the already-authenticated Microsoft session.

        Security shape (mirrors ``/auth/bootstrap/collect-observation``):

        * NOT an MCP tool, absent from every tool/capability/agent-card catalog,
          the typed ``/operations`` dispatcher and the control-plane worker client;
        * SOCKET-level loopback admission only (``127.0.0.1``/``::1``); proxy
          headers are never consulted, so a Docker-network peer gets ``404``;
        * GET only: takes NO parameters. Any query string is rejected and no
          request body is processed. The fixed fragment scope
          (``planner.plan-surface`` + ``planner.task-surface``) is the ONLY thing
          probed — no caller-supplied selector/stage/url/js;
        * reuses ``live_attestation_probe`` which counts declared candidates via
          ``locator_runtime.build_locator`` against the single live page only —
          NO wait, NO fill, NO click, NO navigate, NO ``page.evaluate``, and no
          DOM/URL/value/credential is ever read or returned;
        * enforces a positive-broker precondition BEFORE any probe: the dedicated
          persistent professional profile must be positioned on the fixed Planner
          Web surface (the post-MFA landing surface) AND the live auth state must
          be AUTHENTICATED with a VERIFIED account context. Any failure fails
          closed with a sanitized 503 (no exception text). A fragment selector
          with no declared ``locators`` plan is reported as ``NO_LOCATOR`` — never
          fabricated (CORE-019);
        * it NEVER weakens the fail-closed evaluator or the attestation gate: it
          only COLLECTS sanitized evidence (IDs, digests, counts,
          UNIQUE_MATCH/NO_MATCH/AMBIGUOUS/NO_LOCATOR). It promotes nothing and
          writes no contract JSON;
        * fails closed (503, no exception text) when the running context is
          unusable, the surface is ambiguous (multiple pages), or any selector
          cannot be deterministically counted.
        """
        client = request.client
        if not is_loopback_peer(client.host if client else None):
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "Resource not available"},
            )
        if request.url.query:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_REQUEST", "message": "No parameters are accepted"},
            )

        if _is_mock():
            # Mock mode has no live context to observe; report the fixed closed
            # scope without performing or fabricating any observation.
            return {
                "ok": True,
                "mode": "mock",
                "fragment_ids": list(PLANNER_SURFACE_FRAGMENT_IDS),
            }

        # Positive-broker precondition: the live professional session must be
        # AUTHENTICATED on the VERIFIED dedicated profile sitting on the Planner
        # Web surface. These are exactly the conditions proven by the post-MFA
        # broker promotion (AUTH-115); they are the minimum that makes observing
        # the Planner board legitimate. Fail closed otherwise.
        if not (
            worker_browser.started
            and worker_browser.is_dedicated_persistent_profile()
            and worker_browser.planner_web_surface_present()
            and live_auth_state() is AuthState.AUTHENTICATED
            and live_account_context(worker_browser).valid
        ):
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "PROBE_NOT_ALLOWED",
                    "message": "live planner-surface probe requires an authenticated, "
                    "verified session on the Planner Web surface",
                },
            )

        try:
            fragments = await probe_all_live_surface_fragments(worker_browser)
        except LiveProbeError as exc:
            raise HTTPException(
                status_code=503,
                detail={"error": "PROBE_FAILED", "message": exc.reason},
            ) from None

        return {
            "ok": True,
            "operation": PROBE_PLANNER_SURFACE_OPERATION,
            "fragments": fragments,
        }

    @app.get("/auth/session")
    async def auth_session() -> dict[str, Any]:
        return {
            "profile": "professional-isolated",
            "persistent_profile": True,
            "secrets_stored_in_state": False,
            "mode": _mode(),
            "broker": session_broker.snapshot(),
        }

    @app.get("/account/context")
    async def account_context() -> dict[str, Any]:
        if _is_mock():
            return dict(mock_data.ACCOUNT_CONTEXT)
        live_guard("account_context")
        return current_account_context().to_dict()

    @app.get("/account/license")
    async def account_license() -> dict[str, Any]:
        if _is_mock():
            return dict(mock_data.LICENSE)
        live_guard("account_license")
        return {"premium_detected": False, "evidence": "unattested"}

    @app.get("/planner/plans")
    async def plans() -> dict[str, Any]:
        return await planner_adapter.plan_list()

    @app.get("/planner/plans/{plan_id}")
    async def plan_get(plan_id: str) -> dict[str, Any]:
        return await planner_adapter.plan_get(plan_id)

    @app.get("/planner/tasks")
    async def task_list(plan_id: str) -> dict[str, Any]:
        return await planner_adapter.task_list(plan_id)

    @app.get("/planner/tasks/{task_id}")
    async def task_get(task_id: str) -> dict[str, Any]:
        return await planner_adapter.task_get(task_id)

    @app.get("/planner/plans/{plan_id}/snapshot")
    async def snapshot(plan_id: str) -> dict[str, Any]:
        return await planner_adapter.project_snapshot(plan_id)

    async def dispatch_semantic_operation(request: WorkerRequestEnvelope) -> dict[str, Any]:
        operation = request.operation

        if operation is WorkerOperation.AUTH_STATUS:
            return await auth_status()
        if operation is WorkerOperation.AUTH_START:
            return await auth_start()
        if operation is WorkerOperation.AUTH_RESUME:
            return await auth_resume()
        if operation is WorkerOperation.AUTH_SESSION:
            return await auth_session()
        if operation is WorkerOperation.ACCOUNT_CONTEXT:
            return await account_context()
        if operation is WorkerOperation.ACCOUNT_LICENSE:
            return await account_license()
        if planner_adapter.owns(operation):
            return await planner_adapter.dispatch(request)

        raise HTTPException(status_code=422, detail="unsupported worker operation")

    @app.post("/operations", response_model=WorkerResponseEnvelope)
    async def execute_operation(
        request: WorkerRequestEnvelope,
    ) -> WorkerResponseEnvelope | JSONResponse:
        """Execute one negotiated semantic operation with sanitized typed failures."""
        try:
            if not worker_protocol.compatible:
                raise ProtocolIncompatible("typed worker protocol is not negotiated")
            result = await profile_executor.execute(
                request.operation.value,
                lambda: dispatch_semantic_operation(request),
            )
        except (PlannerMcpError, HTTPException) as exc:
            status_code, envelope = project_worker_error(
                exc,
                request_id=request.request_id,
                operation=request.operation,
            )
            return JSONResponse(
                status_code=status_code,
                content=envelope.model_dump(mode="json"),
            )

        return WorkerResponseEnvelope(
            request_id=request.request_id,
            operation=request.operation,
            result=result,
        )

    return app


app = create_app()
