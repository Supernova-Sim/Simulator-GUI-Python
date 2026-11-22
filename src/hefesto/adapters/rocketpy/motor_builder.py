"""RocketPy SolidMotor builder with blocking geometry guards and in-memory thrust curves."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

from rocketpy import SolidMotor

from hefesto.domain import GeometryValidationError, GrainInhibition, GrainSpec, MotorSpec

_GEOMETRY_TOLERANCE_M: Final[float] = 1e-12
_MOTOR_COORDINATE_SYSTEM: Final[str] = "nozzle_to_combustion_chamber"


def _require_positive_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and > 0, got {value!r}")
    return float(value)


def validate_motor_geometry_fit(motor: MotorSpec) -> None:
    """Enforce blocking axial and radial grain-to-casing limits before instantiating RocketPy."""
    if motor.coordinate_system != _MOTOR_COORDINATE_SYSTEM:
        raise GeometryValidationError(
            f"Motor coordinate_system must be {_MOTOR_COORDINATE_SYSTEM!r}, "
            f"got {motor.coordinate_system!r}"
        )
    if not motor.grains:
        raise GeometryValidationError("At least one propellant grain is required")

    for idx, grain in enumerate(motor.grains):
        if not (
            math.isfinite(grain.length_m)
            and math.isfinite(grain.outer_radius_m)
            and math.isfinite(grain.inner_radius_m)
        ):
            raise GeometryValidationError(f"Grain [{idx}] has non-finite dimensions")
        if grain.length_m <= 0.0 or grain.outer_radius_m <= 0.0 or grain.inner_radius_m < 0.0:
            raise GeometryValidationError(f"Grain [{idx}] dimensions out of physical bounds")
        if grain.inner_radius_m >= grain.outer_radius_m:
            raise GeometryValidationError(
                f"Grain [{idx}] inner_radius_m ({grain.inner_radius_m}) must be < "
                f"outer_radius_m ({grain.outer_radius_m})"
            )

    if motor.casing.internal_clearance_m >= motor.casing.length_m:
        raise GeometryValidationError(
            f"internal_clearance_m ({motor.casing.internal_clearance_m:.4f} m) must be less than "
            f"casing_length_m ({motor.casing.length_m:.4f} m)"
        )

    stack_length_m = motor.grain_stack_length_m
    available_length_m = motor.casing.available_grain_length_m
    if stack_length_m - available_length_m > _GEOMETRY_TOLERANCE_M:
        raise GeometryValidationError(
            f"Grain stack {stack_length_m:.4f} m exceeds available casing "
            f"{available_length_m:.4f} m"
        )

    max_outer_radius_m = motor.max_grain_outer_radius_m
    if max_outer_radius_m - motor.casing.inner_radius_m > _GEOMETRY_TOLERANCE_M:
        raise GeometryValidationError(
            f"Grain outer radius {max_outer_radius_m:.6f} m exceeds casing inner radius "
            f"{motor.casing.inner_radius_m:.6f} m"
        )


def _derive_effective_grain_dimensions(
    grains: Sequence[GrainSpec],
) -> tuple[int, float, float, float]:
    """Collapse multi-grain stack into RocketPy's volume-equivalent single-grain parameters."""
    total_volume_m3 = 0.0
    total_propellant_length_m = 0.0
    weighted_outer_radius = 0.0

    for grain in grains:
        total_volume_m3 += (
            math.pi * (grain.outer_radius_m**2 - grain.inner_radius_m**2) * grain.length_m
        )
        total_propellant_length_m += grain.length_m
        weighted_outer_radius += grain.outer_radius_m * grain.length_m

    grain_count = len(grains)
    # Preserve exact dimensions when uniform to avoid 1-ULP drift in RocketPy burn ODEs.
    uniform_length = all(g.length_m == grains[0].length_m for g in grains)
    uniform_outer = all(g.outer_radius_m == grains[0].outer_radius_m for g in grains)
    effective_height_m = (
        grains[0].length_m if uniform_length else total_propellant_length_m / grain_count
    )
    effective_outer_radius_m = (
        grains[0].outer_radius_m
        if uniform_outer
        else weighted_outer_radius / total_propellant_length_m
    )
    inner_sq = max(
        0.0,
        effective_outer_radius_m**2 - total_volume_m3 / (math.pi * total_propellant_length_m),
    )
    return (
        grain_count,
        effective_outer_radius_m,
        math.sqrt(inner_sq),
        effective_height_m,
    )


def _build_in_memory_thrust_points(
    motor: MotorSpec,
    thrust_factor: float,
) -> list[tuple[float, float]]:
    factor = _require_positive_finite(thrust_factor, "thrust_factor")
    points: list[tuple[float, float]] = []
    prev_t: float | None = None
    for idx, (time_s, thrust_n) in enumerate(motor.thrust_curve):
        t_val = float(time_s)
        f_val = float(thrust_n) * factor
        if not (math.isfinite(t_val) and math.isfinite(f_val)) or t_val < 0.0 or f_val < 0.0:
            raise ValueError(f"Thrust point [{idx}] must be finite and >= 0: {(t_val, f_val)!r}")
        if prev_t is not None and t_val <= prev_t:
            raise ValueError(f"Thrust curve time must strictly increase at [{idx}]")
        prev_t = t_val
        points.append((t_val, f_val))
    if len(points) < 2:
        raise ValueError("Thrust curve requires at least 2 finite points")
    return points


def build_solid_motor(
    motor: MotorSpec,
    *,
    thrust_factor: float = 1.0,
) -> SolidMotor:
    """Construct a RocketPy SolidMotor in SI after blocking grain-casing overflow checks."""
    validate_motor_geometry_fit(motor)
    thrust_points = _build_in_memory_thrust_points(motor, thrust_factor)
    grain_count, eff_outer_r, eff_inner_r, eff_height = _derive_effective_grain_dimensions(
        motor.grains
    )

    return SolidMotor(
        thrust_source=thrust_points,
        dry_mass=motor.casing.dry_mass_kg,
        dry_inertia=motor.casing.dry_inertia_kg_m2,
        nozzle_radius=motor.nozzle.exit_radius_m,
        grain_number=grain_count,
        grain_density=motor.propellant_density_kg_m3,
        grain_outer_radius=eff_outer_r,
        grain_initial_inner_radius=eff_inner_r,
        grain_initial_height=eff_height,
        grain_separation=motor.grain_separation_m,
        grains_center_of_mass_position=motor.grains_center_of_mass_m,
        center_of_dry_mass_position=motor.casing.center_of_dry_mass_m,
        nozzle_position=motor.nozzle.position_m,
        burn_time=motor.burn_time_s,
        throat_radius=motor.nozzle.throat_radius_m,
        interpolation_method=motor.interpolation_method.value,
        coordinate_system_orientation=_MOTOR_COORDINATE_SYSTEM,
        only_radial_burn=all(
            grain.inhibited_ends == GrainInhibition.BOTH for grain in motor.grains
        ),
    )


__all__ = [
    "build_solid_motor",
    "validate_motor_geometry_fit",
]
