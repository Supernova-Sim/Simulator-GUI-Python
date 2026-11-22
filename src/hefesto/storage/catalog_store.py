"""JSON catalog CRUD for rockets, motors, launch sites, safety limits, and missions."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from hefesto.domain import (
    CatalogOverview,
    EnvironmentSpec,
    MissionPreset,
    MotorPreset,
    RocketPreset,
    SafetyLimits,
)
from hefesto.storage.asset_store import AssetStore
from hefesto.storage.paths import (
    StoragePaths,
    atomic_write_text,
    resolve_safe_relative_path,
    resolve_storage_paths,
    validate_safe_slug,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class CatalogStore:
    """Strict Pydantic JSON repository under data/catalog/ with atomic persistence."""

    def __init__(
        self,
        paths: StoragePaths | None = None,
        asset_store: AssetStore | None = None,
    ) -> None:
        self.paths = resolve_storage_paths() if paths is None else paths
        self.asset_store = AssetStore(self.paths) if asset_store is None else asset_store

    def _normalize_id(self, preset_id: str) -> str:
        stripped = preset_id.strip()
        stem = stripped.removesuffix(".json") if stripped.endswith(".json") else stripped
        return validate_safe_slug(stem, "preset_id")

    def _list_section(self, directory: Path) -> tuple[str, ...]:
        if not directory.is_dir():
            return ()
        resolved_dir = directory.resolve()
        names = [
            entry.stem
            for entry in sorted(directory.glob("*.json"))
            if entry.is_file() and entry.resolve().is_relative_to(resolved_dir)
        ]
        return tuple(names)

    def _load_model(self, directory: Path, preset_id: str, model_cls: type[ModelT]) -> ModelT:
        slug = self._normalize_id(preset_id)
        target = resolve_safe_relative_path(directory, f"{slug}.json")
        if not target.is_file():
            raise FileNotFoundError(f"{model_cls.__name__} preset not found: {slug!r}")
        return model_cls.model_validate_json(target.read_text(encoding="utf-8"))

    def _save_model(self, directory: Path, preset_id: str, model: BaseModel) -> Path:
        slug = self._normalize_id(preset_id)
        target = resolve_safe_relative_path(directory, f"{slug}.json")
        payload = model.model_dump_json(indent=2) + "\n"
        return atomic_write_text(target, payload)

    def list_rockets(self) -> tuple[str, ...]:
        return self._list_section(self.paths.rockets_catalog_dir)

    def load_rocket(self, preset_id: str) -> RocketPreset:
        return self._load_model(self.paths.rockets_catalog_dir, preset_id, RocketPreset)

    def save_rocket(self, preset: RocketPreset, preset_id: str | None = None) -> Path:
        resolved_id = preset.name if preset_id is None else preset_id
        return self._save_model(self.paths.rockets_catalog_dir, resolved_id, preset)

    def list_motors(self) -> tuple[str, ...]:
        return self._list_section(self.paths.motors_catalog_dir)

    def load_motor(self, preset_id: str) -> MotorPreset:
        return self._load_model(self.paths.motors_catalog_dir, preset_id, MotorPreset)

    def save_motor(self, preset: MotorPreset, preset_id: str | None = None) -> Path:
        resolved_id = preset.name if preset_id is None else preset_id
        return self._save_model(self.paths.motors_catalog_dir, resolved_id, preset)

    def list_sites(self) -> tuple[str, ...]:
        return self._list_section(self.paths.sites_catalog_dir)

    def load_site(self, preset_id: str) -> EnvironmentSpec:
        return self._load_model(self.paths.sites_catalog_dir, preset_id, EnvironmentSpec)

    def save_site(self, preset: EnvironmentSpec, preset_id: str | None = None) -> Path:
        resolved_id = preset.name if preset_id is None else preset_id
        return self._save_model(self.paths.sites_catalog_dir, resolved_id, preset)

    def list_limits(self) -> tuple[str, ...]:
        return self._list_section(self.paths.limits_catalog_dir)

    def load_limits(self, preset_id: str) -> SafetyLimits:
        return self._load_model(self.paths.limits_catalog_dir, preset_id, SafetyLimits)

    def save_limits(self, limits: SafetyLimits, preset_id: str = "default") -> Path:
        return self._save_model(self.paths.limits_catalog_dir, preset_id, limits)

    def list_missions(self) -> tuple[str, ...]:
        return self._list_section(self.paths.missions_catalog_dir)

    def load_mission(self, preset_id: str) -> MissionPreset:
        return self._load_model(self.paths.missions_catalog_dir, preset_id, MissionPreset)

    def save_mission(self, preset: MissionPreset, preset_id: str | None = None) -> Path:
        resolved_id = preset.name if preset_id is None else preset_id
        return self._save_model(self.paths.missions_catalog_dir, resolved_id, preset)

    def overview(self) -> CatalogOverview:
        """Return a CatalogOverview DTO summarizing available raw assets and JSON presets."""
        return CatalogOverview(
            assets=self.asset_store.list_assets(),
            motor_presets=self.list_motors(),
            rocket_presets=self.list_rockets(),
            environment_presets=self.list_sites(),
            mission_presets=self.list_missions(),
        )


__all__ = ["CatalogStore"]
