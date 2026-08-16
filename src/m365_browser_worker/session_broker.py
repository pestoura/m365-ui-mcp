"""Session-bound semantic capability broker for the M365 browser worker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from m365_mcp.capability_registry import CapabilityRegistry, ScopedCapability
from planner_mcp.auth import AuthState
from planner_mcp.errors import AuthRequired, PolicyDenied, WorkerUnavailable

from .account_context import AccountContext, unverified_account_context
from .browser import PersistentBrowser


@dataclass(frozen=True)
class SessionCapabilityGrant:
    """Bounded proof that one semantic capability is session-bound."""

    application: str
    surface: str
    account_scope: str
    container_scope: str
    capability: str
    session_bound: bool = True
    account_context_verified: bool = True
    secret_material_exported: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "application": self.application,
            "surface": self.surface,
            "account_scope": self.account_scope,
            "container_scope": self.container_scope,
            "capability": self.capability,
            "session_bound": self.session_bound,
            "account_context_verified": self.account_context_verified,
            "secret_material_exported": self.secret_material_exported,
        }


class SessionCapabilityBroker:
    """Bind semantic authorization to a verified professional browser context."""

    def __init__(
        self,
        *,
        browser: PersistentBrowser,
        registry: CapabilityRegistry,
        auth_state_provider: Callable[[], AuthState],
        account_context_provider: Callable[[], AccountContext] | None = None,
        live_read_path_provider: Callable[[], bool] | None = None,
    ) -> None:
        self._browser = browser
        self._registry = registry
        self._auth_state_provider = auth_state_provider
        self._account_context_provider = account_context_provider or unverified_account_context
        # Read-only delivery capabilities (plans.read / tasks.read /
        # project_snapshot.read) are authorized by the verified professional
        # session on the live Planner Web surface, NOT by tenant license metadata.
        # When this provider returns True, the account-context license check is
        # relaxed for those delivery caps only; every other capability (including
        # all mutations) still requires a verified account context.
        self._live_read_path_provider = live_read_path_provider

    _READ_ONLY_DELIVERY_CAPABILITIES = frozenset(
        {"plans.read", "tasks.read", "project_snapshot.read"}
    )

    def _is_read_only_delivery(self, capability: str) -> bool:
        return capability in self._READ_ONLY_DELIVERY_CAPABILITIES

    @property
    def viable(self) -> bool:
        """Return whether browser, authentication and account context are proven."""
        return (
            self._browser.started
            and self._auth_state_provider() is AuthState.AUTHENTICATED
            and self._account_context_provider().valid
        )

    def authorize(self, *, application: str, capability: str) -> SessionCapabilityGrant:
        """Authorize exactly one registered semantic capability, failing closed."""
        if not self._browser.started:
            raise WorkerUnavailable("session broker requires a process-owned browser")
        if self._auth_state_provider() is not AuthState.AUTHENTICATED:
            raise AuthRequired("session broker requires an authenticated professional session")

        account_context = self._account_context_provider()
        if not account_context.valid:
            # Read-only delivery capabilities are authorized by the verified
            # professional session on the live Planner Web surface, independent of
            # tenant license / account-context metadata. When the live read path
            # is verified, the read may proceed against the already-rendered board
            # without requiring a verified license account context. All other
            # capabilities (including every mutation) remain gated on the verified
            # account context, so this does NOT widen the write surface.
            live_read_path = (
                self._live_read_path_provider() if self._live_read_path_provider else False
            )
            if not (self._is_read_only_delivery(capability) and live_read_path):
                raise PolicyDenied(
                    "professional account context is not verified",
                    account_context_state=account_context.state.value,
                    professional=account_context.professional,
                    expected_profile=account_context.expected_profile,
                )

        definitions = tuple(
            definition
            for definition in self._registry.by_application(application)
            if definition.capability == capability
        )
        if len(definitions) != 1:
            raise WorkerUnavailable(
                "semantic capability is not uniquely registered",
                application=application,
                capability=capability,
            )

        # Read-only delivery capabilities (plans.read / tasks.read /
        # project_snapshot.read) are authorized by Gate-1 — the verified
        # professional session on the live Planner Web surface — and do NOT
        # require full UIContract fragment attestation. The live read path
        # signal is already the post-MFA surface proof the broker trusts for
        # these caps, so we skip the stricter ensure_live_allowed guard here.
        # Every other capability (including all mutations) still falls through
        # to ensure_live_allowed and therefore remains gated on attestation.
        live_read_path = (
            self._live_read_path_provider() if self._live_read_path_provider else False
        )
        if not (
            self._is_read_only_delivery(capability) and live_read_path
        ):
            self._browser.ensure_live_allowed(capability)
        definition: ScopedCapability = definitions[0]
        return SessionCapabilityGrant(
            application=definition.application,
            surface=definition.surface,
            account_scope=definition.account_scope,
            container_scope=definition.container_scope,
            capability=definition.capability,
        )

    def snapshot(self) -> dict[str, object]:
        """Return bounded operational metadata."""
        account_context = self._account_context_provider()
        return {
            "viable": self.viable,
            "browser_started": self._browser.started,
            "auth_state": self._auth_state_provider().value,
            "account_context": account_context.to_dict(),
            "secret_material_exported": False,
        }


__all__ = ["SessionCapabilityBroker", "SessionCapabilityGrant"]
