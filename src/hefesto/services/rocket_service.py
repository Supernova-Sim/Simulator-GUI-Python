"""Rocket vehicle assembly and structural mass/inertia services."""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Sequence
from pathlib import Path

from hefesto.adapters.aerodynamics import parse_rasaero_csv_file, parse_rasaero_csv_text
from hefesto.domain import (
    AssetCategory,
    CasingResizeResult,
    CasingScalingMode,
    DragCurveSpec,
    DragCurveTable,
    FinComponent,
    FinGeometryMode,
    FinSetSpec,
    MassMode,
    MotorCasingSpec,
    MotorSpec,
    RocketComponent,
    RocketPreset,
    RocketSpec,
)
from hefesto.physics import (
    ALUMINUM_DENSITY_KG_M3,
    DEFAULT_MIN_CASE_SAFETY_FACTOR,
    DEFAULT_TARGET_CASE_SAFETY_FACTOR,
    GEOMETRY_TOLERANCE_M,
    ComponentMassProperties,
    StructureSummary,
    compute_analytical_drag_curves,
    compute_casing_shell_mass_kg,
    compute_minimum_casing_wall_thickness_m,
    derive_rocket_structure,
    recalculate_casing_dry_properties,
    resize_motor_casing,
)
from hefesto.services.asset_service import (
    DEFAULT_ROCKET_ID,
    load_drag_curve_asset,
    resolve_asset_path,
    resolve_paths,
)
from hefesto.services.motor_service import load_motor_spec, run_motor_ballistics_for_preset
from hefesto.storage import CatalogStore

CASING_MATERIAL_DENSITY_PRESETS: dict[str, float] = {
    "aluminum_6061_t6": 2700.0,
    "steel_1020_4130": 7850.0,
    "stainless_304": 8000.0,
    "carbon_fiber": 1550.0,
    "fiberglass": 1850.0,
}

CASING_MATERIAL_LABELS: dict[str, str] = {
    "aluminum_6061_t6": "Alumínio 6061-T6 (2700 kg/m³)",
    "steel_1020_4130": "Aço 1020 / 4130 (7850 kg/m³)",
    "stainless_304": "Aço Inox 304 (8000 kg/m³)",
    "carbon_fiber": "Fibra de Carbono (1550 kg/m³)",
    "fiberglass": "Fibra de Vidro (1850 kg/m³)",
    "custom": "Customizado",
}

# Float round-trip tolerance for edits that did not actually change any casing input.
_CASING_NOOP_TOLERANCE = 1e-9


def _casing_noop_result(casing: MotorCasingSpec, mode: CasingScalingMode) -> CasingResizeResult:
    """Describe an unchanged casing without rewriting the rocket CG/inertia."""
    estimated_tube_mass_kg = compute_casing_shell_mass_kg(
        casing.inner_radius_m,
        casing.wall_thickness_m,
        casing.length_m,
        casing.material_density_kg_m3 or ALUMINUM_DENSITY_KG_M3,
    )
    return CasingResizeResult(
        casing=casing,
        mode=mode,
        delta_mass_kg=0.0,
        estimated_tube_mass_kg=estimated_tube_mass_kg,
        estimated_fixed_hardware_mass_kg=casing.dry_mass_kg - estimated_tube_mass_kg,
        warnings=(),
    )


