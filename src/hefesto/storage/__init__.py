"""Filesystem layer: canonical paths, atomic writes, curve parsers, and JSON stores.

Owns data/assets resolution, data/catalog CRUD, data/runs snapshots, and data/cache
artifacts. No simulator or UI imports here. Storage imports only hefesto.domain and
hefesto.storage; services and adapters consume it.
"""

from __future__ import annotations

from hefesto.storage.asset_store import ASSET_EXTENSION_WHITELIST, AssetStore
from hefesto.storage.catalog_store import CatalogStore
from hefesto.storage.file_parsers import (
    load_drag_curve,
    parse_csv_curve,
    parse_csv_text,
    parse_eng_file,
    parse_eng_text,
)
from hefesto.storage.paths import (
    StoragePaths,
    atomic_write_bytes,
    atomic_write_text,
    get_repo_root,
    resolve_safe_relative_path,
    resolve_storage_paths,
    validate_safe_slug,
)
from hefesto.storage.run_store import RunStore

__all__ = [
    "ASSET_EXTENSION_WHITELIST",
    "AssetStore",
    "CatalogStore",
    "RunStore",
    "StoragePaths",
    "atomic_write_bytes",
    "atomic_write_text",
    "get_repo_root",
    "load_drag_curve",
    "parse_csv_curve",
    "parse_csv_text",
    "parse_eng_file",
    "parse_eng_text",
    "resolve_safe_relative_path",
    "resolve_storage_paths",
    "validate_safe_slug",
]
