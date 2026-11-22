"""Catalog listing and CRUD services for rockets, motors, sites, limits, and missions."""

from __future__ import annotations

from pathlib import Path

from hefesto.domain import (
    CatalogDatabaseInspection,
    CatalogOverview,
    EnvironmentSpec,
    MissionPreset,
    MotorPreset,
    NamedSafetyLimitsPreset,
    NamedSitePreset,
    PointMassComponent,
    RocketPreset,
    SafetyLimits,
    SavedRocketInspection,
    TubeComponent,
)
from hefesto.services.asset_service import (
    DEFAULT_LIMITS_ID,
    DEFAULT_MOTOR_ID,
    DEFAULT_ROCKET_ID,
    DEFAULT_SITE_ID,
    list_assets,
    resolve_paths,
)
from hefesto.services.motor_service import inspect_saved_motor
from hefesto.services.rocket_service import load_rocket_spec, summarize_rocket_structure
from hefesto.storage import CatalogStore, RunStore


def _catalog_store(repo_root: Path | str | None = None) -> CatalogStore:
    return CatalogStore(resolve_paths(repo_root))


def get_catalog_overview(repo_root: Path | str | None = None) -> CatalogOverview:
    """Return a picklable CatalogOverview DTO of available assets and presets."""
    return _catalog_store(repo_root).overview()


def list_rockets(repo_root: Path | str | None = None) -> tuple[str, ...]:
    """List available rocket preset identifiers."""
    return _catalog_store(repo_root).list_rockets()


def load_rocket_preset(
    preset_id: str = DEFAULT_ROCKET_ID,
    repo_root: Path | str | None = None,
) -> RocketPreset:
    """Load a RocketPreset from data/catalog/rockets/."""
    return _catalog_store(repo_root).load_rocket(preset_id)


