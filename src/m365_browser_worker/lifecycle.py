"""FastAPI ownership of the canonical Microsoft 365 browser lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from m365_browser_worker.browser import PersistentBrowser

BrowserLifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def browser_lifespan(browser: PersistentBrowser) -> BrowserLifespan:
    """Bind exactly one browser instance to one FastAPI application lifespan.

    Startup and shutdown are owned by the ASGI process. The browser object is
    exposed through ``app.state.browser`` for typed internal components only;
    no HTTP route or generic browser primitive is introduced here.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.browser = browser
        try:
            await browser.start()
            yield
        finally:
            await browser.stop()

    return lifespan


__all__ = ["BrowserLifespan", "browser_lifespan"]
