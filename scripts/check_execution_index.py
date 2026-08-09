#!/usr/bin/env python3
"""Fail-closed validation for the bounded M365 executable WIP index."""

from __future__ import annotations

import json
import re
from pathlib import Path

INDEX_PATH = Path("docs/m365-transition/execution-index.json")
SCHEMA = "m365.execution-index/v1"
KEY_PATTERN = re.compile(r"^(?:M365-(?:SETUP|JDS|CONTROL)-\d{3}|CORE-\d{3}|PLN-MIG-\d{3}|OUT-\d{3}|XAPP-\d{3}|REL-\d{3})$")
STATES = {
    "DEFERRED",
    "READY",
    "IN_PROGRESS",
    "INTEGRATING",
    "ACCEPTED",
    "BLOCKED",
    "SUPERSEDED",
}
IMPLEMENTATION_STATES = {
    "PLANNED",
    "SPECIFIED_ONLY",
    "IMPLEMENTED_MOCK_ONLY",
    "IMPLEMENTED_NOT_ATTESTED",
    "IMPLEMENTED_LIVE",
    "DEPRECATED",
    "BLOCKED",
}
LIVE_SUPPORT_STATES = {
    "UNOBSERVED",
    "UNSUPPORTED",
    "SUPPORTED_LIVE",
    "DEGRADED",
    "RE_ATTESTATION_REQUIRED",
    "NOT_APPLICABLE",
}
ACTIVE_STATES = {"IN_PROGRESS", "INTEGRATING"}


def _fail(message: str) -> None:
    raise SystemExit(f"EXECUTION_INDEX_INVALID: {message}")


def _load() -> dict[str, object]:
    if not INDEX_PATH.is_file():
        _fail(f"missing {INDEX_PATH}")
    try:
        document = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"cannot parse index: {exc}")
    if not isinstance(document, dict):
        _fail("top-level document must be an object")
    return document


def main() -> int:
    document = _load()
    if document.get("schema") != SCHEMA:
        _fail(f"schema must be {SCHEMA}")

    rules = document.get("rules")
    if not isinstance(rules, dict):
        _fail("rules must be an object")
    max_wip = rules.get("maxActiveFeatureWip")
    if not isinstance(max_wip, int) or isinstance(max_wip, bool) or not 1 <= max_wip <= 6:
        _fail("maxActiveFeatureWip must be an integer from 1 to 6")
    if rules.get("roadmapIsExecutionQueue") is not False:
        _fail("roadmapIsExecutionQueue must remain false")
    if rules.get("mergeImpliesLiveSupport") is not False:
        _fail("mergeImpliesLiveSupport must remain false")

    items = document.get("items")
    if not isinstance(items, list) or not items:
        _fail("items must be a non-empty list")

    keys: set[str] = set()
    prs: dict[int, str] = {}
    feature_wip = 0
    for position, raw_item in enumerate(items):
        if not isinstance(raw_item, dict):
            _fail(f"item {position} must be an object")
        item = raw_item
        key = item.get("key")
        if not isinstance(key, str) or KEY_PATTERN.fullmatch(key) is None:
            _fail(f"item {position} has invalid canonical key")
        if key in keys:
            _fail(f"duplicate canonical key {key}")
        keys.add(key)

        state = item.get("state")
        if state not in STATES:
            _fail(f"{key} has invalid state {state!r}")
        implementation_state = item.get("implementationState")
        if implementation_state not in IMPLEMENTATION_STATES:
            _fail(f"{key} has invalid implementationState {implementation_state!r}")
        live_state = item.get("liveSupportState")
        if live_state not in LIVE_SUPPORT_STATES:
            _fail(f"{key} has invalid liveSupportState {live_state!r}")

        dependencies = item.get("dependencies")
        if not isinstance(dependencies, list) or not all(
            isinstance(value, str) and KEY_PATTERN.fullmatch(value) for value in dependencies
        ):
            _fail(f"{key} dependencies must contain canonical keys")
        if len(dependencies) != len(set(dependencies)):
            _fail(f"{key} dependencies contain duplicates")
        if key in dependencies:
            _fail(f"{key} cannot depend on itself")

        item_prs = item.get("prs")
        if not isinstance(item_prs, list) or not all(
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            for value in item_prs
        ):
            _fail(f"{key} prs must contain positive integers")
        for pr_number in item_prs:
            owner = prs.get(pr_number)
            if owner is not None and owner != key:
                _fail(f"PR #{pr_number} is mapped to both {owner} and {key}")
            prs[pr_number] = key

        blocker = item.get("blockerCode")
        if state == "BLOCKED" and not isinstance(blocker, str):
            _fail(f"{key} BLOCKED state requires blockerCode")
        if state != "BLOCKED" and blocker is not None:
            _fail(f"{key} non-BLOCKED state cannot carry blockerCode")

        branch = item.get("branch")
        if state in ACTIVE_STATES and not isinstance(branch, str):
            _fail(f"{key} active state requires branch")
        if state == "INTEGRATING" and not item.get("wave"):
            _fail(f"{key} INTEGRATING state requires wave")

        if key.startswith("OUT-") and state in ACTIVE_STATES:
            feature_wip += 1
        if live_state == "SUPPORTED_LIVE" and implementation_state != "IMPLEMENTED_LIVE":
            _fail(f"{key} cannot be SUPPORTED_LIVE without IMPLEMENTED_LIVE")
        if implementation_state == "IMPLEMENTED_MOCK_ONLY" and live_state == "SUPPORTED_LIVE":
            _fail(f"{key} mock-only implementation cannot be live-supported")

    if feature_wip > max_wip:
        _fail(f"active OUT WIP {feature_wip} exceeds bounded maximum {max_wip}")

    print(
        "EXECUTION_INDEX_OK "
        f"items={len(items)} active_out={feature_wip} max_out={max_wip} prs={len(prs)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