def save_rocket_preset(
    preset: RocketPreset,
    preset_id: str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    """Persist a RocketPreset atomically into data/catalog/rockets/."""
    return _catalog_store(repo_root).save_rocket(preset, preset_id=preset_id)


def list_motors(repo_root: Path | str | None = None) -> tuple[str, ...]:
    """List available motor preset identifiers."""
    return _catalog_store(repo_root).list_motors()


def load_motor_preset(
    preset_id: str = DEFAULT_MOTOR_ID,
    repo_root: Path | str | None = None,
) -> MotorPreset:
    """Load a MotorPreset from data/catalog/motors/."""
    return _catalog_store(repo_root).load_motor(preset_id)


def save_motor_preset(
    preset: MotorPreset,
    preset_id: str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    """Persist a MotorPreset atomically into data/catalog/motors/."""
    return _catalog_store(repo_root).save_motor(preset, preset_id=preset_id)


def list_sites(repo_root: Path | str | None = None) -> tuple[str, ...]:
    """List available launch site EnvironmentSpec identifiers."""
    return _catalog_store(repo_root).list_sites()


def load_site_preset(
    preset_id: str = DEFAULT_SITE_ID,
    repo_root: Path | str | None = None,
) -> EnvironmentSpec:
    """Load an EnvironmentSpec from data/catalog/sites/."""
    return _catalog_store(repo_root).load_site(preset_id)


def save_site_preset(
    preset: EnvironmentSpec,
    preset_id: str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    """Persist an EnvironmentSpec atomically into data/catalog/sites/."""
    return _catalog_store(repo_root).save_site(preset, preset_id=preset_id)


def list_limits(repo_root: Path | str | None = None) -> tuple[str, ...]:
    """List available SafetyLimits preset identifiers."""
    return _catalog_store(repo_root).list_limits()


def load_limits_preset(
    preset_id: str = DEFAULT_LIMITS_ID,
    repo_root: Path | str | None = None,
) -> SafetyLimits:
    """Load SafetyLimits from data/catalog/limits/."""
    return _catalog_store(repo_root).load_limits(preset_id)


def save_limits_preset(
    limits: SafetyLimits,
    preset_id: str = DEFAULT_LIMITS_ID,
    repo_root: Path | str | None = None,
) -> Path:
    """Persist SafetyLimits atomically into data/catalog/limits/."""
    return _catalog_store(repo_root).save_limits(limits, preset_id=preset_id)


def list_missions(repo_root: Path | str | None = None) -> tuple[str, ...]:
    """List available MissionPreset identifiers."""
    return _catalog_store(repo_root).list_missions()


def load_mission_preset(
    preset_id: str,
    repo_root: Path | str | None = None,
) -> MissionPreset:
    """Load a MissionPreset from data/catalog/missions/."""
    return _catalog_store(repo_root).load_mission(preset_id)


def save_mission_preset(
    preset: MissionPreset,
    preset_id: str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    """Persist a MissionPreset atomically into data/catalog/missions/."""
    return _catalog_store(repo_root).save_mission(preset, preset_id=preset_id)


def inspect_saved_rocket(
    rocket_id: str = DEFAULT_ROCKET_ID,
    *,
    repo_root: Path | str | None = None,
) -> SavedRocketInspection:
    """Inspect a saved RocketPreset with calculated dry mass, components, and aero summary."""
    preset = load_rocket_preset(rocket_id, repo_root=repo_root)
    spec = load_rocket_spec(rocket_id, repo_root=repo_root)
    structure = summarize_rocket_structure(spec)
    tube_count = sum(1 for comp in preset.components if isinstance(comp, TubeComponent))
    point_mass_count = sum(1 for comp in preset.components if isinstance(comp, PointMassComponent))
    components_summary = tuple(
        f"{comp.name} ({comp.kind} @ {comp.position_m:.3f} m)" for comp in preset.components
    )
    return SavedRocketInspection(
        preset_id=rocket_id,
        name=preset.name,
        motor_preset_name=preset.motor_preset_name,
        radius_m=preset.radius_m,
        calculated_dry_mass_kg=structure.dry_mass_kg,
        dry_mass_override_kg=preset.dry_mass_override_kg,
        center_of_mass_without_motor_m=structure.center_of_mass_m,
        inertia_kg_m2=structure.inertia_kg_m2,
        motor_position_m=preset.motor_position_m,
        tube_count=tube_count,
        point_mass_count=point_mass_count,
        fin_count=preset.fins.count,
        fin_position_m=preset.fins.position_m,
        nose_cone_kind=preset.nose_cone.kind.value,
        nose_cone_length_m=preset.nose_cone.length_m,
        parachute_names=tuple(chute.name for chute in preset.parachutes),
        power_off_drag_asset=preset.power_off_drag_asset,
        power_on_drag_asset=preset.power_on_drag_asset,
        components_summary=components_summary,
    )


def inspect_catalog_database(
    repo_root: Path | str | None = None,
) -> CatalogDatabaseInspection:
    """Return a complete typed inspection of motors, rockets, sites, limits, assets, and runs."""
    paths = resolve_paths(repo_root)
    store = CatalogStore(paths)
    motors = tuple(
        inspect_saved_motor(motor_id, repo_root=repo_root) for motor_id in store.list_motors()
    )
    rockets = tuple(
        inspect_saved_rocket(rocket_id, repo_root=repo_root) for rocket_id in store.list_rockets()
    )
    sites = tuple(
        NamedSitePreset(preset_id=site_id, spec=store.load_site(site_id))
        for site_id in store.list_sites()
    )
    limits = tuple(
        NamedSafetyLimitsPreset(preset_id=lim_id, limits=store.load_limits(lim_id))
        for lim_id in store.list_limits()
    )
    assets = list_assets(repo_root=repo_root)
    runs = RunStore(paths).list_runs()
    return CatalogDatabaseInspection(
        motors=motors,
        rockets=rockets,
        sites=sites,
        limits=limits,
        assets=assets,
        runs=runs,
    )


__all__ = [
    "DEFAULT_LIMITS_ID",
    "DEFAULT_MOTOR_ID",
    "DEFAULT_ROCKET_ID",
    "DEFAULT_SITE_ID",
    "get_catalog_overview",
    "inspect_catalog_database",
    "inspect_saved_rocket",
    "list_limits",
    "list_missions",
    "list_motors",
    "list_rockets",
    "list_sites",
    "load_limits_preset",
    "load_mission_preset",
    "load_motor_preset",
    "load_rocket_preset",
    "load_site_preset",
    "save_limits_preset",
    "save_mission_preset",
    "save_motor_preset",
    "save_rocket_preset",
    "save_site_preset",
]
