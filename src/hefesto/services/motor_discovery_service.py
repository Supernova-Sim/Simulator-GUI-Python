"""Automatic .ric motor discovery, cached conversion, and GUI upload import services."""

from __future__ import annotations

import hashlib
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from hefesto.adapters import extract_grains_from_props, load_ric_props
from hefesto.domain import (
    AssetCategory,
    MotorCasingSpec,
    MotorPreset,
    NozzleSpec,
    RicMotorAsset,
    RicMotorCache,
    RicMotorCacheEntry,
)
from hefesto.physics import (
    DEFAULT_CASE_YIELD_STRENGTH_PA,
    DEFAULT_WALL_THICKNESS_M,
    derive_motor_casing_properties,
)
from hefesto.services.asset_service import DEFAULT_MOTOR_ID, resolve_paths
from hefesto.storage import AssetStore, CatalogStore, StoragePaths, validate_safe_slug

_RIC_EXTENSION = ".ric"
_CACHE_VERSION = 2
# A .ric carries grains/nozzle/propellant but no casing, so the preset casing is
# synthesized from the grain stack with a default aluminium shell unless a catalog
# preset references a byte-identical asset (then its calibrated casing is inherited).
_RIC_GRAIN_SEPARATION_M = 0.0
_CASE_RADIAL_CLEARANCE_M = 0.002
_CASE_END_MARGIN_M = 0.02
_CASE_INTERNAL_CLEARANCE_M = 0.04
_SYNTHETIC_CASING_WARNING = (
    "Carcaça sintetizada a partir dos grãos (tubo Al 2 mm, sem tubeira/ferragens); "
    "revise massa e parede antes de simular."
)
_UNSAFE_SLUG_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _one_line(message: object) -> str:
    """Collapse adapter/parser tracebacks into a single GUI-safe warning line."""
    return " ".join(str(message).split())


def _normalize_motor_id(motor_id: str) -> str:
    cleaned = motor_id.strip()
    if cleaned.lower().endswith(_RIC_EXTENSION):
        return cleaned[: -len(_RIC_EXTENSION)]
    return cleaned


def _sanitize_ric_slug(filename: str) -> str:
    """Return a safe single-segment stem for an uploaded .ric filename."""
    cleaned = filename.strip()
    if not cleaned.lower().endswith(_RIC_EXTENSION):
        raise ValueError(
            f"Extensão inválida em '{filename}': apenas arquivos .ric são aceitos."
        )
    stem = _UNSAFE_SLUG_CHARS.sub("_", cleaned[: -len(_RIC_EXTENSION)]).strip("._-")
    return validate_safe_slug(stem, "ric_filename")


def _ric_relative_paths(store: AssetStore) -> tuple[str, ...]:
    """Return relative .ric asset paths under data/assets/motors/."""
    return tuple(
        entry.relative_path
        for entry in store.list_assets(AssetCategory.MOTORS)
        if entry.file_format == "ric"
    )


def _catalog_covered_stems(paths: StoragePaths) -> set[str]:
    """Return motor ids and .ric stems already represented by a catalog preset JSON."""
    catalog = CatalogStore(paths)
    covered: set[str] = set()
    for motor_id in catalog.list_motors():
        covered.add(motor_id.lower())
        try:
            preset = catalog.load_motor(motor_id)
        except (FileNotFoundError, ValidationError):
            # A broken preset JSON must not hide its raw .ric asset from discovery.
            continue
        if preset.motor_asset is not None:
            covered.add(Path(preset.motor_asset).stem.lower())
    return covered


def _thrust_curve_asset(store: AssetStore, slug: str) -> str | None:
    """Return '<slug>.eng' when a RASP thrust curve with the same stem exists."""
    asset_name = f"{slug}.eng"
    return asset_name if store.asset_exists(AssetCategory.MOTORS, asset_name) else None


def _catalog_casing_templates(store: AssetStore) -> dict[str, MotorPreset]:
    """Map sha256 of each catalog .ric asset to its preset, for casing inheritance."""
    catalog = CatalogStore(store.paths)
    templates: dict[str, MotorPreset] = {}
    for motor_id in catalog.list_motors():
        try:
            preset = catalog.load_motor(motor_id)
        except (FileNotFoundError, ValidationError):
            continue
        if preset.motor_asset is None:
            continue
        try:
            asset_path = store.resolve_asset(
                AssetCategory.MOTORS, preset.motor_asset, must_exist=False
            )
            raw = asset_path.read_bytes()
        except (FileNotFoundError, ValueError, OSError):
            continue
        templates.setdefault(_sha256(raw), preset)
    return templates