def update_rocket_motor_casing_length(
    rocket: RocketSpec,
    new_length_m: float,
    *,
    mode: CasingScalingMode = "tubular_delta",
    material_density_kg_m3: float | None = None,
    motor_position_m: float | None = None,
    grain_separation_m: float | None = None,
    internal_clearance_m: float | None = None,
    wall_thickness_m: float | None = None,
    fixed_hardware_mass_kg: float | None = None,
) -> tuple[RocketSpec, CasingResizeResult]:
    """Update motor casing length/clearance/spacing/position and recalculate rocket structure."""
    resolved_density = (
        material_density_kg_m3
        if material_density_kg_m3 is not None
        else (rocket.motor.casing.material_density_kg_m3 or ALUMINUM_DENSITY_KG_M3)
    )
    base_casing = rocket.motor.casing
    if internal_clearance_m is not None:
        clearance_val = float(internal_clearance_m)
        if clearance_val < 0.0:
            raise ValueError(f"Folga interna deve ser >= 0 m, obtido {clearance_val!r}")
        if clearance_val >= new_length_m:
            raise ValueError(
                f"Folga interna ({clearance_val:.4f} m) deve ser menor que o comprimento da "
                f"carcaça ({new_length_m:.4f} m)."
            )
        base_casing = base_casing.model_copy(update={"internal_clearance_m": clearance_val})
    if wall_thickness_m is not None:
        thickness_val = float(wall_thickness_m)
        if not math.isfinite(thickness_val) or thickness_val <= 0.0:
            raise ValueError(
                f"Espessura da parede deve ser finita e > 0 m, obtido {thickness_val!r}"
            )
        if thickness_val != base_casing.wall_thickness_m:
            # Δ tube at fixed hardware: dry mass follows the shell while closures stay put.
            base_casing = recalculate_casing_dry_properties(
                base_casing.model_copy(update={"wall_thickness_m": thickness_val}),
                base_casing=base_casing,
                case_density_kg_m3=resolved_density,
            )

    current_density = base_casing.material_density_kg_m3 or ALUMINUM_DENSITY_KG_M3
    hardware_unchanged = True
    if fixed_hardware_mass_kg is not None:
        implied_hardware_kg = (
            base_casing.dry_mass_kg
            - compute_casing_shell_mass_kg(
                base_casing.inner_radius_m,
                base_casing.wall_thickness_m,
                base_casing.length_m,
                resolved_density,
            )
        )
        hardware_unchanged = (
            abs(float(fixed_hardware_mass_kg) - implied_hardware_kg) <= _CASING_NOOP_TOLERANCE
        )
    noop_edit = (
        base_casing == rocket.motor.casing
        and abs(float(new_length_m) - rocket.motor.casing.length_m) <= _CASING_NOOP_TOLERANCE
        and abs(resolved_density - current_density) <= _CASING_NOOP_TOLERANCE
        and hardware_unchanged
        and (
            grain_separation_m is None
            or abs(float(grain_separation_m) - rocket.motor.grain_separation_m)
            <= _CASING_NOOP_TOLERANCE
        )
        and (
            motor_position_m is None
            or abs(float(motor_position_m) - rocket.motor_position_m) <= _CASING_NOOP_TOLERANCE
        )
    )
    if noop_edit:
        # Keep the preset's stored CG/I_l untouched when the edit changes no numeric input.
        return rocket, _casing_noop_result(rocket.motor.casing, mode)

    resize_result = resize_motor_casing(
        base_casing,
        new_length_m,
        mode=mode,
        material_density_kg_m3=resolved_density,
        fixed_hardware_mass_kg=fixed_hardware_mass_kg,
    )

    motor_updates: dict[str, object] = {"casing": resize_result.casing}
    if grain_separation_m is not None:
        sep_val = float(grain_separation_m)
        if sep_val < 0.0:
            raise ValueError(f"Separação entre grãos deve ser >= 0 m, obtido {sep_val!r}")
        motor_updates["grain_separation_m"] = sep_val

    updated_motor = rocket.motor.model_copy(update=motor_updates)
    warnings = list(resize_result.warnings)
    if (
        updated_motor.grain_stack_length_m - updated_motor.casing.available_grain_length_m
        > GEOMETRY_TOLERANCE_M
    ):
        warnings.append(
            f"Pilha de grãos ({updated_motor.grain_stack_length_m:.4f} m) excede o comprimento "
            f"útil da carcaça ({updated_motor.casing.available_grain_length_m:.4f} m)."
        )
    if len(warnings) != len(resize_result.warnings):
        resize_result = resize_result.model_copy(update={"warnings": tuple(warnings)})

    rocket_updates: dict[str, object] = {"motor": updated_motor}
    if motor_position_m is not None:
        rocket_updates["motor_position_m"] = float(motor_position_m)

    recalculated = recalculate_rocket_structure(rocket.model_copy(update=rocket_updates))
    return recalculated, resize_result


