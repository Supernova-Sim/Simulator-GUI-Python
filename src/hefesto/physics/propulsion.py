"""Pure propulsion preparation, blocking casing-fit checks, and shell mass scaling."""

from __future__ import annotations

import math
from dataclasses import dataclass

from hefesto.domain import (
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
    "prepare_solid_motor",
    "recalculate_casing_dry_properties",
]