def _optional_positive_float(raw: object) -> float | None:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        value = float(raw)
        if value > 0.0:
            return value
    return None


def _optional_angle_deg(raw: object) -> float | None:
    value = _optional_positive_float(raw)
    if value is not None and value < 90.0:
        return value
    return None


def _preset_from_ric_path(
    ric_path: Path,
    slug: str,
    thrust_curve_asset: str | None,
    casing_template: MotorPreset | None = None,
) -> MotorPreset:
    """Convert one OpenMotor .ric file into a selection-ready MotorPreset.

    A .ric carries no casing: when a catalog preset references a byte-identical asset its
    calibrated casing is inherited, otherwise a bare aluminium tube is synthesized.
    """
    props = load_ric_props(ric_path, ())
    grains = extract_grains_from_props(props)
    nozzle_raw = props.get("nozzle")
    propellant_raw = props.get("propellant")
    assert isinstance(nozzle_raw, Mapping)
    assert isinstance(propellant_raw, Mapping)

    density_kg_m3 = float(propellant_raw["density"])
    if casing_template is None:
        grain_separation_m = _RIC_GRAIN_SEPARATION_M
        case_inner_radius_m = (
            max(grain.outer_radius_m for grain in grains) + _CASE_RADIAL_CLEARANCE_M
        )
        case_wall_thickness_m = DEFAULT_WALL_THICKNESS_M
        case_length_m: float | None = None
        internal_clearance_m = _CASE_INTERNAL_CLEARANCE_M
        yield_strength_pa = DEFAULT_CASE_YIELD_STRENGTH_PA
        dry_mass_override_kg: float | None = None
        dry_inertia_override_kg_m2: tuple[float, float, float] | None = None
        nozzle_position_m = 0.0
    else:
        inherited = casing_template.casing
        grain_separation_m = casing_template.grain_separation_m
        case_inner_radius_m = inherited.inner_radius_m
        case_wall_thickness_m = inherited.wall_thickness_m
        case_length_m = inherited.length_m
        internal_clearance_m = inherited.internal_clearance_m
        yield_strength_pa = inherited.yield_strength_pa
        dry_mass_override_kg = inherited.dry_mass_kg
        dry_inertia_override_kg_m2 = inherited.dry_inertia_kg_m2
        nozzle_position_m = casing_template.nozzle_position_m

    mass = derive_motor_casing_properties(
        grains,
        grain_separation_m,
        density_kg_m3,
        case_inner_radius_m=case_inner_radius_m,
        case_wall_thickness_m=case_wall_thickness_m,
        case_length_m=case_length_m,
        margin_forward_side_m=_CASE_END_MARGIN_M,
        margin_nozzle_side_m=_CASE_END_MARGIN_M,
        internal_clearance_m=internal_clearance_m,
        dry_mass_override_kg=dry_mass_override_kg,
        dry_inertia_override_kg_m2=dry_inertia_override_kg_m2,
    )
    casing = MotorCasingSpec(
        inner_radius_m=case_inner_radius_m,
        wall_thickness_m=case_wall_thickness_m,
        length_m=mass.case_length_m,
        internal_clearance_m=internal_clearance_m,
        yield_strength_pa=yield_strength_pa,
        dry_mass_kg=mass.dry_mass_kg,
        dry_inertia_kg_m2=mass.dry_inertia_kg_m2,
        center_of_dry_mass_m=mass.center_of_dry_mass_m,
    )

    efficiency_raw = nozzle_raw.get("efficiency", 1.0)
    efficiency = (
        float(efficiency_raw)
        if isinstance(efficiency_raw, (int, float)) and not isinstance(efficiency_raw, bool)
        else 1.0
    )
    nozzle = NozzleSpec(
        throat_radius_m=float(nozzle_raw["throat"]) / 2.0,
        exit_radius_m=float(nozzle_raw["exit"]) / 2.0,
        throat_length_m=_optional_positive_float(nozzle_raw.get("throatLength")),
        converging_angle_deg=_optional_angle_deg(nozzle_raw.get("convAngle")),
        diverging_angle_deg=_optional_angle_deg(nozzle_raw.get("divAngle")),
        efficiency=min(max(efficiency, 1e-6), 1.0),
    )

    raw_name = propellant_raw.get("name")
    propellant_name = (
        raw_name.strip()
        if isinstance(raw_name, str) and raw_name.strip()
        else "KNSB"
    )
    return MotorPreset(
        name=slug,
        motor_asset=f"{slug}{_RIC_EXTENSION}",
        thrust_curve_asset=thrust_curve_asset,
        casing=casing,
        grain_separation_m=grain_separation_m,
        grains_center_of_mass_m=mass.grains_center_of_mass_m,
        nozzle_position_m=nozzle_position_m,
        propellant_name=propellant_name,
        fallback_grains=grains,
        propellant_density_kg_m3=density_kg_m3,
        nozzle=nozzle,
    )