def estimate_motor_casing_fixed_hardware_mass_kg(
    casing: MotorCasingSpec,
    *,
    material_density_kg_m3: float,
) -> float:
    """Return the closures/nozzle mass implied by dry_mass_kg minus the cylindrical shell."""
    tube_mass_kg = compute_casing_shell_mass_kg(
        casing.inner_radius_m,
        casing.wall_thickness_m,
        casing.length_m,
        material_density_kg_m3,
    )
    return casing.dry_mass_kg - tube_mass_kg


def auto_size_rocket_motor_casing(
    rocket: RocketSpec,
    target_safety_factor: float = DEFAULT_TARGET_CASE_SAFETY_FACTOR,
    *,
    min_safety_factor: float = DEFAULT_MIN_CASE_SAFETY_FACTOR,
    repo_root: Path | None = None,
) -> RocketSpec:
    """Size the casing wall to the thinnest value meeting target FS at the active peak P0."""
    if target_safety_factor < min_safety_factor:
        raise ValueError(
            f"target_safety_factor ({target_safety_factor}) must be >= "
            f"min_case_safety_factor ({min_safety_factor})"
        )
    casing = rocket.motor.casing
    ballistics = run_motor_ballistics_for_preset(rocket.motor.name, repo_root=repo_root)
    min_wall_m = compute_minimum_casing_wall_thickness_m(
        ballistics.peak_chamber_pressure_pa,
        casing.inner_radius_m,
        casing.yield_strength_pa,
        target_safety_factor,
        min_safety_factor=min_safety_factor,
    )
    updated_rocket, _ = update_rocket_motor_casing_length(
        rocket,
        casing.length_m,
        mode="tubular_delta",
        material_density_kg_m3=casing.material_density_kg_m3,
        wall_thickness_m=min_wall_m,
    )
    return updated_rocket


# Analytical sources need a RocketSpec before the geometry model can run.
_ANALYTICAL_PLACEHOLDER_CURVE = DragCurveSpec(points=((0.0, 0.4), (1.0, 0.8)))


def _resolve_preset_drag_curves(
    preset: RocketPreset,
    *,
    repo_root: Path | str | None,
) -> tuple[DragCurveSpec, DragCurveSpec]:
    """Resolve the persisted (power_off, power_on) curve pair for a preset drag_source."""
    if preset.drag_source == "analytical":
        return _ANALYTICAL_PLACEHOLDER_CURVE, _ANALYTICAL_PLACEHOLDER_CURVE
    if preset.drag_source == "ork_sim":
        if preset.drag_table is None:
            raise ValueError(
                f"RocketPreset '{preset.name}' uses drag_source='ork_sim' without a drag_table"
            )
        return preset.drag_table.to_specs()
    if preset.drag_source == "rasaero_csv":
        csv_path = resolve_asset_path(
            AssetCategory.DRAG, preset.power_off_drag_asset, repo_root=repo_root
        )
        return parse_rasaero_csv_file(csv_path).to_specs()
    return (
        load_drag_curve_asset(preset.power_off_drag_asset, repo_root=repo_root),
        load_drag_curve_asset(preset.power_on_drag_asset, repo_root=repo_root),
    )


def with_analytical_drag(rocket: RocketSpec) -> RocketSpec:
    """Recompute the geometry-based drag curves so parametric edits never fly stale Cd."""
    power_off_drag, power_on_drag = compute_analytical_drag_curves(rocket).to_specs()
    return rocket.model_copy(
        update={"power_off_drag": power_off_drag, "power_on_drag": power_on_drag}
    )


def interpolate_drag_curve(
    mach: Sequence[float],
    cd: Sequence[float],
    target_mach: float,
) -> float:
    """Linearly interpolate Cd at target_mach, clamping to the curve ends (RocketPy parity)."""
    if len(mach) != len(cd) or len(mach) < 2:
        raise ValueError(
            f"drag curve needs matching mach/cd samples with at least 2 points, "
            f"got {len(mach)} mach and {len(cd)} cd"
        )
    if target_mach <= mach[0]:
        return cd[0]
    if target_mach >= mach[-1]:
        return cd[-1]
    upper = bisect_right(mach, target_mach)
    m0, m1 = mach[upper - 1], mach[upper]
    c0, c1 = cd[upper - 1], cd[upper]
    if m1 <= m0:
        return c0
    return c0 + (c1 - c0) * (target_mach - m0) / (m1 - m0)


