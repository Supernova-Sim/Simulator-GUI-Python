"""Asset discovery, safe relative resolution, and in-memory curve loading services."""

from __future__ import annotations

from pathlib import Path

from hefesto.domain import AssetCategory, AssetEntry, DragCurveSpec
from hefesto.storage import (
    AssetStore,
    StoragePaths,
    load_drag_curve,
    parse_eng_file,
    resolve_storage_paths,
)

DEFAULT_ROCKET_ID = "hefesto_v1"
DEFAULT_MOTOR_ID = "medusa_knsb_a"
DEFAULT_SITE_ID = "irec_oper"
DEFAULT_LIMITS_ID = "default"


def resolve_paths(repo_root: Path | str | None = None) -> StoragePaths:
    """Resolve StoragePaths from an optional string or Path workspace root."""
    root = None if repo_root is None else Path(repo_root)
    return resolve_storage_paths(root)


def list_assets(
    category: AssetCategory | None = None,
    repo_root: Path | str | None = None,
) -> tuple[AssetEntry, ...]:
    """List whitelisted raw assets under data/assets/ for one or all categories."""
    return AssetStore(resolve_paths(repo_root)).list_assets(category)


def resolve_asset_path(
    category: AssetCategory,
    relative_path: str,
    *,
    must_exist: bool = True,
    repo_root: Path | str | None = None,
) -> Path:
    """Resolve and validate a relative asset path under data/assets/<category>/."""
    return AssetStore(resolve_paths(repo_root)).resolve_asset(
        category,
        relative_path,
        must_exist=must_exist,
    )


def asset_exists(
    category: AssetCategory,
    relative_path: str,
    repo_root: Path | str | None = None,
) -> bool:
    """Return whether a whitelisted relative asset exists on disk."""
    return AssetStore(resolve_paths(repo_root)).asset_exists(category, relative_path)


def load_drag_curve_asset(
    relative_path: str,
    repo_root: Path | str | None = None,
) -> DragCurveSpec:
    """Load a relative CSV drag curve from data/assets/drag/ into memory."""
    path = resolve_asset_path(AssetCategory.DRAG, relative_path, repo_root=repo_root)
    return load_drag_curve(path, asset_name=relative_path)


def load_thrust_curve_asset(
    relative_path: str,
    repo_root: Path | str | None = None,
) -> tuple[tuple[float, float], ...]:
    """Load a relative RASP .eng thrust curve from data/assets/motors/ into memory."""
    path = resolve_asset_path(AssetCategory.MOTORS, relative_path, repo_root=repo_root)
    return tuple(parse_eng_file(path))


__all__ = [
    "DEFAULT_LIMITS_ID",
    "DEFAULT_MOTOR_ID",
    "DEFAULT_ROCKET_ID",
    "DEFAULT_SITE_ID",
    "asset_exists",
    "list_assets",
    "load_drag_curve_asset",
    "load_thrust_curve_asset",
    "resolve_asset_path",
    "resolve_paths",
]
