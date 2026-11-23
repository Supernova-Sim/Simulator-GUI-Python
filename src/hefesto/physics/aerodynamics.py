"""Analytical subsonic drag build-up from RocketSpec geometry (pure math, no I/O).

The four additive terms are normalized by the reference area ``A_ref = pi * R_ref^2``:

1. skin friction  - turbulent Prandtl-Schlichting coefficient bounded by the surface
   roughness, Hoerner compressibility correction and body/fin form factors;
2. pressure       - nose profile/fineness plus a calibrated compressible rise;
3. base           - ``(0.12 + 0.13 M^2)`` subsonic / ``0.25 / M`` supersonic, with the
   powered phase relieved by the nozzle *exit* area times an explicit empirical
   efficiency (OpenRocket's powered Cd already embeds most of that relief);
4. protuberances  - rail buttons/launch lugs frontal area immersed in the boundary layer
   plus fin-root/fuselage interference.

The coefficients below are calibrated against the 3.442 ``<datapoint>`` embedded in
``data/assets/openrocket/hefesto_1.41.ork`` (see ``tests/physics/test_aerodynamics.py``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from hefesto.domain import (
    SURFACE_ROUGHNESS_M,
    DragCurveTable,
    FinComponent,
    NoseConeKind,
    RocketSpec,
    TubeComponent,
)
from hefesto.physics.constants import DEFAULT_FIN_THICKNESS_M, GEOMETRY_TOLERANCE_M
from hefesto.physics.geometry import compute_polygon_properties, nose_cone_radius_at

# Reference (ISA sea level) atmosphere: the analytical model is a function of Mach only.
REFERENCE_DENSITY_KG_M3: Final[float] = 1.225
REFERENCE_SOUND_SPEED_M_S: Final[float] = 340.294
REFERENCE_VISCOSITY_PA_S: Final[float] = 1.7894e-5

# Default Mach grid: 0.000 to 3.000 step 0.025 (covers every calibration Mach exactly).
DEFAULT_MACH_GRID: Final[tuple[float, ...]] = tuple(index * 0.025 for index in range(121))

_PRANDTL_SCHLICHTING_COEFFICIENT: Final[float] = 0.455
_PRANDTL_SCHLICHTING_EXPONENT: Final[float] = 2.58
_HOERNER_ROUGH_OFFSET: Final[float] = 1.89
_HOERNER_ROUGH_SLOPE: Final[float] = 1.62
_HOERNER_ROUGH_EXPONENT: Final[float] = -2.5
_HOERNER_COMPRESSIBILITY_SLOPE: Final[float] = 0.15
_HOERNER_COMPRESSIBILITY_EXPONENT: Final[float] = -0.58

_BODY_FORM_FACTOR_CUBIC: Final[float] = 60.0
_BODY_FORM_FACTOR_LINEAR: Final[float] = 0.0025
_FIN_THICKNESS_FORM_FACTOR: Final[float] = 2.0

_BASE_DRAG_SUBSONIC_OFFSET: Final[float] = 0.12
_BASE_DRAG_SUBSONIC_SLOPE: Final[float] = 0.13
_BASE_DRAG_SUPERSONIC_COEFFICIENT: Final[float] = 0.25
# Jet blockage assumed when the motor carries no nozzle geometry (central grain, ~5% of base).
DEFAULT_PLUME_AREA_FRACTION: Final[float] = 0.05
# Empirical fraction of the full exit-area plume relief retained by the OpenRocket
# powered-phase convention: OpenRocket's powered Cd already embeds most of the base-drag
# reduction, so applying the full physical relief would double count it.
PLUME_RELIEF_EFFICIENCY: Final[float] = 0.19

# Nose pressure drag at incompressible conditions, referenced to A_ref.
_NOSE_PRESSURE_CD: Final[dict[NoseConeKind, float]] = {
    NoseConeKind.VON_KARMAN: 0.019,
    NoseConeKind.LV_HAACK: 0.019,
    NoseConeKind.OGIVE: 0.025,
    # RASAero/OpenRocket parabolic and elliptical profiles map to the closest domain kind.
    NoseConeKind.POWERSERIES: 0.021,
    NoseConeKind.CONICAL: 0.033,
}
_NOSE_FINENESS_PENALTY: Final[float] = 0.5

# Calibrated compressible pressure rise: mild M^2 growth plus a transonic knee.
# Joint least squares over OpenRocket's pressure_drag_coeff column and the total Cd
# curve (equal relative weights) at Mach 0.1/0.3/0.5/0.7/0.9/0.95 from hefesto_1.41.ork.
_PRESSURE_SUBSONIC_RISE: Final[float] = 0.6692
_PRESSURE_TRANSONIC_RISE: Final[float] = 1.0416
_PRESSURE_TRANSONIC_EXPONENT: Final[float] = 10.256
_PRESSURE_RISE_MACH_START: Final[float] = 0.50
_PRESSURE_RISE_MACH_END: Final[float] = 1.05

_RAIL_BUTTON_CD: Final[float] = 0.8
_RAIL_BUTTON_IMMERSION: Final[float] = 0.55
_RAIL_BUTTON_EXPOSED_HEIGHT_M: Final[float] = 0.02
_RAIL_BUTTON_DEFAULT_RADIUS_M: Final[float] = 0.01

_FIN_ROOT_INTERFERENCE: Final[float] = 0.13

# Friction needs a non-zero dynamic pressure; below this Mach the Reynolds number freezes.
_MIN_FRICTION_MACH: Final[float] = 0.05
_NOSE_SLICES: Final[int] = 200
_POLYGON_TOLERANCE_M: Final[float] = 1e-9


@dataclass(frozen=True)
class _FinGeometry:
    """Aggregated wetted/trailing-edge areas and mean chord for the fin set."""

    count: int
    wetted_area_m2: float
    trailing_edge_area_m2: float
    thickness_m: float
    mean_chord_m: float
    root_chord_m: float


def _fin_polygon_edges(points: Sequence[tuple[float, float]]) -> list[float]:
    count = len(points)
    return [
        math.dist(points[index], points[(index + 1) % count]) for index in range(count)
    ]


def _root_chord_m(points: Sequence[tuple[float, float]]) -> float:
    """Return the chord of the polygon edge attached to the body (lowest y)."""
    min_y = min(y for _, y in points)
    count = len(points)
    root_chords = [
        abs(points[(index + 1) % count][0] - points[index][0])
        for index in range(count)
        if abs(points[index][1] - min_y) <= _POLYGON_TOLERANCE_M
        and abs(points[(index + 1) % count][1] - min_y) <= _POLYGON_TOLERANCE_M
    ]
    if root_chords:
        return max(root_chords)
    xs = [x for x, _ in points]
    return max(xs) - min(xs)


def _fin_geometry(rocket: RocketSpec) -> _FinGeometry:
    """Aggregate fin planform/wetted areas from structural FinComponents (or the FinSetSpec)."""
    components = [c for c in rocket.components if isinstance(c, FinComponent)]
    if not components:
        fins = rocket.fins
        components = [
            FinComponent(
                name=fins.name,
                count=fins.count,
                shape_points_m=fins.shape_points_m,
                thickness_m=DEFAULT_FIN_THICKNESS_M,
                density_kg_m3=1.0,
                position_m=fins.position_m,
            )
        ]

    count = 0
    wetted_area_m2 = 0.0
    trailing_edge_area_m2 = 0.0
    total_thickness_m = 0.0
    total_mean_chord_m = 0.0
    total_root_chord_m = 0.0
    for component in components:
        points = component.shape_points_m
        area_m2 = compute_polygon_properties(points).area_m2
        perimeter_m = sum(_fin_polygon_edges(points))
        span = max(y for _, y in points) - min(y for _, y in points)
        if span <= 0.0:
            raise ValueError(f"Fin '{component.name}' has zero radial span")
        count += component.count
        wetted_area_m2 += component.count * (2.0 * area_m2 + perimeter_m * component.thickness_m)
        trailing_edge_area_m2 += component.count * component.thickness_m * span
        total_thickness_m += component.thickness_m
        total_mean_chord_m += area_m2 / span
        total_root_chord_m += _root_chord_m(points)

    sets = len(components)
    return _FinGeometry(
        count=count,
        wetted_area_m2=wetted_area_m2,
        trailing_edge_area_m2=trailing_edge_area_m2,
        thickness_m=total_thickness_m / sets,
        mean_chord_m=total_mean_chord_m / sets,
        root_chord_m=total_root_chord_m / sets,
    )


def body_tubes(rocket: RocketSpec) -> tuple[TubeComponent, ...]:
    """Return the airframe tubes (flush with R_ref) that contribute wetted area."""
    tubes = tuple(
        component for component in rocket.components if isinstance(component, TubeComponent)
    )
    flush = tuple(
        tube
        for tube in tubes
        if tube.outer_radius_m >= rocket.radius_m - 1e-3
    )
    return flush or tubes


def total_length_m(rocket: RocketSpec) -> float:
    """Return the reference length (nose tip to tail) used for the Reynolds number."""
    return rocket.nose_cone.length_m + sum(tube.length_m for tube in body_tubes(rocket))


def reference_area_m2(rocket: RocketSpec) -> float:
    """Return the reference area A_ref = pi * R_ref^2 used to normalize every Cd term."""
    return math.pi * rocket.radius_m**2


def base_area_m2(rocket: RocketSpec) -> float:
    """Return the aft-facing area: airframe base plus fin trailing edges."""
    fins = _fin_geometry(rocket)
    return math.pi * rocket.radius_m**2 + fins.trailing_edge_area_m2


def _nose_wetted_area_m2(rocket: RocketSpec) -> float:
    nose = rocket.nose_cone
    base_radius = nose.base_radius_m if nose.base_radius_m is not None else rocket.radius_m
    length = nose.length_m
    dx = length / _NOSE_SLICES
    area = 0.0
    for index in range(_NOSE_SLICES):
        x_m = (index + 0.5) * dx
        radius = nose_cone_radius_at(x_m, length, base_radius, nose.kind, power=nose.power)
        radius_next = nose_cone_radius_at(
            min(length, x_m + dx), length, base_radius, nose.kind, power=nose.power
        )
        slope = (radius_next - radius) / dx
        area += 2.0 * math.pi * radius * math.sqrt(1.0 + slope**2) * dx
    return area


def _skin_friction_coefficient(reynolds: float, length_m: float, roughness_m: float) -> float:
    """Prandtl-Schlichting turbulent Cf bounded below by the fully rough plate limit."""
    smooth = _PRANDTL_SCHLICHTING_COEFFICIENT / (
        math.log10(max(reynolds, 1.0)) ** _PRANDTL_SCHLICHTING_EXPONENT
    )
    roughness_ratio = max(length_m / max(roughness_m, 1e-9), 1.0 + 1e-9)
    rough = (
        _HOERNER_ROUGH_OFFSET + _HOERNER_ROUGH_SLOPE * math.log10(roughness_ratio)
    ) ** _HOERNER_ROUGH_EXPONENT
    return max(smooth, rough)


def skin_friction_drag_cd(rocket: RocketSpec, mach: float) -> float:
    """Return the skin-friction drag coefficient at the given Mach number."""
    area_ref = reference_area_m2(rocket)
    length_m = total_length_m(rocket)
    body_length_m = max(length_m - rocket.nose_cone.length_m, GEOMETRY_TOLERANCE_M)
    roughness_m = SURFACE_ROUGHNESS_M[rocket.surface_finish]

    reynolds = (
        REFERENCE_DENSITY_KG_M3
        * max(mach, _MIN_FRICTION_MACH)
        * REFERENCE_SOUND_SPEED_M_S
        * length_m
        / REFERENCE_VISCOSITY_PA_S
    )
    compressibility = (
        1.0 + _HOERNER_COMPRESSIBILITY_SLOPE * mach**2
    ) ** _HOERNER_COMPRESSIBILITY_EXPONENT
    coefficient = _skin_friction_coefficient(reynolds, length_m, roughness_m) * compressibility

    fineness = body_length_m / (2.0 * rocket.radius_m)
    body_form_factor = (
        1.0
        + _BODY_FORM_FACTOR_CUBIC / fineness**3
        + _BODY_FORM_FACTOR_LINEAR * fineness
    )

    fins = _fin_geometry(rocket)
    thickness_ratio = fins.thickness_m / fins.mean_chord_m
    fin_form_factor = 1.0 + _FIN_THICKNESS_FORM_FACTOR * thickness_ratio

    wetted_body_m2 = sum(
        math.pi * 2.0 * tube.outer_radius_m * tube.length_m for tube in body_tubes(rocket)
    ) + _nose_wetted_area_m2(rocket)

    return coefficient * (
        body_form_factor * wetted_body_m2 + fin_form_factor * fins.wetted_area_m2
    ) / area_ref


def _nose_pressure_cd(rocket: RocketSpec) -> float:
    coefficient = _NOSE_PRESSURE_CD.get(rocket.nose_cone.kind, 0.025)
    fineness = rocket.nose_cone.length_m / (2.0 * rocket.radius_m)
    return coefficient * (1.0 + _NOSE_FINENESS_PENALTY / fineness**2)


def _protuberance_cd(rocket: RocketSpec) -> float:
    radius = rocket.rail_buttons.radius_m
    if radius is None or radius <= 0.0:
        return 0.0
    exposed_height = _RAIL_BUTTON_EXPOSED_HEIGHT_M
    frontal_area = 2.0 * (2.0 * radius * exposed_height)
    return (
        frontal_area * _RAIL_BUTTON_CD * _RAIL_BUTTON_IMMERSION / reference_area_m2(rocket)
    )


def _fin_interference_cd(rocket: RocketSpec) -> float:
    fins = _fin_geometry(rocket)
    return (
        _FIN_ROOT_INTERFERENCE
        * fins.count
        * fins.thickness_m
        * fins.root_chord_m
        / reference_area_m2(rocket)
    )


def pressure_drag_cd(rocket: RocketSpec, mach: float) -> float:
    """Return nose/transition/protuberance pressure drag with the compressible rise."""
    incompressible_cd = (
        _nose_pressure_cd(rocket) + _protuberance_cd(rocket) + _fin_interference_cd(rocket)
    )
    span = _PRESSURE_RISE_MACH_END - _PRESSURE_RISE_MACH_START
    unit = min(1.0, max(0.0, (mach - _PRESSURE_RISE_MACH_START) / span))
    rise = (
        1.0
        + _PRESSURE_SUBSONIC_RISE * mach**2
        + _PRESSURE_TRANSONIC_RISE * unit**_PRESSURE_TRANSONIC_EXPONENT
    )
    return incompressible_cd * rise


def base_drag_coefficient(rocket: RocketSpec, mach: float) -> float:
    """Return the power-off base drag coefficient (plume attenuation applied elsewhere)."""
    area_ratio = base_area_m2(rocket) / reference_area_m2(rocket)
    if mach < 1.0:
        coefficient = _BASE_DRAG_SUBSONIC_OFFSET + _BASE_DRAG_SUBSONIC_SLOPE * mach**2
    else:
        coefficient = _BASE_DRAG_SUPERSONIC_COEFFICIENT / mach
    return coefficient * area_ratio


def plume_area_fraction(rocket: RocketSpec) -> float:
    """Return the nozzle-exit blockage fraction A_exit/A_base of the power-on base drag."""
    base_area = base_area_m2(rocket)
    nozzle = rocket.motor.nozzle
    exit_area = math.pi * nozzle.exit_radius_m**2 if nozzle is not None else 0.0
    if exit_area <= 0.0 or base_area <= 0.0:
        return DEFAULT_PLUME_AREA_FRACTION
    return min(1.0, exit_area / base_area)


def plume_relief_fraction(rocket: RocketSpec) -> float:
    """Return the empirical base-drag relief fraction applied while the motor burns."""
    return plume_area_fraction(rocket) * PLUME_RELIEF_EFFICIENCY


def compute_analytical_drag_curves(
    rocket: RocketSpec,
    mach_grid: Sequence[float] | None = None,
) -> DragCurveTable:
    """Build power_off/power_on Cd(Mach) from RocketSpec geometry (see module docstring)."""
    grid = tuple(float(mach) for mach in (DEFAULT_MACH_GRID if mach_grid is None else mach_grid))
    if len(grid) < 2:
        raise ValueError(f"mach_grid requires at least 2 points, got {len(grid)}")
    previous: float | None = None
    for index, mach in enumerate(grid):
        if not math.isfinite(mach) or mach < 0.0:
            raise ValueError(f"mach_grid[{index}] must be finite and >= 0, got {mach!r}")
        if previous is not None and mach <= previous:
            raise ValueError(f"mach_grid must strictly increase at [{index}]: {previous} -> {mach}")
        previous = mach

    plume = plume_relief_fraction(rocket)
    cd_power_off: list[float] = []
    cd_power_on: list[float] = []
    for mach in grid:
        base_cd = base_drag_coefficient(rocket, mach)
        total_off = skin_friction_drag_cd(rocket, mach) + pressure_drag_cd(rocket, mach) + base_cd
        cd_power_off.append(total_off)
        cd_power_on.append(total_off - base_cd * plume)

    return DragCurveTable(
        mach=list(grid),
        cd_power_off=cd_power_off,
        cd_power_on=cd_power_on,
        source="analytical",
    )


__all__ = [
    "DEFAULT_MACH_GRID",
    "DEFAULT_PLUME_AREA_FRACTION",
    "PLUME_RELIEF_EFFICIENCY",
    "REFERENCE_DENSITY_KG_M3",
    "REFERENCE_SOUND_SPEED_M_S",
    "REFERENCE_VISCOSITY_PA_S",
    "base_area_m2",
    "base_drag_coefficient",
    "body_tubes",
    "compute_analytical_drag_curves",
    "plume_area_fraction",
    "plume_relief_fraction",
    "pressure_drag_cd",
    "reference_area_m2",
    "skin_friction_drag_cd",
    "total_length_m",
]