def _drag_table_from_curves(rocket: RocketSpec) -> DragCurveTable:
    """Merge the stored in-memory curve pair onto a single Mach grid."""
    off_mach = [mach for mach, _ in rocket.power_off_drag.points]
    on_mach = [mach for mach, _ in rocket.power_on_drag.points]
    off_cd = [cd for _, cd in rocket.power_off_drag.points]
    on_cd = [cd for _, cd in rocket.power_on_drag.points]
    if off_mach == on_mach:
        return DragCurveTable(
            mach=off_mach,
            cd_power_off=off_cd,
            cd_power_on=on_cd,
            source=rocket.drag_source,
        )
    grid = sorted({*off_mach, *on_mach})
    return DragCurveTable(
        mach=grid,
        cd_power_off=[interpolate_drag_curve(off_mach, off_cd, mach) for mach in grid],
        cd_power_on=[interpolate_drag_curve(on_mach, on_cd, mach) for mach in grid],
        source=rocket.drag_source,
    )


def preview_rocket_drag_curves(rocket: RocketSpec) -> DragCurveTable:
    """Materialize the active power_off/power_on Cd(Mach) table for any RocketSpec.drag_source."""
    if rocket.drag_source == "analytical":
        return compute_analytical_drag_curves(rocket)
    return _drag_table_from_curves(rocket)


_RASAERO_ALPHA_TOLERANCE_DEG = 1e-6


def _rasaero_alpha_row(table: DragCurveTable, alpha_deg: float, filename: str) -> int | None:
    """Return the alpha grid row for alpha_deg, or None for single-alpha exports."""
    if not table.alpha_deg:
        if abs(alpha_deg) > _RASAERO_ALPHA_TOLERANCE_DEG:
            raise ValueError(
                f"{filename}: export contains only alpha=0 rows, requested alpha={alpha_deg:g}"
            )
        return None
    for index, alpha in enumerate(table.alpha_deg):
        if abs(alpha - alpha_deg) <= _RASAERO_ALPHA_TOLERANCE_DEG:
            return index
    raise ValueError(
        f"{filename}: alpha={alpha_deg:g} not in the RASAero II export; "
        f"available angles: {table.alpha_deg}"
    )


def list_rasaero_csv_angles(csv_content: str, filename: str = "rasaero.csv") -> tuple[float, ...]:
    """List the angle-of-attack rows exported by RASAero II (empty for a single axial table)."""
    if not csv_content.strip():
        raise ValueError(f"{filename}: RASAero CSV is empty")
    return tuple(parse_rasaero_csv_text(csv_content, source_name=filename).alpha_deg)


def import_rasaero_drag_csv(
    rocket: RocketSpec,
    csv_content: str,
    filename: str = "rasaero.csv",
    alpha_deg: float = 0.0,
) -> RocketSpec:
    """Parse a RASAero II CSV export into the rocket's active drag curves and validate the spec."""
    if not csv_content.strip():
        raise ValueError(f"{filename}: RASAero CSV is empty")
    table = parse_rasaero_csv_text(csv_content, source_name=filename)
    row = _rasaero_alpha_row(table, alpha_deg, filename)
    if row is None:
        power_off_drag, power_on_drag = table.to_specs()
    else:
        power_off_drag = DragCurveSpec(
            points=tuple(zip(table.mach, table.cd_alpha_power_off[row], strict=True))
        )
        power_on_drag = DragCurveSpec(
            points=tuple(zip(table.mach, table.cd_alpha_power_on[row], strict=True))
        )
    updated = rocket.model_copy(
        update={
            "drag_source": "rasaero_csv",
            "power_off_drag": power_off_drag,
            "power_on_drag": power_on_drag,
        }
    )
    return RocketSpec.model_validate(updated.model_dump())


