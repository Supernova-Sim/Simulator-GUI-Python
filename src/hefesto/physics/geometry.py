"""Pure geometry calculations and blocking casing-fit guards."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from hefesto.domain import GeometryValidationError, GrainSpec, MotorSpec, NoseConeKind
from hefesto.physics.constants import (
    DEFAULT_DERIVATIVE_STEP_M,
    GEOMETRY_TOLERANCE_M,
    INCHES_PER_METER,
)


def _require_finite(value: float, name: str) -> float:
    if not math.isfinite(value):
        raise GeometryValidationError(f"{name} must be finite, got {value!r}")
    return value


def _require_positive(value: float, name: str) -> float:
    _require_finite(value, name)
    if value <= 0.0:
        raise GeometryValidationError(f"{name} must be > 0, got {value!r}")
    return value


def _require_non_negative(value: float, name: str) -> float:
    _require_finite(value, name)
    if value < 0.0:
        raise GeometryValidationError(f"{name} must be >= 0, got {value!r}")
    return value


@dataclass(frozen=True)
class EffectiveGrainGeometry:
    """Equivalent single-grain BATES dimensions derived from an arbitrary grain stack."""

    grain_count: int
    total_propellant_length_m: float
    stack_length_m: float
    total_volume_m3: float
    effective_height_m: float
    effective_outer_radius_m: float
    effective_inner_radius_m: float


@dataclass(frozen=True)
class PolygonProperties:
    """2D polygon area and centroid computed with the Shoelace formula."""

    area_m2: float
    centroid_x_m: float
    centroid_y_m: float


@dataclass(frozen=True)
class RasaeroFinGeometry:
    """Trapezoidal fin dimensions converted to inches for RASAero export."""

    root_chord_in: float
    tip_chord_in: float
    sweep_distance_in: float
    span_in: float


def compute_grain_stack_length(
    grains: Sequence[GrainSpec],
    grain_separation_m: float,
) -> float:
    """Return total axial length of stacked grains including inter-grain gaps."""
    if not grains:
        raise GeometryValidationError("At least one propellant grain is required")
    _require_non_negative(grain_separation_m, "grain_separation_m")
    total_propellant = sum(_require_positive(grain.length_m, "grain.length_m") for grain in grains)
    return total_propellant + (len(grains) - 1) * grain_separation_m


def validate_grain_casing_dimensions(
    grains: Sequence[GrainSpec],
    grain_separation_m: float,
    casing_length_m: float,
    casing_inner_radius_m: float,
    internal_clearance_m: float = 0.0,
) -> None:
    """Enforce blocking axial and radial fit limits before instantiating RocketPy."""
    _require_positive(casing_length_m, "casing_length_m")
    _require_positive(casing_inner_radius_m, "casing_inner_radius_m")
    _require_non_negative(internal_clearance_m, "internal_clearance_m")
    if internal_clearance_m >= casing_length_m:
        raise GeometryValidationError(
            f"internal_clearance_m ({internal_clearance_m:.4f} m) must be less than "
            f"casing_length_m ({casing_length_m:.4f} m)"
        )

    stack_length_m = compute_grain_stack_length(grains, grain_separation_m)
    available_length_m = casing_length_m - internal_clearance_m
    if stack_length_m - available_length_m > GEOMETRY_TOLERANCE_M:
        raise GeometryValidationError(
            f"Grain stack {stack_length_m:.4f} m exceeds available casing "
            f"{available_length_m:.4f} m"
        )

    max_outer_radius_m = max(
        _require_positive(grain.outer_radius_m, "grain.outer_radius_m") for grain in grains
    )
    if max_outer_radius_m - casing_inner_radius_m > GEOMETRY_TOLERANCE_M:
        raise GeometryValidationError(
            f"Grain outer radius {max_outer_radius_m:.6f} m exceeds casing inner radius "
            f"{casing_inner_radius_m:.6f} m"
        )


def validate_grain_casing_fit(motor: MotorSpec) -> None:
    """Validate that a MotorSpec's propellant grains fit inside its motor casing."""
    validate_grain_casing_dimensions(
        grains=motor.grains,
        grain_separation_m=motor.grain_separation_m,
        casing_length_m=motor.casing.length_m,
        casing_inner_radius_m=motor.casing.inner_radius_m,
        internal_clearance_m=motor.casing.internal_clearance_m,
    )


