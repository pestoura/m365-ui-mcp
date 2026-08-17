"""RED regression test for PersistentBrowser._password_surface_transitioned.

Models a TRANSIENT disappearance followed by REHYDRATION of the fixed
password/submit controls:

  1. initial sample: password + submit both uniquely present (count == 1);
  2. at least 3 consecutive samples: non-unique/absent (count != 1);
  3. BOTH controls return to uniquely present (count == 1) again BEFORE the
     bounded observation window is exhausted.

Desired behavior: the helper must return ``False`` -- a transient dip that
rehydrates must NOT be accepted as a stable surface transition. The current
implementation early-returns ``True`` as soon as the absence streak reaches 3,
before the rehydration sample is ever observed: that is the bug this test
pins.

No live browser, no network, no credentials. The page object is a fake whose
``locator(...).count()`` yields a fixed sequence of control counts.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from m365_browser_worker.browser import BrowserConfig, PersistentBrowser

# Control-count sequence (password, submit) per observation sample.
#   sample 0: both unique           -> streak 0
#   sample 1: both absent           -> streak 1
#   sample 2: both absent           -> streak 2
#   sample 3: both absent           -> streak 3 (bug returns True HERE)
#   sample 4: both unique again     -> rehydration (must reset streak)
_CONTROL_COUNTS = [1, 1, 0, 0, 0, 0, 0, 0, 1, 1]


def _fake_page() -> MagicMock:
    """Build a fake page whose locator.count() yields control counts in order."""
    locator = MagicMock()
    locator.count = AsyncMock(side_effect=list(_CONTROL_COUNTS))
    page = MagicMock()
    page.locator = MagicMock(return_value=locator)
    return page


async def test_password_surface_transitioned_rejects_transient_dip_then_rehydration(
    tmp_path: Path,
) -> None:
    """A transient absence that rehydrates before the window ends is NOT a transition."""
    browser = PersistentBrowser(BrowserConfig(profile_dir=tmp_path, mode="mock"))
    page = _fake_page()

    result = await browser._password_surface_transitioned(page)

    assert result is False