def build_rocket_spec(
    preset: RocketPreset,
    *,
    motor: MotorSpec | None = None,
    dry_mass_override_kg: float | None = None,
    simulate_ric: bool = False,
    repo_root: Path | str | None = None,
) -> RocketSpec:
    """Assemble an in-memory RocketSpec from a RocketPreset and relative drag/motor assets."""
    resolved_motor = (
        load_motor_spec(
            preset.motor_preset_name,
            simulate_ric=simulate_ric,
            repo_root=repo_root,
        )
        if motor is None
        else motor
    )
    power_off_drag, power_on_drag = _resolve_preset_drag_curves(preset, repo_root=repo_root)
    resolved_override = (
        preset.dry_mass_override_kg if dry_mass_override_kg is None else dry_mass_override_kg
    )

    rocket = RocketSpec(
        name=preset.name,
        coordinate_system=preset.coordinate_system,
        radius_m=preset.radius_m,
        center_of_mass_without_motor_m=preset.center_of_mass_without_motor_m,
        inertia_kg_m2=preset.inertia_kg_m2,
        motor_position_m=preset.motor_position_m,
        components=preset.components,
        dry_mass_override_kg=resolved_override,
        nose_cone=preset.nose_cone,
        fins=preset.fins,
        rail_buttons=preset.rail_buttons,
        parachutes=preset.parachutes,
        power_off_drag=power_off_drag,
        power_on_drag=power_on_drag,
        motor=resolved_motor,
        drag_source=preset.drag_source,
        surface_finish=preset.surface_finish,
    )
    if rocket.drag_source == "analytical":
        return with_analytical_drag(rocket)
    return rocket


def load_rocket_spec(
    rocket_id: str = DEFAULT_ROCKET_ID,
    *,
    motor_id: str | None = None,
    motor: MotorSpec | None = None,
    dry_mass_override_kg: float | None = None,
    simulate_ric: bool = False,
    repo_root: Path | str | None = None,
) -> RocketSpec:
    """Load a RocketPreset by ID and assemble its RocketSpec."""
    preset = CatalogStore(resolve_paths(repo_root)).load_rocket(rocket_id)
    resolved_motor = motor
    if resolved_motor is None and motor_id is not None:
        resolved_motor = load_motor_spec(
            motor_id,
            simulate_ric=simulate_ric,
            repo_root=repo_root,
        )
    return build_rocket_spec(
        preset,
        motor=resolved_motor,
        dry_mass_override_kg=dry_mass_override_kg,
        simulate_ric=simulate_ric,
        repo_root=repo_root,
    )


def summarize_rocket_structure(
    rocket: RocketSpec,
    nose_cone: ComponentMassProperties | None = None,
) -> StructureSummary:
    """Derive structural dry mass, CG, and Steiner inertia for a RocketSpec."""
    return derive_rocket_structure(rocket, nose_cone=nose_cone)


def calculate_rocket_dry_mass_kg(
    rocket: RocketSpec,
    *,
    mass_mode: MassMode = "calculated",
) -> float:
    """Compute rocket dry mass without motor according to MassMode."""
    if mass_mode == "measured":
        if rocket.dry_mass_override_kg is None:
            raise ValueError(
                "mass_mode='measured' requires rocket.dry_mass_override_kg to be set"
            )
        return rocket.dry_mass_override_kg
    if mass_mode == "calculated":
        return derive_rocket_structure(rocket).dry_mass_kg
    raise ValueError(f"Unsupported mass_mode: {mass_mode!r}")


def recalculate_rocket_structure(rocket: RocketSpec) -> RocketSpec:
    """Recalculate dry CG/inertia and refresh analytical drag for parametric edits."""
    summary = derive_rocket_structure(rocket)
    updated = rocket.model_copy(
        update={
            "center_of_mass_without_motor_m": summary.center_of_mass_m,
            "inertia_kg_m2": summary.inertia_kg_m2,
        }
    )
    if updated.drag_source == "analytical":
        return with_analytical_drag(updated)
    return updated


def trapezoidal_to_shape_points(
    root_chord_m: float,
    tip_chord_m: float,
    span_m: float,
    sweep_length_m: float = 0.0,
) -> tuple[tuple[float, float], ...]:
    """Convert trapezoidal fin parameters into a 4-vertex nose_to_tail polygon."""
    return (
        (0.0, 0.0),
        (sweep_length_m, span_m),
        (sweep_length_m + tip_chord_m, span_m),
        (root_chord_m, 0.0),
    )


