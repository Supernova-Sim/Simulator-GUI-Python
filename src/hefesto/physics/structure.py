"""Structural component, nose cone, Steiner aggregation, and motor casing derivations."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from hefesto.domain import (
    FinComponent,
    GeometryValidationError,
    GrainSpec,
    NoseConeSpec,
    PointMassComponent,
    RocketComponent,
    RocketSpec,
    TubeComponent,
    validate_nose_cone_shell_thickness,
)
from hefesto.physics.constants import (
    ALUMINUM_DENSITY_KG_M3,
    DEFAULT_NOSE_CONE_SLICES,
    GEOMETRY_TOLERANCE_M,
)
from hefesto.physics.geometry import (
    EffectiveGrainGeometry,
    compute_polygon_properties,
    derive_effective_grain_geometry,
    hollow_cylinder_volume_m3,
    nose_cone_radius_at,
    nose_cone_slope_at,
    validate_grain_casing_dimensions,
)
from hefesto.physics.inertia import (
    InertiaContribution,
    compute_center_of_mass_m,
    compute_motor_casing_dry_inertia_kg_m2,
    compute_steiner_inertia_kg_m2,
    fin_set_inertia_kg_m2,
    hollow_cylinder_inertia_kg_m2,
    point_mass_inertia_kg_m2,
)


def _require_non_negative(value: float, name: str) -> float:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and >= 0, got {value!r}")
    return value


def _require_positive(value: float, name: str) -> float:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and > 0, got {value!r}")
    return value


@dataclass(frozen=True)
class ComponentMassProperties:
    """Mass, axial center of mass (nose_to_tail), and local principal moments of inertia."""

    name: str
    mass_kg: float
    cg_m: float
    i_longitudinal_local_kg_m2: float
    i_transverse_local_kg_m2: float

    def to_inertia_contribution(self) -> InertiaContribution:
        return InertiaContribution(
            name=self.name,
            mass_kg=self.mass_kg,
            cg_m=self.cg_m,
            i_transverse_local_kg_m2=self.i_transverse_local_kg_m2,
            i_longitudinal_local_kg_m2=self.i_longitudinal_local_kg_m2,
        )


@dataclass(frozen=True)
class StructureSummary:
    """Aggregated dry mass, center of mass, and RocketPy (I_t, I_t, I_l) inertia tensor."""

    dry_mass_kg: float
    center_of_mass_m: float
    inertia_kg_m2: tuple[float, float, float]
    i_transverse_kg_m2: float
    i_longitudinal_kg_m2: float
    components: tuple[ComponentMassProperties, ...]


@dataclass(frozen=True)
class MotorMassProperties:
    """Derived motor propellant, casing, dry inertia, and loaded mass properties."""

    propellant_mass_kg: float
    propellant_volume_m3: float
    effective_grain: EffectiveGrainGeometry
    grains_center_of_mass_m: float
    case_length_m: float
    case_outer_radius_m: float
    dry_mass_kg: float
    loaded_mass_kg: float
    center_of_dry_mass_m: float
    dry_inertia_kg_m2: tuple[float, float, float]


@dataclass(frozen=True)
class ThrustCurveSummary:
    """Integrated thrust-curve summary metrics."""

    total_impulse_ns: float
    burn_time_s: tuple[float, float]
    max_thrust_n: float


def derive_tube_properties(
    component: TubeComponent,
    extra_mass_kg: float = 0.0,
) -> ComponentMassProperties:
    """Compute mass and local inertia for a cylindrical shell or solid bulkhead."""
    _require_non_negative(extra_mass_kg, "extra_mass_kg")
    volume_m3 = hollow_cylinder_volume_m3(
        component.outer_radius_m,
        component.inner_radius_m,
        component.length_m,
    )
    # An imported OpenRocket override replaces the density-derived shell mass.
    mass_kg = (
        component.mass_override_kg
        if component.mass_override_kg is not None
        else volume_m3 * component.density_kg_m3
    ) + extra_mass_kg
    i_transverse, i_longitudinal = hollow_cylinder_inertia_kg_m2(
        mass_kg,
        component.outer_radius_m,
        component.inner_radius_m,
        component.length_m,
    )
    return ComponentMassProperties(
        name=component.name,
        mass_kg=mass_kg,
        cg_m=(
            component.cg_override_m
            if component.cg_override_m is not None
            else component.position_m
        ),
        i_longitudinal_local_kg_m2=i_longitudinal,
        i_transverse_local_kg_m2=i_transverse,
    )


def derive_point_mass_properties(
    component: PointMassComponent,
    equivalent_radius_m: float = 0.0,
    length_m: float = 0.0,
) -> ComponentMassProperties:
    """Compute mass and optional equivalent-cylinder local inertia for a lumped mass."""
    i_transverse, i_longitudinal = point_mass_inertia_kg_m2(
        component.mass_kg,
        equivalent_radius_m=equivalent_radius_m,
        length_m=length_m,
    )
    return ComponentMassProperties(
        name=component.name,
        mass_kg=component.mass_kg,
        cg_m=component.position_m,
        i_longitudinal_local_kg_m2=i_longitudinal,
        i_transverse_local_kg_m2=i_transverse,
    )


def derive_fin_component_properties(
    component: FinComponent,
    rocket_radius_m: float,
) -> ComponentMassProperties:
    """Compute fin set mass, axial CG, and radial-offset inertia via Shoelace polygon area."""
    _require_positive(rocket_radius_m, "rocket_radius_m")
    polygon = compute_polygon_properties(component.shape_points_m)
    unit_volume_m3 = polygon.area_m2 * component.thickness_m
    total_mass_kg = component.count * component.density_kg_m3 * unit_volume_m3
    radial_cg_m = rocket_radius_m + polygon.centroid_y_m
    i_transverse, i_longitudinal = fin_set_inertia_kg_m2(total_mass_kg, radial_cg_m)
    return ComponentMassProperties(
        name=component.name,
        mass_kg=total_mass_kg,
        cg_m=component.position_m + polygon.centroid_x_m,
        i_longitudinal_local_kg_m2=i_longitudinal,
        i_transverse_local_kg_m2=i_transverse,
    )


def derive_component_properties(
    component: RocketComponent,
    rocket_radius_m: float,
) -> ComponentMassProperties:
    """Dispatch mass and local inertia derivation for any RocketComponent variant."""
    if isinstance(component, TubeComponent):
        return derive_tube_properties(component)
    if isinstance(component, PointMassComponent):
        return derive_point_mass_properties(component)
    if isinstance(component, FinComponent):
        return derive_fin_component_properties(component, rocket_radius_m)
    raise TypeError(f"Unsupported RocketComponent: {type(component)!r}")


def derive_nose_cone_properties(
    nose_cone: NoseConeSpec,
    wall_thickness_m: float,
    density_kg_m3: float,
    base_radius_m: float | None = None,
    extra_mass_kg: float = 0.0,
    extra_mass_position_m: float | None = None,
    slices: int = DEFAULT_NOSE_CONE_SLICES,
) -> ComponentMassProperties:
    """Integrate hollow nose cone shell mass, CG, and local inertia over midpoint slices."""
    resolved_base_radius = (
        nose_cone.base_radius_m if nose_cone.base_radius_m is not None else base_radius_m
    )
    if resolved_base_radius is None:
        raise GeometryValidationError(
            "base_radius_m must be provided when NoseConeSpec.base_radius_m is None"
        )
    _require_positive(resolved_base_radius, "base_radius_m")
    _require_non_negative(wall_thickness_m, "wall_thickness_m")
    try:
        validate_nose_cone_shell_thickness(wall_thickness_m, resolved_base_radius)
    except ValueError as exc:
        raise GeometryValidationError(str(exc)) from exc
    _require_positive(density_kg_m3, "density_kg_m3")
    _require_non_negative(extra_mass_kg, "extra_mass_kg")
    if extra_mass_position_m is not None and not math.isfinite(extra_mass_position_m):
        raise ValueError(
            f"extra_mass_position_m must be finite, got {extra_mass_position_m!r}"
        )
    if slices < 1:
        raise ValueError(f"slices must be >= 1, got {slices}")

    length_m = nose_cone.length_m
    dx = length_m / slices
    m_shell = 0.0
    moment = 0.0
    i_xx = 0.0
    solid_volume_m3 = 0.0
    x_samples: list[float] = []
    r_samples: list[float] = []
    dm_samples: list[float] = []

    for idx in range(slices):
        x_m = (idx + 0.5) * dx
        r_m = nose_cone_radius_at(
            x_m,
            length_m,
            resolved_base_radius,
            nose_cone.kind,
            power=nose_cone.power,
            haack_parameter=nose_cone.haack_parameter,
        )
        dr_dx = nose_cone_slope_at(
            x_m,
            length_m,
            resolved_base_radius,
            nose_cone.kind,
            power=nose_cone.power,
            haack_parameter=nose_cone.haack_parameter,
        )
        ds = math.sqrt(1.0 + dr_dx**2) * dx
        dm = 2.0 * math.pi * r_m * ds * wall_thickness_m * density_kg_m3
        m_shell += dm
        solid_volume_m3 += math.pi * r_m**2 * dx
        moment += x_m * dm
        i_xx += (r_m**2) * dm
        x_samples.append(x_m)
        r_samples.append(r_m)
        dm_samples.append(dm)

    shell_volume_m3 = m_shell / density_kg_m3
    if shell_volume_m3 > solid_volume_m3 * (1.0 + GEOMETRY_TOLERANCE_M):
        raise GeometryValidationError(
            f"nose shell volume ({shell_volume_m3:.6f} m³) exceeds the solid nose volume "
            f"({solid_volume_m3:.6f} m³) for wall_thickness_m={wall_thickness_m}"
        )

    cg_shell = moment / m_shell if m_shell > 0.0 else 0.0
    x_extra = extra_mass_position_m if extra_mass_position_m is not None else cg_shell
    m_total = m_shell + extra_mass_kg
    cg_total = (m_shell * cg_shell + extra_mass_kg * x_extra) / m_total if m_total > 0.0 else 0.0

    i_yy_local = sum(
        ((x_m - cg_total) ** 2 + (r_m**2) / 2.0) * dm
        for x_m, r_m, dm in zip(x_samples, r_samples, dm_samples, strict=True)
    )
    if extra_mass_kg > 0.0:
        i_yy_local += extra_mass_kg * ((x_extra - cg_total) ** 2)

    return ComponentMassProperties(
        name=nose_cone.name,
        mass_kg=m_total,
        cg_m=nose_cone.position_m + cg_total,
        # Extra ballast mass contributes to axial CG and transverse inertia only.
        i_longitudinal_local_kg_m2=i_xx,
        i_transverse_local_kg_m2=i_yy_local,
    )


def aggregate_structure(
    components: Sequence[ComponentMassProperties],
    nose_cone: ComponentMassProperties | None = None,
    fins: ComponentMassProperties | None = None,
) -> StructureSummary:
    """Aggregate component mass properties with Steiner theorem into RocketPy inertia."""
    items = list(components)
    if nose_cone is not None:
        items.append(nose_cone)
    if fins is not None:
        items.append(fins)
    if not items:
        raise ValueError("At least one structural item is required for aggregation")

    contributions = [item.to_inertia_contribution() for item in items]
    dry_mass_kg = sum(item.mass_kg for item in items)
    center_of_mass_m = compute_center_of_mass_m(contributions)
    inertia_kg_m2 = compute_steiner_inertia_kg_m2(contributions, reference_cg_m=center_of_mass_m)
    return StructureSummary(
        dry_mass_kg=dry_mass_kg,
        center_of_mass_m=center_of_mass_m,
        inertia_kg_m2=inertia_kg_m2,
        i_transverse_kg_m2=inertia_kg_m2[0],
        i_longitudinal_kg_m2=inertia_kg_m2[2],
        components=tuple(items),
    )


def derive_dry_mass(rocket: RocketSpec) -> float:
    """Return RocketSpec dry mass, honoring dry_mass_override_kg when specified."""
    if rocket.dry_mass_override_kg is not None:
        return rocket.dry_mass_override_kg
    return derive_rocket_structure(rocket).dry_mass_kg


def derive_rocket_structure(
    rocket: RocketSpec,
    nose_cone: ComponentMassProperties | None = None,
) -> StructureSummary:
    """Derive structural dry mass, CG, and Steiner inertia for a RocketSpec assembly."""
    derived_components = [
        derive_component_properties(component, rocket.radius_m)
        for component in rocket.components
    ]
    # Imported nose shell lives on the nose spec so it is counted exactly once.
    shell = nose_cone
    if shell is None and rocket.nose_cone.shell is not None:
        shell = derive_point_mass_properties(rocket.nose_cone.shell)
    return aggregate_structure(derived_components, nose_cone=shell)


def compute_grain_stack_cg_m(
    grains: Sequence[GrainSpec],
    grain_separation_m: float,
    propellant_density_kg_m3: float,
    start_offset_m: float = 0.0,
) -> float:
    """Compute axial grain stack center of mass starting from start_offset_m."""
    if not grains:
        raise GeometryValidationError("At least one propellant grain is required")
    _require_non_negative(grain_separation_m, "grain_separation_m")
    _require_positive(propellant_density_kg_m3, "propellant_density_kg_m3")
    _require_non_negative(start_offset_m, "start_offset_m")

    x_cursor = start_offset_m
    total_mass_kg = 0.0
    moment = 0.0
    last_idx = len(grains) - 1
    for idx, grain in enumerate(grains):
        volume_m3 = hollow_cylinder_volume_m3(
            grain.outer_radius_m, grain.inner_radius_m, grain.length_m
        )
        mass_kg = volume_m3 * propellant_density_kg_m3
        moment += mass_kg * (x_cursor + grain.length_m / 2.0)
        total_mass_kg += mass_kg
        x_cursor += grain.length_m + (grain_separation_m if idx < last_idx else 0.0)

    return moment / total_mass_kg if total_mass_kg > 0.0 else 0.0


def derive_motor_casing_properties(
    grains: Sequence[GrainSpec],
    grain_separation_m: float,
    propellant_density_kg_m3: float,
    case_inner_radius_m: float,
    case_wall_thickness_m: float,
    case_length_m: float | None = None,
    margin_forward_side_m: float = 0.0,
    margin_nozzle_side_m: float = 0.0,
    internal_clearance_m: float = 0.0,
    case_density_kg_m3: float = ALUMINUM_DENSITY_KG_M3,
    nozzle_mass_kg: float = 0.0,
    dry_mass_extra_kg: float = 0.0,
    dry_mass_override_kg: float | None = None,
    dry_inertia_override_kg_m2: tuple[float, float, float] | None = None,
    coordinate_order: Literal[
        "nozzle_to_combustion_chamber", "forward_to_nozzle"
    ] = "nozzle_to_combustion_chamber",
) -> MotorMassProperties:
    """Derive propellant mass, casing dimensions/dry inertia, and grain CG with fit guard."""
    _require_positive(propellant_density_kg_m3, "propellant_density_kg_m3")
    _require_positive(case_inner_radius_m, "case_inner_radius_m")
    _require_positive(case_wall_thickness_m, "case_wall_thickness_m")
    _require_non_negative(margin_forward_side_m, "margin_forward_side_m")
    _require_non_negative(margin_nozzle_side_m, "margin_nozzle_side_m")
    _require_non_negative(internal_clearance_m, "internal_clearance_m")
    _require_positive(case_density_kg_m3, "case_density_kg_m3")
    _require_non_negative(nozzle_mass_kg, "nozzle_mass_kg")
    _require_non_negative(dry_mass_extra_kg, "dry_mass_extra_kg")
    if dry_mass_override_kg is not None:
        _require_positive(dry_mass_override_kg, "dry_mass_override_kg")

    effective = derive_effective_grain_geometry(grains, grain_separation_m)
    resolved_case_length = (
        case_length_m
        if case_length_m is not None
        else margin_forward_side_m + effective.stack_length_m + margin_nozzle_side_m
    )
    validate_grain_casing_dimensions(
        grains=grains,
        grain_separation_m=grain_separation_m,
        casing_length_m=resolved_case_length,
        casing_inner_radius_m=case_inner_radius_m,
        internal_clearance_m=internal_clearance_m,
    )

    propellant_mass_kg = effective.total_volume_m3 * propellant_density_kg_m3
    case_outer_radius_m = case_inner_radius_m + case_wall_thickness_m
    if dry_mass_override_kg is not None:
        dry_mass_kg = dry_mass_override_kg
    else:
        casing_shell_volume_m3 = hollow_cylinder_volume_m3(
            case_outer_radius_m,
            case_inner_radius_m,
            resolved_case_length,
        )
        dry_mass_kg = (
            casing_shell_volume_m3 * case_density_kg_m3 + nozzle_mass_kg + dry_mass_extra_kg
        )

    if coordinate_order == "forward_to_nozzle":
        cg_from_forward = compute_grain_stack_cg_m(
            grains,
            grain_separation_m,
            propellant_density_kg_m3,
            start_offset_m=margin_forward_side_m,
        )
        grains_center_of_mass_m = resolved_case_length - cg_from_forward
    elif coordinate_order == "nozzle_to_combustion_chamber":
        grains_center_of_mass_m = compute_grain_stack_cg_m(
            grains,
            grain_separation_m,
            propellant_density_kg_m3,
            start_offset_m=margin_nozzle_side_m,
        )
    else:
        raise ValueError(f"Unsupported coordinate_order: {coordinate_order!r}")

    dry_inertia_kg_m2 = compute_motor_casing_dry_inertia_kg_m2(
        dry_mass_kg=dry_mass_kg,
        inner_radius_m=case_inner_radius_m,
        wall_thickness_m=case_wall_thickness_m,
        length_m=resolved_case_length,
        override_inertia_kg_m2=dry_inertia_override_kg_m2,
    )
    return MotorMassProperties(
        propellant_mass_kg=propellant_mass_kg,
        propellant_volume_m3=effective.total_volume_m3,
        effective_grain=effective,
        grains_center_of_mass_m=grains_center_of_mass_m,
        case_length_m=resolved_case_length,
        case_outer_radius_m=case_outer_radius_m,
        dry_mass_kg=dry_mass_kg,
        loaded_mass_kg=dry_mass_kg + propellant_mass_kg,
        center_of_dry_mass_m=resolved_case_length / 2.0,
        dry_inertia_kg_m2=dry_inertia_kg_m2,
    )


def summarize_thrust_curve(
    points: Sequence[tuple[float, float]],
) -> ThrustCurveSummary:
    """Compute total impulse, burn window, and peak thrust from in-memory (t, F) points."""
    if len(points) < 2:
        raise ValueError(f"Thrust curve requires at least 2 points, got {len(points)}")
    prev_t: float | None = None
    for idx, (t_s, thrust_n) in enumerate(points):
        if not (math.isfinite(t_s) and math.isfinite(thrust_n)):
            raise ValueError(f"Thrust curve point [{idx}] must be finite: {(t_s, thrust_n)!r}")
        if t_s < 0.0 or thrust_n < 0.0:
            raise ValueError(f"Thrust curve point [{idx}] must be >= 0: {(t_s, thrust_n)!r}")
        if prev_t is not None and t_s <= prev_t:
            raise ValueError(
                f"Thrust curve time must strictly increase at [{idx}]: {prev_t} -> {t_s}"
            )
        prev_t = t_s

    times = np.array([pt[0] for pt in points], dtype=float)
    thrusts = np.array([pt[1] for pt in points], dtype=float)
    return ThrustCurveSummary(
        total_impulse_ns=float(np.trapezoid(thrusts, times)),
        burn_time_s=(float(times[0]), float(times[-1])),
        max_thrust_n=float(np.max(thrusts)),
    )


__all__ = [
    "ComponentMassProperties",
    "MotorMassProperties",
    "StructureSummary",
    "ThrustCurveSummary",
    "aggregate_structure",
    "compute_grain_stack_cg_m",
    "derive_component_properties",
    "derive_dry_mass",
    "derive_fin_component_properties",
    "derive_motor_casing_properties",
    "derive_nose_cone_properties",
    "derive_point_mass_properties",
    "derive_rocket_structure",
    "derive_tube_properties",
    "summarize_thrust_curve",
]
