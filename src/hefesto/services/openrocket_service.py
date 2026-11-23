"""OpenRocket (.ork) import, hash-cached parsing, and catalog export services."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import ValidationError

from hefesto.adapters.openrocket import parse_ork_bytes
from hefesto.domain import (
    DragCurveSpec,
    DragCurveTable,
    DragSource,
    NoseConeSpec,
    OrkImportSummary,
    OrkImportWarning,
    OrkParsedDesign,
    PointMassComponent,
    RocketSpec,
)
from hefesto.physics import derive_nose_cone_properties
from hefesto.services.asset_service import (
    DEFAULT_ROCKET_ID,
    load_drag_curve_asset,
    resolve_paths,
)
from hefesto.services.catalog_service import save_rocket_preset
from hefesto.services.motor_service import load_motor_spec
from hefesto.services.rocket_service import (
    recalculate_rocket_structure,
    rocket_preset_from_spec,
    summarize_rocket_structure,
)
from hefesto.storage import AssetStore

_PARSER_CACHE_VERSION = "v5"


def list_ork_assets(repo_root: Path | str | None = None) -> tuple[str, ...]:
    """List saved OpenRocket (.ork) files under data/assets/openrocket/."""
    return AssetStore(resolve_paths(repo_root)).list_openrocket_assets()


def save_ork_asset(
    filename: str,
    content: bytes,
    repo_root: Path | str | None = None,
) -> Path:
    """Persist an .ork file atomically under data/assets/openrocket/."""
    return AssetStore(resolve_paths(repo_root)).save_openrocket_asset(filename, content)


def _resolve_ork_bytes(
    ork_bytes_or_asset: bytes | str,
    store: AssetStore,
) -> bytes:
    if isinstance(ork_bytes_or_asset, bytes):
        return ork_bytes_or_asset
    asset_path = store.resolve_openrocket_asset(ork_bytes_or_asset)
    return asset_path.read_bytes()


def _load_or_parse_ork(
    raw_bytes: bytes,
    store: AssetStore,
) -> tuple[OrkParsedDesign, bool]:
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    cached_json = store.load_openrocket_cache(sha256, parser_version=_PARSER_CACHE_VERSION)
    if cached_json is not None:
        try:
            return OrkParsedDesign.model_validate_json(cached_json), True
        except ValidationError:
            pass

    parsed = parse_ork_bytes(raw_bytes)
    store.save_openrocket_cache(
        sha256,
        parsed.model_dump_json(indent=2) + "\n",
        parser_version=_PARSER_CACHE_VERSION,
    )
    return parsed, False


def _default_motor_position_m(parsed: OrkParsedDesign) -> float:
    if parsed.detected_motor_mount_position_m is not None:
        return parsed.detected_motor_mount_position_m
    max_tail = max(
        (comp.position_m for comp in parsed.components),
        default=parsed.nose_cone.length_m + 0.5,
    )
    return max(0.1, max_tail)


def _resolve_nose_cone_shell(parsed: OrkParsedDesign) -> NoseConeSpec:
    """Attach the imported nose shell to the nose spec so dry mass counts it exactly once."""
    if parsed.nose_cone_override_mass_kg is None and (
        parsed.nose_cone_wall_thickness_m is None or parsed.nose_cone_density_kg_m3 is None
    ):
        return parsed.nose_cone
    shell = derive_nose_cone_properties(
        parsed.nose_cone,
        wall_thickness_m=parsed.nose_cone_wall_thickness_m or 0.002,
        density_kg_m3=parsed.nose_cone_density_kg_m3 or 1850.0,
        base_radius_m=parsed.radius_m,
    )
    mass_kg = (
        parsed.nose_cone_override_mass_kg
        if parsed.nose_cone_override_mass_kg is not None
        else shell.mass_kg
    )
    if mass_kg <= 0.0:
        return parsed.nose_cone
    cg_m = (
        parsed.nose_cone_override_cg_m
        if parsed.nose_cone_override_mass_kg is not None
        and parsed.nose_cone_override_cg_m is not None
        else shell.cg_m
    )
    return parsed.nose_cone.model_copy(
        update={
            "shell": PointMassComponent(
                name=f"{parsed.nose_cone.name} (casca)",
                mass_kg=mass_kg,
                position_m=max(0.0, cg_m),
            )
        }
    )


_DRAG_SOURCE_MESSAGES: dict[str, str] = {
    "analytical": (
        "Curvas Cd(Mach) calculadas analiticamente da geometria do foguete "
        "(drag_source='analytical', rugosidade '{finish}'); os assets '{off}'/'{on}' do "
        "catálogo não são usados neste modo."
    ),
    "legacy_csv": (
        "Curvas de arrasto vinculadas do catálogo: power_off='{off}', power_on='{on}' "
        "(drag_source='legacy_csv')."
    ),
    "ork_sim": (
        "Curvas Cd(Mach) extraídas dos <datapoint> de voo do .ork "
        "(drag_source='ork_sim'); assets '{off}'/'{on}' ficam apenas como fallback."
    ),
}


def _drag_source_message(
    drag_source: DragSource,
    *,
    surface_finish: str,
    power_off_drag_asset: str,
    power_on_drag_asset: str,
) -> str:
    template = _DRAG_SOURCE_MESSAGES[drag_source]
    return template.format(
        finish=surface_finish, off=power_off_drag_asset, on=power_on_drag_asset
    )


def _resolve_ork_drag_curves(
    parsed: OrkParsedDesign,
    *,
    drag_source: DragSource,
    power_off_drag_asset: str,
    power_on_drag_asset: str,
    repo_root: Path | str | None,
) -> tuple[DragCurveTable | None, DragCurveSpec, DragCurveSpec]:
    """Return (reference table, power_off curve, power_on curve) for the requested source."""
    if drag_source == "rasaero_csv":
        raise ValueError(
            "drag_source='rasaero_csv' is imported from a RASAero II CSV, not from a .ork file"
        )
    if drag_source == "ork_sim":
        if parsed.drag_table is None:
            raise ValueError(
                "O .ork não possui <flightdata> com colunas Mach/CD utilizáveis para "
                "drag_source='ork_sim'."
            )
        power_off_drag, power_on_drag = parsed.drag_table.to_specs()
        return parsed.drag_table, power_off_drag, power_on_drag
    # analytical curves are recomputed from geometry after the spec exists.
    return (
        parsed.drag_table,
        load_drag_curve_asset(power_off_drag_asset, repo_root=repo_root),
        load_drag_curve_asset(power_on_drag_asset, repo_root=repo_root),
    )


def preview_ork_import(
    ork_bytes_or_asset: bytes | str,
    *,
    base_motor_id: str,
    power_off_drag_asset: str,
    power_on_drag_asset: str,
    drag_source: DragSource = "analytical",
    repo_root: Path | str | None = None,
) -> OrkImportSummary:
    """Parse (with hash cache), bind catalog motor/drag, and derive structural mass/CG/inertia."""
    store = AssetStore(resolve_paths(repo_root))
    raw_bytes = _resolve_ork_bytes(ork_bytes_or_asset, store)
    parsed, from_cache = _load_or_parse_ork(raw_bytes, store)

    motor = load_motor_spec(base_motor_id, repo_root=repo_root)
    drag_table, power_off_drag, power_on_drag = _resolve_ork_drag_curves(
        parsed,
        drag_source=drag_source,
        power_off_drag_asset=power_off_drag_asset,
        power_on_drag_asset=power_on_drag_asset,
        repo_root=repo_root,
    )

    motor_pos_m = _default_motor_position_m(parsed)
    initial_spec = RocketSpec(
        name=parsed.rocket_name,
        radius_m=parsed.radius_m,
        center_of_mass_without_motor_m=max(0.1, parsed.nose_cone.length_m),
        inertia_kg_m2=(1.0, 1.0, 0.05),
        motor_position_m=motor_pos_m,
        components=parsed.components,
        nose_cone=_resolve_nose_cone_shell(parsed),
        fins=parsed.fins,
        rail_buttons=parsed.rail_buttons,
        parachutes=parsed.parachutes,
        power_off_drag=power_off_drag,
        power_on_drag=power_on_drag,
        motor=motor,
        drag_source=drag_source,
        surface_finish=parsed.surface_finish,
    )
    recalculated_spec = recalculate_rocket_structure(initial_spec)
    structure = summarize_rocket_structure(recalculated_spec)

    warnings = list(parsed.warnings)
    warnings.append(
        OrkImportWarning(
            severity="info",
            component_name="Aerodinâmica (Cd)",
            message=_drag_source_message(
                drag_source,
                surface_finish=parsed.surface_finish.value,
                power_off_drag_asset=power_off_drag_asset,
                power_on_drag_asset=power_on_drag_asset,
            ),
        )
    )
    if parsed.stored_datapoint_count > 0:
        used = drag_source == "ork_sim"
        warnings.append(
            OrkImportWarning(
                severity="info",
                component_name="Simulações Salvas (.ork)",
                message=(
                    f"Detectados {parsed.stored_datapoint_count} <datapoint> de voo no .ork"
                    + (
                        " e extraída a curva ork_sim de referência."
                        if used
                        else "; a curva de referência ork_sim não foi usada neste import."
                    )
                ),
            )
        )

    return OrkImportSummary(
        rocket_id=None,
        rocket_spec=recalculated_spec,
        calculated_dry_mass_kg=structure.dry_mass_kg,
        center_of_mass_without_motor_m=structure.center_of_mass_m,
        inertia_kg_m2=structure.inertia_kg_m2,
        from_cache=from_cache,
        source_sha256=parsed.source_sha256,
        embedded_rse_names=parsed.embedded_rse_names,
        stored_datapoint_count=parsed.stored_datapoint_count,
        has_mass_or_cg_overrides=parsed.has_mass_or_cg_overrides,
        drag_source=drag_source,
        drag_table=drag_table if drag_source == "ork_sim" else None,
        warnings=tuple(warnings),
    )


def import_and_save_ork_rocket(
    ork_bytes_or_asset: bytes | str,
    *,
    rocket_id: str,
    base_motor_id: str,
    power_off_drag_asset: str,
    power_on_drag_asset: str,
    rocket_name: str | None = None,
    drag_source: DragSource = "analytical",
    save_ork_asset_file: bool = True,
    repo_root: Path | str | None = None,
) -> OrkImportSummary:
    """Import an .ork design, optionally store the .ork asset, and export RocketPreset JSON."""
    cleaned_id = rocket_id.strip()
    if not cleaned_id:
        raise ValueError("Informe um ID válido para o preset de foguete importado.")
    if cleaned_id == DEFAULT_ROCKET_ID:
        raise ValueError(
            f"Não é permitido sobrescrever o preset Golden Master '{DEFAULT_ROCKET_ID}'."
        )

    summary = preview_ork_import(
        ork_bytes_or_asset,
        base_motor_id=base_motor_id,
        power_off_drag_asset=power_off_drag_asset,
        power_on_drag_asset=power_on_drag_asset,
        drag_source=drag_source,
        repo_root=repo_root,
    )

    resolved_name = (
        rocket_name.strip()
        if rocket_name is not None and rocket_name.strip()
        else summary.rocket_spec.name
    )
    final_spec = summary.rocket_spec.model_copy(update={"name": resolved_name})

    if save_ork_asset_file and isinstance(ork_bytes_or_asset, bytes):
        save_ork_asset(f"{cleaned_id}.ork", ork_bytes_or_asset, repo_root=repo_root)

    preset = rocket_preset_from_spec(
        final_spec,
        motor_preset_name=base_motor_id,
        power_off_drag_asset=power_off_drag_asset,
        power_on_drag_asset=power_on_drag_asset,
        drag_table=summary.drag_table,
    )
    save_rocket_preset(preset, preset_id=cleaned_id, repo_root=repo_root)

    return summary.model_copy(
        update={
            "rocket_id": cleaned_id,
            "rocket_spec": final_spec,
        }
    )


__all__ = [
    "import_and_save_ork_rocket",
    "list_ork_assets",
    "preview_ork_import",
    "save_ork_asset",
]
