"""Pure propulsion preparation, blocking casing-fit checks, and shell mass scaling."""

from __future__ import annotations

import math
from dataclasses import dataclass

from hefesto.domain import (
    CasingResizeResult,
    CasingScalingMode,
    GeometryValidationError,
    MotorCasingSpec,
    MotorSpec,
)
from hefesto.physics.constants import ALUMINUM_DENSITY_KG_M3, MOTOR_COORDINATE_SYSTEM
from hefesto.physics.geometry import (
    EffectiveGrainGeometry,
    derive_effective_grain_geometry,
    hollow_cylinder_volume_m3,
    validate_grain_casing_fit,
)
from hefesto.physics.inertia import compute_motor_casing_dry_inertia_kg_m2
from hefesto.physics.structure import summarize_thrust_curve


@dataclass(frozen=True)
class PreparedSolidMotor:
    """Validated SI propulsion parameters ready for RocketPy SolidMotor construction."""

    effective_grain: EffectiveGrainGeometry
    casing: MotorCasingSpec
    propellant_mass_kg: float
    loaded_mass_kg: float
    delta_shell_mass_kg: float
    thrust_points: list[tuple[float, float]]
    total_impulse_ns: float
    max_thrust_n: float


def _require_positive_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0.0:
        raise GeometryValidationError(f"{name} must be finite and > 0, got {value!r}")
    return float(value)


def compute_casing_shell_mass_kg(
    inner_radius_m: float,
    wall_thickness_m: float,
    length_m: float,
    case_density_kg_m3: float = ALUMINUM_DENSITY_KG_M3,
) -> float:
    """Return cylindrical casing shell mass in kg from inner radius, wall thickness, and length."""
    r_inner = _require_positive_finite(inner_radius_m, "inner_radius_m")
    thickness = _require_positive_finite(wall_thickness_m, "wall_thickness_m")
    length = _require_positive_finite(length_m, "length_m")
    density = _require_positive_finite(case_density_kg_m3, "case_density_kg_m3")
    volume_m3 = hollow_cylinder_volume_m3(r_inner + thickness, r_inner, length)
    return volume_m3 * density


def compute_minimum_casing_wall_thickness_m(
    max_chamber_pressure_pa: float,
    inner_radius_m: float,
    yield_strength_pa: float,
    target_safety_factor: float = 1.5,
    step_m: float = 0.0001,
) -> float:
    """Return the thinnest wall rounding up to step_m that reaches the target safety factor."""
    pressure = _require_positive_finite(max_chamber_pressure_pa, "max_chamber_pressure_pa")
    inner_radius = _require_positive_finite(inner_radius_m, "inner_radius_m")
    yield_strength = _require_positive_finite(yield_strength_pa, "yield_strength_pa")
    step = _require_positive_finite(step_m, "step_m")
    target = _require_positive_finite(target_safety_factor, "target_safety_factor")
    if target < 1.0:
        raise GeometryValidationError(
            f"target_safety_factor must be >= 1.0, got {target_safety_factor!r}"
        )
    # Same thin-wall hoop law as compute_case_hoop_stress_pa: sigma = P0*r_i/t, FS = yield/sigma.
    ideal_wall_m = target * pressure * inner_radius / yield_strength
    steps = math.ceil(ideal_wall_m / step)
    wall_m = steps * step
    # ceil can land a ULP below the ideal ratio; bump one step so FS is never under target.
    while yield_strength * wall_m / (pressure * inner_radius) < target:
        steps += 1
        wall_m = steps * step
    return wall_m