def _read_cache(store: AssetStore) -> RicMotorCache:
    payload = store.load_motor_discovery_cache()
    if payload is None:
        return RicMotorCache()
    try:
        cache = RicMotorCache.model_validate_json(payload)
    except ValidationError:
        return RicMotorCache()
    return cache if cache.version == _CACHE_VERSION else RicMotorCache()


def _write_cache(store: AssetStore, cache: RicMotorCache) -> None:
    try:
        store.save_motor_discovery_cache(cache.model_dump_json(indent=2) + "\n")
    except OSError:
        # The cache is best-effort: a read-only data/cache must not break the listing.
        return


def _cache_entry_from_disk(
    ric_path: Path,
    relative_path: str,
    slug: str,
    store: AssetStore,
    templates: Mapping[str, MotorPreset],
) -> RicMotorCacheEntry:
    stat = ric_path.stat()
    raw = ric_path.read_bytes()
    digest = _sha256(raw)
    try:
        preset = _preset_from_ric_path(
            ric_path,
            slug,
            _thrust_curve_asset(store, slug),
            templates.get(digest),
        )
    except Exception as exc:  # Corrupt .ric files must never break the other motors.
        return RicMotorCacheEntry(
            relative_path=relative_path,
            mtime_ns=stat.st_mtime_ns,
            size_bytes=stat.st_size,
            sha256=digest,
            warnings=(f"Falha ao ler '{relative_path}': {_one_line(exc)}",),
        )
    return RicMotorCacheEntry(
        relative_path=relative_path,
        mtime_ns=stat.st_mtime_ns,
        size_bytes=stat.st_size,
        sha256=digest,
        preset=preset,
        warnings=() if digest in templates else (_SYNTHETIC_CASING_WARNING,),
    )


def _synced_entries(
    store: AssetStore,
    covered_stems: set[str],
) -> tuple[RicMotorCacheEntry, ...]:
    """Reconcile data/cache/motors/discovery.json against the .ric files on disk."""
    cache = _read_cache(store)
    cached = {entry.relative_path: entry for entry in cache.entries}
    motors_dir = store.paths.asset_category_dir(AssetCategory.MOTORS)
    templates = _catalog_casing_templates(store)
    synced: list[RicMotorCacheEntry] = []

    for relative_path in _ric_relative_paths(store):
        slug = Path(relative_path).stem
        if slug.lower() in covered_stems:
            continue
        ric_path = motors_dir / relative_path
        try:
            stat = ric_path.stat()
        except OSError:
            continue
        entry = cached.get(relative_path)
        if (
            entry is not None
            and entry.mtime_ns == stat.st_mtime_ns
            and entry.size_bytes == stat.st_size
        ):
            synced.append(entry)
            continue
        if entry is not None and entry.sha256 == _sha256(ric_path.read_bytes()):
            # Only the mtime moved: reuse the validated preset and refresh the identity.
            synced.append(
                entry.model_copy(
                    update={"mtime_ns": stat.st_mtime_ns, "size_bytes": stat.st_size}
                )
            )
            continue
        synced.append(_cache_entry_from_disk(ric_path, relative_path, slug, store, templates))

    new_cache = RicMotorCache(version=_CACHE_VERSION, entries=tuple(synced))
    if new_cache.model_dump_json() != cache.model_dump_json():
        _write_cache(store, new_cache)
    return tuple(synced)


def discover_ric_motors(repo_root: Path | str | None = None) -> tuple[RicMotorAsset, ...]:
    """List .ric motors under data/assets/motors/ that have no equivalent catalog preset."""
    paths = resolve_paths(repo_root)
    store = AssetStore(paths)
    covered = _catalog_covered_stems(paths)
    assets: list[RicMotorAsset] = []
    for entry in _synced_entries(store, covered):
        slug = Path(entry.relative_path).stem
        assets.append(
            RicMotorAsset(
                preset_id=slug,
                name=entry.preset.name if entry.preset is not None else slug,
                motor_asset=entry.relative_path,
                warnings=entry.warnings,
            )
        )
    return tuple(assets)


