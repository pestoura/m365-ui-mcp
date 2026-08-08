"""Canonical product, contract and schema version constants."""

from __future__ import annotations

# Keep a literal __version__ assignment because Hatch's default regex version
# source reads this file without importing the package.
__version__ = "0.1.0"
PRODUCT_VERSION = __version__
CONTRACT_VERSION = PRODUCT_VERSION
SCHEMA_VERSION = PRODUCT_VERSION
UI_CONTRACT_VERSION = PRODUCT_VERSION
TOOL_CATALOG_VERSION = PRODUCT_VERSION