def sync_rocket_fins(
    rocket: RocketSpec,
    fins: FinSetSpec,
    *,
    thickness_m: float | None = None,
    density_kg_m3: float | None = None,
    fin_geometry_mode: FinGeometryMode = "freeform",
) -> RocketSpec:
    """Update FinSetSpec, synchronize matching FinComponent(s), and recalculate structure."""
    resolved_fins = fins
    if (
        fin_geometry_mode == "trapezoidal"
        and fins.root_chord_m is not None
        and fins.tip_chord_m is not None
        and fins.span_m is not None
    ):
        points = trapezoidal_to_shape_points(
            fins.root_chord_m,
            fins.tip_chord_m,
            fins.span_m,
            0.0 if fins.sweep_length_m is None else float(fins.sweep_length_m),
        )
        resolved_fins = fins.model_copy(update={"shape_points_m": points})
    if thickness_m is not None and resolved_fins.thickness_m != thickness_m:
        resolved_fins = resolved_fins.model_copy(update={"thickness_m": thickness_m})

    updated_components: list[RocketComponent] = []
    for comp in rocket.components:
        if isinstance(comp, FinComponent):
            updates: dict[str, object] = {
                "name": resolved_fins.name,
                "count": resolved_fins.count,
                "position_m": resolved_fins.position_m,
                "shape_points_m": resolved_fins.shape_points_m,
            }
            if thickness_m is not None:
                updates["thickness_m"] = thickness_m
            if density_kg_m3 is not None:
                updates["density_kg_m3"] = density_kg_m3
            updated_components.append(comp.model_copy(update=updates))
        else:
            updated_components.append(comp)

    updated_rocket = rocket.model_copy(
        update={
            "fins": resolved_fins,
            "components": tuple(updated_components),
        }
    )
    return recalculate_rocket_structure(updated_rocket)


def rocket_preset_from_spec(
    rocket: RocketSpec,
    *,
    motor_preset_name: str | None = None,
    power_off_drag_asset: str | None = None,
    power_on_drag_asset: str | None = None,
    drag_table: DragCurveTable | None = None,
) -> RocketPreset:
    """Convert an in-memory RocketSpec into a persistable RocketPreset DTO."""
    resolved_drag_table: DragCurveTable | None = None
    if rocket.drag_source == "ork_sim":
        resolved_drag_table = (
            drag_table if drag_table is not None else _drag_table_from_curves(rocket)
        )
    return RocketPreset(
        name=rocket.name,
        coordinate_system=rocket.coordinate_system,
        radius_m=rocket.radius_m,
        center_of_mass_without_motor_m=rocket.center_of_mass_without_motor_m,
        inertia_kg_m2=rocket.inertia_kg_m2,
        motor_position_m=rocket.motor_position_m,
        components=rocket.components,
        dry_mass_override_kg=rocket.dry_mass_override_kg,
        nose_cone=rocket.nose_cone,
        fins=rocket.fins,
        rail_buttons=rocket.rail_buttons,
        parachutes=rocket.parachutes,
        power_off_drag_asset=(
            power_off_drag_asset
            or rocket.power_off_drag.asset_name
            or "power_off.csv"
        ),
        power_on_drag_asset=(
            power_on_drag_asset
            or rocket.power_on_drag.asset_name
            or "power_on.csv"
        ),
        motor_preset_name=motor_preset_name or rocket.motor.name,
        drag_source=rocket.drag_source,
        surface_finish=rocket.surface_finish,
        drag_table=resolved_drag_table,
    )


__all__ = [
    "CASING_MATERIAL_DENSITY_PRESETS",
    "CASING_MATERIAL_LABELS",
    "auto_size_rocket_motor_casing",
    "build_rocket_spec",
    "calculate_rocket_dry_mass_kg",
    "estimate_motor_casing_fixed_hardware_mass_kg",
    "import_rasaero_drag_csv",
    "interpolate_drag_curve",
    "list_rasaero_csv_angles",
    "load_rocket_spec",
    "preview_rocket_drag_curves",
    "recalculate_rocket_structure",
    "rocket_preset_from_spec",
    "summarize_rocket_structure",
    "sync_rocket_fins",
    "trapezoidal_to_shape_points",
    "update_rocket_motor_casing_length",
    "with_analytical_drag",
]