def recalculate_casing_dry_properties(
    casing: MotorCasingSpec,
    base_casing: MotorCasingSpec | None = None,
    *,
    case_density_kg_m3: float = ALUMINUM_DENSITY_KG_M3,
) -> MotorCasingSpec:
    """Recalculate motor dry mass via dry_mass_base + delta_m_shell and update dry inertia."""
    density = _require_positive_finite(case_density_kg_m3, "case_density_kg_m3")
    center_of_dry_mass_m = casing.center_of_dry_mass_m

    if base_casing is not None:
        base_shell_mass_kg = compute_casing_shell_mass_kg(
            base_casing.inner_radius_m,
            base_casing.wall_thickness_m,
            base_casing.length_m,
            density,
        )
        target_shell_mass_kg = compute_casing_shell_mass_kg(
            casing.inner_radius_m,
            casing.wall_thickness_m,
            casing.length_m,
            density,
        )
        delta_shell_mass_kg = target_shell_mass_kg - base_shell_mass_kg
        dry_mass_kg = base_casing.dry_mass_kg + delta_shell_mass_kg
        if not math.isfinite(dry_mass_kg) or dry_mass_kg <= 0.0:
            raise GeometryValidationError(
                f"Recalculated casing dry mass must be > 0 kg, got {dry_mass_kg!r}"
            )
        # Preserve relative CG placement if length changed without a manual CG override.
        if not math.isclose(
            casing.length_m, base_casing.length_m, rel_tol=1e-12, abs_tol=1e-12
        ) and math.isclose(
            casing.center_of_dry_mass_m,
            base_casing.center_of_dry_mass_m,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            center_of_dry_mass_m = base_casing.center_of_dry_mass_m * (
                casing.length_m / base_casing.length_m
            )
    else:
        dry_mass_kg = casing.dry_mass_kg

    dry_inertia_kg_m2 = compute_motor_casing_dry_inertia_kg_m2(
        dry_mass_kg=dry_mass_kg,
        inner_radius_m=casing.inner_radius_m,
        wall_thickness_m=casing.wall_thickness_m,
        length_m=casing.length_m,
    )
    return casing.model_copy(
        update={
            "dry_mass_kg": dry_mass_kg,
            "dry_inertia_kg_m2": dry_inertia_kg_m2,
            "center_of_dry_mass_m": center_of_dry_mass_m,
        }
    )


def resize_motor_casing(
    casing: MotorCasingSpec,
    new_length_m: float,
    *,
    mode: CasingScalingMode = "tubular_delta",
    material_density_kg_m3: float = ALUMINUM_DENSITY_KG_M3,
    fixed_hardware_mass_kg: float | None = None,
) -> CasingResizeResult:
    """Resize casing length and update dry mass, CG, and inertia without numerical drift.

    fixed_hardware_mass_kg pins the closures/nozzle mass instead of inheriting
    dry_mass_kg - shell_mass_kg, so the dry mass becomes cylindrical shell + hardware.
    """
    if isinstance(new_length_m, bool) or not math.isfinite(new_length_m) or new_length_m <= 0.0:
        raise ValueError(f"new_length_m deve ser finito e > 0, obtido {new_length_m!r}")
    if (
        isinstance(material_density_kg_m3, bool)
        or not math.isfinite(material_density_kg_m3)
        or material_density_kg_m3 <= 0.0
    ):
        raise ValueError(
            f"material_density_kg_m3 deve ser finito e > 0, obtido {material_density_kg_m3!r}"
        )
    if fixed_hardware_mass_kg is not None and (
        isinstance(fixed_hardware_mass_kg, bool)
        or not math.isfinite(fixed_hardware_mass_kg)
        or fixed_hardware_mass_kg < 0.0
    ):
        raise ValueError(
            f"fixed_hardware_mass_kg deve ser finito e >= 0, "
            f"obtido {fixed_hardware_mass_kg!r}"
        )

    length_val = float(new_length_m)
    density_val = float(material_density_kg_m3)
    if length_val <= casing.internal_clearance_m:
        raise ValueError(
            f"Comprimento da carcaça ({length_val:.4f} m) deve ser maior que a folga interna "
            f"({casing.internal_clearance_m:.4f} m)."
        )

    r_out = casing.inner_radius_m + casing.wall_thickness_m
    a_wall = math.pi * (r_out**2 - casing.inner_radius_m**2)
    old_tube_mass_kg = density_val * a_wall * casing.length_m
    estimated_tube_mass_kg = density_val * a_wall * length_val
    implied_hardware_mass_kg = casing.dry_mass_kg - old_tube_mass_kg
    hardware_overridden = fixed_hardware_mass_kg is not None
    resolved_hardware_mass_kg = (
        float(fixed_hardware_mass_kg) if hardware_overridden else implied_hardware_mass_kg
    )

    warnings: list[str] = []
    if mode == "tubular_delta" and not hardware_overridden and implied_hardware_mass_kg < 0.0:
        warnings.append(
            f"Massa seca do preset ({casing.dry_mass_kg:.3f} kg) é menor que a massa teórica "
            f"do tubo ({old_tube_mass_kg:.3f} kg) para ρ={density_val:.0f} kg/m³; "
            "possível divergência de material ou espessura no preset."
        )

    # Preserve exact original values when length and hardware are unchanged (Golden parity).
    if length_val == casing.length_m and not hardware_overridden:
        return CasingResizeResult(
            casing=casing,
            mode=mode,
            delta_mass_kg=0.0,
            estimated_tube_mass_kg=old_tube_mass_kg,
            estimated_fixed_hardware_mass_kg=implied_hardware_mass_kg,
            warnings=tuple(warnings),
        )

    if mode == "tubular_delta" or hardware_overridden:
        if hardware_overridden:
            delta_mass_kg = (estimated_tube_mass_kg - old_tube_mass_kg) + (
                resolved_hardware_mass_kg - implied_hardware_mass_kg
            )
        else:
            delta_mass_kg = density_val * a_wall * (length_val - casing.length_m)
        m_new = casing.dry_mass_kg + delta_mass_kg
        if not math.isfinite(m_new) or m_new <= 0.0:
            raise ValueError(
                f"O comprimento {length_val:.4f} m reduziria a massa seca da carcaça para "
                f"{m_new:.4f} kg (<= 0 kg)."
            )
        hardware_cg_m: float | None = None
        if hardware_overridden and implied_hardware_mass_kg > 0.0:
            # Hardware keeps the axial CG implied by the edited casing, scaled with length.
            candidate = (
                casing.dry_mass_kg * casing.center_of_dry_mass_m
                - old_tube_mass_kg * 0.5 * casing.length_m
            ) / implied_hardware_mass_kg
            if math.isfinite(candidate) and 0.0 <= candidate <= casing.length_m:
                hardware_cg_m = candidate
        if hardware_cg_m is None:
            cg_new = (casing.center_of_dry_mass_m / casing.length_m) * length_val
        else:
            cg_new = (
                estimated_tube_mass_kg * 0.5 * length_val
                + resolved_hardware_mass_kg * hardware_cg_m * (length_val / casing.length_m)
            ) / m_new
        inertia_new = compute_motor_casing_dry_inertia_kg_m2(
            dry_mass_kg=m_new,
            inner_radius_m=casing.inner_radius_m,
            wall_thickness_m=casing.wall_thickness_m,
            length_m=length_val,
        )
        updated_casing = casing.model_copy(
            update={
                "length_m": length_val,
                "dry_mass_kg": m_new,
                "center_of_dry_mass_m": cg_new,
                "dry_inertia_kg_m2": inertia_new,
                "material_density_kg_m3": density_val,
            }
        )
    elif mode == "proportional":
        scale = length_val / casing.length_m
        m_new = casing.dry_mass_kg * scale
        delta_mass_kg = m_new - casing.dry_mass_kg
        cg_new = casing.center_of_dry_mass_m * scale
        inertia_new = compute_motor_casing_dry_inertia_kg_m2(
            dry_mass_kg=m_new,
            inner_radius_m=casing.inner_radius_m,
            wall_thickness_m=casing.wall_thickness_m,
            length_m=length_val,
        )
        updated_casing = casing.model_copy(
            update={
                "length_m": length_val,
                "dry_mass_kg": m_new,
                "center_of_dry_mass_m": cg_new,
                "dry_inertia_kg_m2": inertia_new,
            }
        )
    elif mode == "manual":
        delta_mass_kg = 0.0
        updated_casing = casing.model_copy(update={"length_m": length_val})
    else:
        raise ValueError(f"Modo de escala da carcaça não suportado: {mode!r}")

    return CasingResizeResult(
        casing=updated_casing,
        mode=mode,
        delta_mass_kg=delta_mass_kg,
        estimated_tube_mass_kg=estimated_tube_mass_kg,
        estimated_fixed_hardware_mass_kg=resolved_hardware_mass_kg,
        warnings=tuple(warnings),
    )


def prepare_solid_motor(
    motor: MotorSpec,
    *,
    base_casing: MotorCasingSpec | None = None,
    case_density_kg_m3: float = ALUMINUM_DENSITY_KG_M3,
) -> PreparedSolidMotor:
    """Validate grain-casing fit and derive RocketPy-ready propulsion parameters in SI."""
    if motor.coordinate_system != MOTOR_COORDINATE_SYSTEM:
        raise GeometryValidationError(
            f"Motor coordinate_system must be {MOTOR_COORDINATE_SYSTEM!r}, "
            f"got {motor.coordinate_system!r}"
        )

    validate_grain_casing_fit(motor)
    effective_grain = derive_effective_grain_geometry(motor.grains, motor.grain_separation_m)

    if base_casing is not None:
        resolved_casing = recalculate_casing_dry_properties(
            motor.casing,
            base_casing=base_casing,
            case_density_kg_m3=case_density_kg_m3,
        )
        delta_shell_mass_kg = resolved_casing.dry_mass_kg - base_casing.dry_mass_kg
    else:
        resolved_casing = motor.casing
        delta_shell_mass_kg = 0.0

    propellant_mass_kg = effective_grain.total_volume_m3 * motor.propellant_density_kg_m3
    loaded_mass_kg = resolved_casing.dry_mass_kg + propellant_mass_kg
    thrust_points = [(float(time_s), float(thrust_n)) for time_s, thrust_n in motor.thrust_curve]
    thrust_summary = summarize_thrust_curve(thrust_points)

    return PreparedSolidMotor(
        effective_grain=effective_grain,
        casing=resolved_casing,
        propellant_mass_kg=propellant_mass_kg,
        loaded_mass_kg=loaded_mass_kg,
        delta_shell_mass_kg=delta_shell_mass_kg,
        thrust_points=thrust_points,
        total_impulse_ns=thrust_summary.total_impulse_ns,
        max_thrust_n=thrust_summary.max_thrust_n,
    )


__all__ = [
    "PreparedSolidMotor",
    "compute_casing_shell_mass_kg",
    "compute_minimum_casing_wall_thickness_m",
    "prepare_solid_motor",
    "recalculate_casing_dry_properties",
    "resize_motor_casing",
]
