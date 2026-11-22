"""Raw asset discovery and resolution with strict extension whitelist and traversal guard."""

from __future__ import annotations

from pathlib import Path

from hefesto.domain import AssetCategory, AssetEntry
from hefesto.storage.paths import (
    StoragePaths,
    resolve_safe_relative_path,
    resolve_storage_paths,
)

ASSET_EXTENSION_WHITELIST: dict[AssetCategory, frozenset[str]] = {
    AssetCategory.MOTORS: frozenset({".eng", ".ric"}),
    AssetCategory.DRAG: frozenset({".csv"}),
    AssetCategory.ATMOSPHERE: frozenset({".nc"}),
}


class AssetStore:
    """Read-only asset resolver and indexer under data/assets/{motors,drag,atmosphere}/."""

    def __init__(self, paths: StoragePaths | None = None) -> None:
        self.paths = resolve_storage_paths() if paths is None else paths

    def resolve_asset(
        self,
        category: AssetCategory,
        relative_path: str,
        *,
        must_exist: bool = True,
    ) -> Path:
        """Validate category whitelist and containment, then return resolved asset Path."""
        resolved_category = AssetCategory(category)
        category_dir = self.paths.asset_category_dir(resolved_category)
        candidate = resolve_safe_relative_path(category_dir, relative_path)

        allowed_exts = ASSET_EXTENSION_WHITELIST[resolved_category]
        suffix = candidate.suffix.lower()
        if suffix not in allowed_exts:
            allowed_list = ", ".join(sorted(allowed_exts))
            raise ValueError(
                f"Disallowed file extension {suffix!r} for asset category "
                f"'{resolved_category.value}' (allowed: {allowed_list})"
            )

        if must_exist and not candidate.is_file():
            raise FileNotFoundError(
                f"Asset not found under '{resolved_category.value}': {relative_path}"
            )
        return candidate

    def asset_exists(self, category: AssetCategory, relative_path: str) -> bool:
        """Return whether a whitelisted relative asset exists on disk."""
        return self.resolve_asset(category, relative_path, must_exist=False).is_file()

    def list_assets(self, category: AssetCategory | None = None) -> tuple[AssetEntry, ...]:
        """List valid whitelisted assets under one category or all asset categories."""
        categories = (
            (AssetCategory(category),) if category is not None else tuple(AssetCategory)
        )
        entries: list[AssetEntry] = []

        for cat in categories:
            category_dir = self.paths.asset_category_dir(cat)
            if not category_dir.is_dir():
                continue
            resolved_root = category_dir.resolve()
            allowed_exts = ASSET_EXTENSION_WHITELIST[cat]

            for item in sorted(category_dir.rglob("*")):
                if not item.is_file():
                    continue
                resolved_item = item.resolve()
                if not resolved_item.is_relative_to(resolved_root):
                    continue
                suffix = item.suffix.lower()
                if suffix not in allowed_exts:
                    continue
                rel_posix = item.relative_to(category_dir).as_posix()
                entries.append(
                    AssetEntry(
                        category=cat,
                        relative_path=rel_posix,
                        name=item.stem,
                        file_format=suffix.lstrip("."),
                    )
                )

        entries.sort(key=lambda entry: (entry.category.value, entry.relative_path))
        return tuple(entries)


__all__ = ["ASSET_EXTENSION_WHITELIST", "AssetStore"]
