#!/usr/bin/env python3
"""Create one GitHub issue per backlog key, idempotently.

Reads docs/backlog.md, extracts P-001..P-074 with their epic and title, then creates any
issue that does not already exist. Matching is done on the ``[P-0NN]`` title prefix, so
re-running the script never creates duplicates.

Usage:
    python scripts/sync_backlog_issues.py --repo pestoura/planner-mcp [--dry-run]

Requires the ``gh`` CLI, already authenticated. This script never touches Planner or any
Microsoft tenant.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKLOG = REPO_ROOT / "docs" / "backlog.md"

EPIC_RE = re.compile(r"^##\s+(EPIC-\d{2})\s+[—-]\s+(.+?)\s*$")
ITEM_RE = re.compile(r"^###\s+(P-\d{3})\s+[—-]\s+(.+?)\s*$")

EPIC_LABELS = {
    "EPIC-01": "epic:foundation",
    "EPIC-02": "epic:browser-worker",
    "EPIC-03": "epic:auth-mfa",
    "EPIC-04": "epic:read-model",
    "EPIC-05": "epic:mutations",
    "EPIC-06": "epic:scheduling",
    "EPIC-07": "epic:reconciliation",
    "EPIC-08": "epic:reporting",
    "EPIC-09": "epic:security-governance",
    "EPIC-10": "epic:acceptance-release",
}

MUTATION_LABELS = {
    "EPIC-05": "mutation-class:governed-write",
    "EPIC-07": "mutation-class:governed-write",
}

HIGH_RISK_EPICS = {"EPIC-03", "EPIC-05", "EPIC-09"}


def run(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(args)}\n{proc.stderr.strip()}")
    return proc.stdout


def parse_backlog(text: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    epic_id = ""
    epic_title = ""
    current: dict[str, str] | None = None
    body_lines: list[str] = []

    def flush() -> None:
        if current is not None:
            current["body"] = "\n".join(body_lines).strip()
            items.append(current)

    for line in text.splitlines():
        epic_match = EPIC_RE.match(line)
        if epic_match:
            flush()
            current = None
            body_lines = []
            epic_id, epic_title = epic_match.group(1), epic_match.group(2)
            continue
        item_match = ITEM_RE.match(line)
        if item_match:
            flush()
            body_lines = []
            current = {
                "key": item_match.group(1),
                "title": item_match.group(2),
                "epic": epic_id,
                "epic_title": epic_title,
            }
            continue
        if current is not None:
            body_lines.append(line)
    flush()
    return items


def existing_keys(repo: str) -> set[str]:
    out = run(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--limit",
            "500",
            "--json",
            "title",
        ]
    )
    keys: set[str] = set()
    for issue in json.loads(out):
        match = re.match(r"^\[(P-\d{3})\]", issue["title"])
        if match:
            keys.add(match.group(1))
    return keys


def labels_for(item: dict[str, str]) -> list[str]:
    labels = ["type:task", EPIC_LABELS.get(item["epic"], "epic:unassigned")]
    if item["epic"] in HIGH_RISK_EPICS:
        labels.append("risk:high")
    if item["epic"] in MUTATION_LABELS:
        labels.append(MUTATION_LABELS[item["epic"]])
    else:
        labels.append("mutation-class:read")
    return labels


def ensure_labels(repo: str, labels: set[str], dry_run: bool) -> None:
    out = run(["gh", "label", "list", "--repo", repo, "--limit", "200", "--json", "name"])
    have = {entry["name"] for entry in json.loads(out)}
    for label in sorted(labels - have):
        if dry_run:
            print(f"[dry-run] would create label {label}")
            continue
        run(["gh", "label", "create", label, "--repo", repo, "--force"])
        print(f"created label {label}")


def build_body(item: dict[str, str]) -> str:
    return (
        f"Backlog key: **{item['key']}**\n"
        f"Epic: **{item['epic']} — {item['epic_title']}**\n\n"
        f"{item['body']}\n\n"
        "---\n"
        "Canonical source: [`docs/backlog.md`](../blob/main/docs/backlog.md). "
        "Definition of Done: "
        "[`docs/definition-of-done.md`](../blob/main/docs/definition-of-done.md).\n"
        "This item must not be closed without code, tests, docs, security checks and CI GREEN."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    items = parse_backlog(BACKLOG.read_text(encoding="utf-8"))
    expected = {f"P-{n:03d}" for n in range(1, 75)}
    found = {item["key"] for item in items}
    if found != expected:
        print(f"backlog parse mismatch: missing={sorted(expected - found)}")
        return 1

    have = existing_keys(args.repo)
    ensure_labels(args.repo, {label for item in items for label in labels_for(item)}, args.dry_run)

    created = 0
    for item in items:
        if item["key"] in have:
            print(f"skip {item['key']} (already exists)")
            continue
        title = f"[{item['key']}] {item['title']}"
        cmd = [
            "gh",
            "issue",
            "create",
            "--repo",
            args.repo,
            "--title",
            title,
            "--body",
            build_body(item),
        ]
        for label in labels_for(item):
            cmd += ["--label", label]
        if args.dry_run:
            print(f"[dry-run] would create {title}")
            continue
        print(run(cmd).strip())
        created += 1

    print(f"done: {created} created, {len(items) - created} already present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