def derive_effective_grain_geometry(
    grains: Sequence[GrainSpec],
    grain_separation_m: float = 0.0,
) -> EffectiveGrainGeometry:
    """Collapse a multi-grain BATES stack into RocketPy's volume-equivalent grain geometry."""
    stack_length_m = compute_grain_stack_length(grains, grain_separation_m)
    total_volume_m3 = 0.0
    total_propellant_length_m = 0.0
    weighted_outer_radius = 0.0

    for grain in grains:
        _require_positive(grain.outer_radius_m, "grain.outer_radius_m")
        _require_non_negative(grain.inner_radius_m, "grain.inner_radius_m")
        if grain.inner_radius_m >= grain.outer_radius_m:
            raise GeometryValidationError(
                f"grain.inner_radius_m ({grain.inner_radius_m}) must be < "
                f"grain.outer_radius_m ({grain.outer_radius_m})"
            )
        total_volume_m3 += hollow_cylinder_volume_m3(
            grain.outer_radius_m, grain.inner_radius_m, grain.length_m
        )
        total_propellant_length_m += grain.length_m
        weighted_outer_radius += grain.outer_radius_m * grain.length_m

    grain_count = len(grains)
    effective_height_m = total_propellant_length_m / grain_count
    effective_outer_radius_m = weighted_outer_radius / total_propellant_length_m
    inner_sq = max(
        0.0,
        effective_outer_radius_m**2 - total_volume_m3 / (math.pi * total_propellant_length_m),
    )
    return EffectiveGrainGeometry(
        grain_count=grain_count,
        total_propellant_length_m=total_propellant_length_m,
        stack_length_m=stack_length_m,
        total_volume_m3=total_volume_m3,
        effective_height_m=effective_height_m,
        effective_outer_radius_m=effective_outer_radius_m,
        effective_inner_radius_m=math.sqrt(inner_sq),
    )


def hollow_cylinder_volume_m3(
    outer_radius_m: float,
    inner_radius_m: float,
    length_m: float,
) -> float:
    """Return the volume of a hollow cylindrical shell (or solid cylinder if inner_radius == 0)."""
    _require_positive(outer_radius_m, "outer_radius_m")
    _require_non_negative(inner_radius_m, "inner_radius_m")
    _require_positive(length_m, "length_m")
    if inner_radius_m > outer_radius_m:
        raise GeometryValidationError(
            f"inner_radius_m ({inner_radius_m}) cannot exceed outer_radius_m ({outer_radius_m})"
        )
    return math.pi * (outer_radius_m**2 - inner_radius_m**2) * length_m


def compute_polygon_properties(
    points_m: Sequence[tuple[float, float]],
) -> PolygonProperties:
    """Compute polygon area and centroid using the Shoelace formula."""
    if len(points_m) < 3:
        raise GeometryValidationError(
            f"Polygon requires at least 3 vertices, got {len(points_m)}"
        )

    for idx, (x_m, y_m) in enumerate(points_m):
        _require_finite(x_m, f"points_m[{idx}].x")
        _require_finite(y_m, f"points_m[{idx}].y")

    area_twice = 0.0
    cx_num = 0.0
    cy_num = 0.0
    count = len(points_m)
    for idx in range(count):
        x1, y1 = points_m[idx]
        x2, y2 = points_m[(idx + 1) % count]
        cross = x1 * y2 - x2 * y1
        area_twice += cross
        cx_num += (x1 + x2) * cross
        cy_num += (y1 + y2) * cross

    area_signed = area_twice / 2.0
    if math.isclose(area_signed, 0.0, abs_tol=1e-15):
        raise GeometryValidationError("Polygon has zero area (collinear or degenerate vertices)")

    return PolygonProperties(
        area_m2=abs(area_signed),
        centroid_x_m=cx_num / (6.0 * area_signed),
        centroid_y_m=cy_num / (6.0 * area_signed),
    )


def trapezoidal_fin_points_m(
    root_chord_m: float,
    tip_chord_m: float,
    sweep_length_m: float,
    span_le_m: float,
    span_te_m: float | None = None,
) -> tuple[tuple[float, float], ...]:
    """Build standard four-vertex fin planform coordinates in meters."""
    _require_positive(root_chord_m, "root_chord_m")
    _require_non_negative(tip_chord_m, "tip_chord_m")
    _require_finite(sweep_length_m, "sweep_length_m")
    _require_positive(span_le_m, "span_le_m")
    te_span = span_le_m if span_te_m is None else _require_positive(span_te_m, "span_te_m")
    return (
        (0.0, 0.0),
        (sweep_length_m, span_le_m),
        (sweep_length_m + tip_chord_m, te_span),
        (root_chord_m, 0.0),
    )


