"""Axisymmetric inertia tensor calculations and Steiner parallel-axis aggregation."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from hefesto.physics.constants import GEOMETRY_TOLERANCE_M


def _require_non_negative_finite(value: float, name: str) -> float:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and >= 0, got {value!r}")
    return value


@dataclass(frozen=True)
class InertiaContribution:
    """Single structural element contribution to center of mass and Steiner inertia."""

    name: str
    mass_kg: float
    cg_m: float
    i_transverse_local_kg_m2: float
    i_longitudinal_local_kg_m2: float


def hollow_cylinder_inertia_kg_m2(
    mass_kg: float,
    outer_radius_m: float,
    inner_radius_m: float,
    length_m: float,
) -> tuple[float, float]:
    """Return local (I_transverse, I_longitudinal) for a hollow or solid cylinder."""
    _require_non_negative_finite(mass_kg, "mass_kg")
    _require_non_negative_finite(outer_radius_m, "outer_radius_m")
    _require_non_negative_finite(inner_radius_m, "inner_radius_m")
    _require_non_negative_finite(length_m, "length_m")
    if inner_radius_m > outer_radius_m + GEOMETRY_TOLERANCE_M:
        raise ValueError(
            f"inner_radius_m ({inner_radius_m}) cannot exceed outer_radius_m ({outer_radius_m})"
        )

    r_sq_sum = outer_radius_m**2 + inner_radius_m**2
    i_longitudinal = 0.5 * mass_kg * r_sq_sum
    i_transverse = (mass_kg / 12.0) * (3.0 * r_sq_sum + length_m**2)
    return i_transverse, i_longitudinal


def point_mass_inertia_kg_m2(
    mass_kg: float,
    equivalent_radius_m: float = 0.0,
    length_m: float = 0.0,
) -> tuple[float, float]:
    """Return local (I_transverse, I_longitudinal) for a lumped mass or equivalent cylinder."""
    return hollow_cylinder_inertia_kg_m2(mass_kg, equivalent_radius_m, 0.0, length_m)


def fin_set_inertia_kg_m2(
    total_mass_kg: float,
    radial_cg_m: float,
) -> tuple[float, float]:
    """Return local (I_transverse, I_longitudinal) for a symmetric fin set around body axis."""
    _require_non_negative_finite(total_mass_kg, "total_mass_kg")
    _require_non_negative_finite(radial_cg_m, "radial_cg_m")
    i_longitudinal = total_mass_kg * (radial_cg_m**2)
    i_transverse = 0.5 * i_longitudinal
    return i_transverse, i_longitudinal


def compute_center_of_mass_m(contributions: Sequence[InertiaContribution]) -> float:
    """Compute mass-weighted center of mass along the vehicle longitudinal axis."""
    if not contributions:
        raise ValueError("At least one InertiaContribution is required")
    total_mass = 0.0
    moment = 0.0
    for item in contributions:
        _require_non_negative_finite(item.mass_kg, f"{item.name}.mass_kg")
        if not math.isfinite(item.cg_m):
            raise ValueError(f"{item.name}.cg_m must be finite, got {item.cg_m!r}")
        total_mass += item.mass_kg
        moment += item.mass_kg * item.cg_m
    return moment / total_mass if total_mass > 0.0 else 0.0


def compute_steiner_inertia_kg_m2(
    contributions: Sequence[InertiaContribution],
    reference_cg_m: float | None = None,
) -> tuple[float, float, float]:
    """Aggregate local inertias via parallel-axis theorem into RocketPy (I_t, I_t, I_l)."""
    cg = (
        compute_center_of_mass_m(contributions)
        if reference_cg_m is None
        else reference_cg_m
    )
    if not math.isfinite(cg):
        raise ValueError(f"reference_cg_m must be finite, got {cg!r}")

    i_longitudinal = 0.0
    i_transverse = 0.0
    for item in contributions:
        _require_non_negative_finite(item.mass_kg, f"{item.name}.mass_kg")
        _require_non_negative_finite(
            item.i_transverse_local_kg_m2, f"{item.name}.i_transverse_local_kg_m2"
        )
        _require_non_negative_finite(
            item.i_longitudinal_local_kg_m2, f"{item.name}.i_longitudinal_local_kg_m2"
        )
        i_longitudinal += item.i_longitudinal_local_kg_m2
        i_transverse += item.i_transverse_local_kg_m2 + item.mass_kg * ((item.cg_m - cg) ** 2)

    return (i_transverse, i_transverse, i_longitudinal)


def compute_motor_casing_dry_inertia_kg_m2(
    dry_mass_kg: float,
    inner_radius_m: float,
    wall_thickness_m: float,
    length_m: float,
    override_inertia_kg_m2: tuple[float, float, float] | None = None,
) -> tuple[float, float, float]:
    """Return RocketPy motor dry inertia (I_t, I_t, I_l) from casing shell or override."""
    if override_inertia_kg_m2 is not None:
        i_t1, i_t2, i_l = override_inertia_kg_m2
        if not all(math.isfinite(val) and val > 0.0 for val in (i_t1, i_t2, i_l)):
            raise ValueError(
                "override_inertia_kg_m2 must be positive and finite, "
                f"got {override_inertia_kg_m2!r}"
            )
        if not math.isclose(i_t1, i_t2, rel_tol=1e-6, abs_tol=1e-12):
            raise ValueError(
                f"override_inertia_kg_m2 must be axisymmetric (I_t, I_t, I_l), "
                f"got {override_inertia_kg_m2!r}"
            )
        return override_inertia_kg_m2

    _require_non_negative_finite(wall_thickness_m, "wall_thickness_m")
    outer_radius_m = inner_radius_m + wall_thickness_m
    i_transverse, i_longitudinal = hollow_cylinder_inertia_kg_m2(
        dry_mass_kg,
        outer_radius_m,
        inner_radius_m,
        length_m,
    )
    return (i_transverse, i_transverse, i_longitudinal)


__all__ = [
    "InertiaContribution",
    "compute_center_of_mass_m",
    "compute_motor_casing_dry_inertia_kg_m2",
    "compute_steiner_inertia_kg_m2",
    "fin_set_inertia_kg_m2",
    "hollow_cylinder_inertia_kg_m2",
    "point_mass_inertia_kg_m2",
]
