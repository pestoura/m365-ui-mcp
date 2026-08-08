"""Session-bound semantic capability broker for the M365 browser worker.

The broker authorizes closed semantic capabilities against the process-owned
professional browser session. It never reads, serializes or exports cookies,
tokens, headers or browser storage state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from m365_mcp.capability_registry import CapabilityRegistry, ScopedCapability
from planner_mcp.auth import AuthState
from planner_mcp.errors import AuthRequired, WorkerUnavailable

from .browser import PersistentBrowser


@dataclass(frozen=True)
class SessionCapabilityGrant:
    """Content-free proof that one semantic capability is session-bound."""

    application: str
    surface: str
    account_scope: str
    container_scope: str
    capability: str
    session_bound: bool = True
    secret_material_exported: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "application": self.application,
            "surface": self.surface,
            "account_scope": self.account_scope,
            "container_scope": self.container_scope,
            "capability": self.capability,
            "session_bound": self.session_bound,
            "secret_material_exported": self.secret_material_exported,
        }


class SessionCapabilityBroker:
    """Bind semantic authorization to an existing authenticated browser session."""

    def __init__(
        self,
        *,
        browser: PersistentBrowser,
        registry: CapabilityRegistry,
        auth_state_provider: Callable[[], AuthState],
    ) -> None:
        self._browser = browser
        self._registry = registry
        self._auth_state_provider = auth_state_provider

    @property
    def viable(self) -> bool:
        """Return whether a live browser and authenticated session are both proven."""
        return self._browser.started and self._auth_state_provider() is AuthState.AUTHENTICATED

    def authorize(self, *, application: str, capability: str) -> SessionCapabilityGrant:
        """Authorize exactly one registered semantic capability, failing closed."""
        if not self._browser.started:
            raise WorkerUnavailable("session broker requires a process-owned browser")
        if self._auth_state_provider() is not AuthState.AUTHENTICATED:
            raise AuthRequired("session broker requires an authenticated professional session")

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
        """Return bounded operational metadata without any session secret material."""
        return {
            "viable": self.viable,
            "browser_started": self._browser.started,
            "auth_state": self._auth_state_provider().value,
            "secret_material_exported": False,
        }


__all__ = ["SessionCapabilityBroker", "SessionCapabilityGrant"]
