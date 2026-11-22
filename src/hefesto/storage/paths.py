"""Filesystem layout, anti-path-traversal resolution, and atomic text writes."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from hefesto.domain import AssetCategory


def get_repo_root() -> Path:
    """Return the Hefesto repository root inferred from this module's location."""
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class StoragePaths:
    """Canonical directory layout rooted at a Hefesto repository workspace."""

    repo_root: Path

    @property
    def data_dir(self) -> Path:
        return self.repo_root / "data"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def catalog_dir(self) -> Path:
        return self.data_dir / "catalog"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def rockets_catalog_dir(self) -> Path:
        return self.catalog_dir / "rockets"

    @property
    def motors_catalog_dir(self) -> Path:
        return self.catalog_dir / "motors"

    @property
    def sites_catalog_dir(self) -> Path:
        return self.catalog_dir / "sites"

    @property
    def limits_catalog_dir(self) -> Path:
        return self.catalog_dir / "limits"

    @property
    def missions_catalog_dir(self) -> Path:
        return self.catalog_dir / "missions"

    @property
    def openrocket_assets_dir(self) -> Path:
        return self.assets_dir / "openrocket"

    @property
    def openrocket_cache_dir(self) -> Path:
        return self.data_dir / "cache" / "openrocket"

    def asset_category_dir(self, category: AssetCategory) -> Path:
        return self.assets_dir / category.value


def resolve_storage_paths(repo_root: Path | None = None) -> StoragePaths:
    """Build a StoragePaths bundle for the active repository or an isolated test root."""
    root = get_repo_root() if repo_root is None else repo_root.resolve()
    return StoragePaths(repo_root=root)


def validate_safe_slug(identifier: str, field_name: str = "identifier") -> str:
    """Validate a single-segment filename stem without traversal or path separators."""
    if "\x00" in identifier:
        raise ValueError(f"{field_name} must not contain null bytes")
    cleaned = identifier.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must be non-empty")
    if (
        cleaned.startswith(".")
        or ".." in cleaned
        or any(sep in cleaned for sep in ("/", "\\", ":"))
    ):
        raise ValueError(f"{field_name} contains unsafe path characters: {identifier!r}")
    return cleaned


def resolve_safe_relative_path(base_dir: Path, relative_path: str | Path) -> Path:
    """Resolve a relative path strictly inside base_dir, blocking traversal and symlink escapes."""
    if isinstance(relative_path, Path) and relative_path.is_absolute():
        raise ValueError(f"Path must be relative, got absolute path: {relative_path!r}")

    raw = str(relative_path)
    if "\x00" in raw:
        raise ValueError("Path must not contain null bytes")

    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("Relative path must be non-empty")
    if cleaned.startswith("/") or "\\" in cleaned or ":" in cleaned:
        raise ValueError(f"Path must be a clean relative POSIX path, got {relative_path!r}")

    parts = [part for part in cleaned.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        raise ValueError(f"Path traversal segment not allowed: {relative_path!r}")

    resolved_base = base_dir.resolve()
    candidate = (resolved_base / Path(*parts)).resolve()
    if candidate == resolved_base or not candidate.is_relative_to(resolved_base):
        raise ValueError(f"Resolved path escapes base directory {resolved_base}: {relative_path!r}")
    return candidate


def atomic_write_text(target: Path, content: str, *, encoding: str = "utf-8") -> Path:
    """Write text to a same-directory temporary file, fsync, and atomically replace target."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, mode="w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return target


def atomic_write_bytes(target: Path, content: bytes) -> Path:
    """Write bytes to a same-directory temporary file, fsync, and atomically replace target."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        text=False,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, mode="wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return target


__all__ = [
    "StoragePaths",
    "atomic_write_bytes",
    "atomic_write_text",
    "get_repo_root",
    "resolve_safe_relative_path",
    "resolve_storage_paths",
    "validate_safe_slug",
]