def load_ric_motor_preset(
    motor_id: str = DEFAULT_MOTOR_ID,
    *,
    repo_root: Path | str | None = None,
) -> MotorPreset:
    """Load the preset synthesized from a matching .ric asset, using the cache when valid."""
    paths = resolve_paths(repo_root)
    store = AssetStore(paths)
    normalized = _normalize_motor_id(motor_id)
    entry = next(
        (
            item
            for item in _synced_entries(store, _catalog_covered_stems(paths))
            if Path(item.relative_path).stem == normalized
        ),
        None,
    )
    if entry is None:
        raise FileNotFoundError(f"Motor preset not found: {motor_id!r}")
    if entry.preset is None:
        details = "; ".join(entry.warnings) or f"'{entry.relative_path}' não convertido"
        raise ValueError(f"Motor .ric inválido ({motor_id}): {details}")
    return entry.preset


def load_motor_preset_any(
    motor_id: str = DEFAULT_MOTOR_ID,
    *,
    repo_root: Path | str | None = None,
) -> MotorPreset:
    """Load a catalog MotorPreset, falling back to an auto-discovered .ric asset."""
    try:
        return CatalogStore(resolve_paths(repo_root)).load_motor(motor_id)
    except FileNotFoundError:
        return load_ric_motor_preset(motor_id, repo_root=repo_root)


def _upsert_cache_entry(
    store: AssetStore,
    preset: MotorPreset,
    relative_path: str,
    warnings: tuple[str, ...],
) -> None:
    ric_path = store.paths.asset_category_dir(AssetCategory.MOTORS) / relative_path
    stat = ric_path.stat()
    entry = RicMotorCacheEntry(
        relative_path=relative_path,
        mtime_ns=stat.st_mtime_ns,
        size_bytes=stat.st_size,
        sha256=_sha256(ric_path.read_bytes()),
        preset=preset,
        warnings=warnings,
    )
    cache = _read_cache(store)
    kept = [item for item in cache.entries if item.relative_path != relative_path]
    kept.append(entry)
    kept.sort(key=lambda item: item.relative_path)
    _write_cache(store, RicMotorCache(version=_CACHE_VERSION, entries=tuple(kept)))


def import_openmotor_ric(
    filename: str,
    raw_bytes: bytes,
    save_to_catalog: bool = True,
    *,
    overwrite: bool = False,
    repo_root: Path | str | None = None,
) -> MotorPreset:
    """Validate an uploaded .ric, store it atomically, and optionally persist its preset."""
    if not raw_bytes:
        raise ValueError(f"Arquivo .ric vazio: '{filename}'.")
    slug = _sanitize_ric_slug(filename)
    paths = resolve_paths(repo_root)
    store = AssetStore(paths)
    if save_to_catalog and not overwrite and slug in CatalogStore(paths).list_motors():
        raise FileExistsError(
            f"Motor preset '{slug}' already exists; pass overwrite=True to replace it."
        )
    relative_path = f"{slug}{_RIC_EXTENSION}"
    thrust_curve_asset = _thrust_curve_asset(store, slug)
    casing_template = _catalog_casing_templates(store).get(_sha256(raw_bytes))

    # Convert from a throwaway copy first: a corrupt upload must never replace a good asset.
    with tempfile.TemporaryDirectory(prefix="hefesto_ric_") as temp_dir:
        temp_path = Path(temp_dir) / relative_path
        temp_path.write_bytes(raw_bytes)
        try:
            preset = _preset_from_ric_path(
                temp_path, slug, thrust_curve_asset, casing_template
            )
        except Exception as exc:
            raise ValueError(
                f"Arquivo .ric inválido ou corrompido: '{filename}': {_one_line(exc)}"
            ) from exc

    store.save_motor_ric_asset(relative_path, raw_bytes)
    if save_to_catalog:
        CatalogStore(paths).save_motor(preset, preset_id=slug, overwrite=overwrite)
    _upsert_cache_entry(
        store,
        preset,
        relative_path,
        () if casing_template is not None else (_SYNTHETIC_CASING_WARNING,),
    )
    return preset


__all__ = [
    "discover_ric_motors",
    "import_openmotor_ric",
    "load_motor_preset_any",
    "load_ric_motor_preset",
]
