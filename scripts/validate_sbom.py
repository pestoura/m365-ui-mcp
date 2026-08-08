"""Validate a CycloneDX SBOM document produced in CI."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_sbom.py <sbom.json>")
        return 2

    path = Path(argv[1])
    if not path.exists():
        print(f"FAIL SBOM not found: {path}")
        return 1

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL SBOM is not valid JSON: {exc}")
        return 1

    errors: list[str] = []
    if document.get("bomFormat") != "CycloneDX":
        errors.append(f"bomFormat is {document.get('bomFormat')!r}, expected 'CycloneDX'")
    if not document.get("specVersion"):
        errors.append("specVersion missing")

    components = document.get("components")
    if not isinstance(components, list) or not components:
        errors.append("components list missing or empty")
    else:
        for index, component in enumerate(components):
            if not component.get("name"):
                errors.append(f"components[{index}] has no name")
            if not (component.get("purl") or component.get("version")):
                errors.append(f"components[{index}] has neither purl nor version")

    for error in errors:
        print(f"FAIL {error}")
    if errors:
        return 1

    print(f"SBOM OK: {path.name}, {len(components)} components")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
