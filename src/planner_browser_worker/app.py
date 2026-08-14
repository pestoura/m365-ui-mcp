"""FastAPI browser worker. Mock mode by default; live mode fails closed."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from m365_browser_worker.account_context import AccountContext, unverified_account_context
from m365_browser_worker.apps.planner import PlannerWorkerAdapter
from m365_browser_worker.auth_bootstrap import AuthBootstrapGuard
from m365_browser_worker.bootstrap_navigation import (
    AUTH_BEGIN_SIGNIN_OPERATION,
    AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
    MICROSOFT_AUTH_TARGET_CLASS,
    PLANNER_WEB_TARGET_CLASS,
    evaluate_microsoft_auth_target,
    is_loopback_peer,
)
from m365_browser_worker.executor import ProfileSerializedExecutor
from m365_browser_worker.lifecycle import browser_lifespan
from m365_browser_worker.operator_signin import (
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
from m365_browser_worker.worker_errors import project_worker_error
from m365_mcp.capability_registry import default_capability_registry
from planner_mcp.auth import AuthState
from planner_mcp.errors import (
    PlannerMcpError,
    PolicyDenied,
    ProtocolIncompatible,
    WorkerUnavailable,
)
from planner_mcp.logging_setup import configure_logging
from planner_mcp.ui_contract import load_status

from . import __version__, mock_data
from .browser import BrowserConfig, PersistentBrowser


def _mode() -> str:
    return os.getenv("PLANNER_MODE", "mock").lower()


def _is_mock() -> bool:
    return _mode() != "live"


def create_app(
    browser: PersistentBrowser | None = None,
    *,
    profile_viability_provider: Callable[[], bool] | None = None,
    auth_state_provider: Callable[[], AuthState] | None = None,
    account_context_provider: Callable[[], AccountContext] | None = None,
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
        auth_state_provider=current_auth_state,
        account_context_provider=current_account_context,
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
    )
    app = FastAPI(
        title="planner-browser-worker",
        version=__version__,
        lifespan=browser_lifespan(worker_browser),
    )
    # Internal ownership only; no generic executor/browser endpoint is exposed.
    app.state.profile_executor = profile_executor
    app.state.protocol_negotiator = worker_protocol

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

    planner_adapter = PlannerWorkerAdapter(
        is_mock=_is_mock,
        capability_guard=capability_guard,
        data_provider=mock_data,
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
            "ui_contract_set_digest": ui.contract_set_digest,
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
        except Exception:  # noqa: BLE001 - malformed body must not echo values
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

        if not _is_mock():
            # Fail closed before any browser interaction: the two memory-only
            # fields must never be applied when the common.auth UIContract
            # fragment is not attested. (Route docstring contract.)
            if not worker_browser.common_auth_attested():
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "NOT_ATTESTED",
                        "message": "common.auth UIContract not attested; operator submit refused",
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