def fin_to_rasaero(
    root_chord_m: float,
    tip_chord_m: float,
    sweep_length_m: float,
    span_le_m: float,
    span_te_m: float | None = None,
    span_mode: Literal["le", "te", "mean"] = "mean",
) -> RasaeroFinGeometry:
    """Convert trapezoidal fin geometry from SI meters into RASAero inches."""
    _require_positive(root_chord_m, "root_chord_m")
    _require_non_negative(tip_chord_m, "tip_chord_m")
    _require_finite(sweep_length_m, "sweep_length_m")
    _require_positive(span_le_m, "span_le_m")
    te_span = span_le_m if span_te_m is None else _require_positive(span_te_m, "span_te_m")

    span_by_mode = {
        "le": span_le_m,
        "te": te_span,
        "mean": (span_le_m + te_span) / 2.0,
    }
    if span_mode not in span_by_mode:
        raise GeometryValidationError(f"Unsupported span_mode: {span_mode!r}")

    return RasaeroFinGeometry(
        root_chord_in=root_chord_m * INCHES_PER_METER,
        tip_chord_in=tip_chord_m * INCHES_PER_METER,
        sweep_distance_in=sweep_length_m * INCHES_PER_METER,
        span_in=span_by_mode[span_mode] * INCHES_PER_METER,
    )


def _conical_radius(x_m: float, length_m: float, base_radius_m: float) -> float:
    return base_radius_m * (x_m / length_m)


def _haack_radius(x_m: float, length_m: float, base_radius_m: float) -> float:
    # Clamp argument to [-1, 1] to guard acos against endpoint rounding drift.
    arg = max(-1.0, min(1.0, 1.0 - 2.0 * x_m / length_m))
    theta = math.acos(arg)
    val = theta - math.sin(2.0 * theta) / 2.0
    return (base_radius_m / math.sqrt(math.pi)) * math.sqrt(max(0.0, val))


def _ogive_radius(x_m: float, length_m: float, base_radius_m: float) -> float:
    rho = (base_radius_m**2 + length_m**2) / (2.0 * base_radius_m)
    return math.sqrt(max(0.0, rho**2 - (length_m - x_m) ** 2)) + base_radius_m - rho


_NOSE_PROFILE_BY_KIND: dict[str, Callable[[float, float, float], float]] = {
    "conical": _conical_radius,
    "lvhaack": _haack_radius,
    "von karman": _haack_radius,
    "ogive": _ogive_radius,
}


def nose_cone_radius_at(
    x_m: float,
    length_m: float,
    base_radius_m: float,
    kind: NoseConeKind | str,
    power: float | None = None,
) -> float:
    """Evaluate nose cone outer radius r(x) at axial station x_m from tip (0) to base (L)."""
    _require_positive(length_m, "length_m")
    _require_positive(base_radius_m, "base_radius_m")
    _require_finite(x_m, "x_m")
    if x_m < -GEOMETRY_TOLERANCE_M or x_m > length_m + GEOMETRY_TOLERANCE_M:
        raise GeometryValidationError(
            f"x_m ({x_m}) must lie within nose cone [0, {length_m}]"
        )
    x_clamped = max(0.0, min(length_m, x_m))
    kind_key = (kind.value if isinstance(kind, NoseConeKind) else kind).strip().lower()

    if kind_key == NoseConeKind.POWERSERIES.value:
        if power is None or not math.isfinite(power) or power <= 0.0:
            raise GeometryValidationError(
                f"power series nose cone requires positive finite power, got {power!r}"
            )
        return base_radius_m * ((x_clamped / length_m) ** power)

    profile_fn = _NOSE_PROFILE_BY_KIND.get(kind_key)
    if profile_fn is None:
        raise GeometryValidationError(f"Unsupported nose cone profile kind: {kind!r}")
    return profile_fn(x_clamped, length_m, base_radius_m)


def nose_cone_slope_at(
    x_m: float,
    length_m: float,
    base_radius_m: float,
    kind: NoseConeKind | str,
    power: float | None = None,
    eps_m: float = DEFAULT_DERIVATIVE_STEP_M,
) -> float:
    """Compute central-clamped finite-difference slope dr/dx along the nose cone profile."""
    _require_positive(length_m, "length_m")
    _require_positive(eps_m, "eps_m")
    _require_finite(x_m, "x_m")
    x_lo = max(0.0, x_m - eps_m)
    x_hi = min(length_m, x_m + eps_m)
    if x_hi <= x_lo:
        return 0.0
    r_lo = nose_cone_radius_at(x_lo, length_m, base_radius_m, kind, power=power)
    r_hi = nose_cone_radius_at(x_hi, length_m, base_radius_m, kind, power=power)
    return (r_hi - r_lo) / (x_hi - x_lo)


__all__ = [
    "EffectiveGrainGeometry",
    "PolygonProperties",
    "RasaeroFinGeometry",
    "compute_grain_stack_length",
    "compute_polygon_properties",
    "derive_effective_grain_geometry",
    "fin_to_rasaero",
    "hollow_cylinder_volume_m3",
    "nose_cone_radius_at",
    "nose_cone_slope_at",
    "trapezoidal_fin_points_m",
    "validate_grain_casing_dimensions",
    "validate_grain_casing_fit",
]
