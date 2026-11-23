"""RocketPy Rocket assembly in nose_to_tail coordinates with in-memory drag curves."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

from rocketpy import Function, Rocket, SolidMotor

from hefesto.adapters.aerodynamics import DragModelProtocol
from hefesto.adapters.rocketpy.motor_builder import build_solid_motor
from hefesto.domain import (
    DragCurveSpec,
    FinComponent,
    FinGeometryMode,
    FinSetSpec,
    GeometryValidationError,
    MassMode,
    PointMassComponent,
    RocketSpec,
    TubeComponent,
)

_ROCKET_COORDINATE_SYSTEM: Final[str] = "nose_to_tail"


def _require_positive_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and > 0, got {value!r}")
    return float(value)


def _polygon_area_m2(points_m: Sequence[tuple[float, float]]) -> float:
    if len(points_m) < 3:
        raise GeometryValidationError(f"Fin polygon requires >= 3 vertices, got {len(points_m)}")
    twice_area = 0.0
    count = len(points_m)
    for idx in range(count):
        x1, y1 = points_m[idx]
        x2, y2 = points_m[(idx + 1) % count]
        twice_area += x1 * y2 - x2 * y1
    area = abs(twice_area) / 2.0
    if math.isclose(area, 0.0, abs_tol=1e-15):
        raise GeometryValidationError("Fin polygon has zero area")
    return area


def compute_rocket_dry_mass_kg(
    rocket: RocketSpec,
    mass_mode: MassMode | None = None,
) -> float:
    """Compute RocketSpec dry mass without motor according to MassMode."""
    if mass_mode == "measured":
        if rocket.dry_mass_override_kg is None:
            raise ValueError(
                "mass_mode='measured' requires rocket.dry_mass_override_kg to be set"
            )
        return _require_positive_finite(rocket.dry_mass_override_kg, "dry_mass_override_kg")
    if mass_mode is None and rocket.dry_mass_override_kg is not None:
        return _require_positive_finite(rocket.dry_mass_override_kg, "dry_mass_override_kg")
    if mass_mode not in (None, "calculated"):
        raise ValueError(f"Unsupported mass_mode: {mass_mode!r}")

    total_mass_kg = 0.0
    for component in rocket.components:
        if isinstance(component, TubeComponent):
            if component.mass_override_kg is not None:
                total_mass_kg += component.mass_override_kg
                continue
            volume_m3 = (
                math.pi
                * (component.outer_radius_m**2 - component.inner_radius_m**2)
                * component.length_m
            )
            total_mass_kg += volume_m3 * component.density_kg_m3
        elif isinstance(component, PointMassComponent):
            total_mass_kg += component.mass_kg
        elif isinstance(component, FinComponent):
            area_m2 = _polygon_area_m2(component.shape_points_m)
            total_mass_kg += (
                component.count * area_m2 * component.thickness_m * component.density_kg_m3
            )
        else:
            raise TypeError(f"Unsupported RocketComponent: {type(component)!r}")

    # Mirrors physics.structure.derive_rocket_structure: adapters cannot import physics.
    shell = rocket.nose_cone.shell
    if shell is not None:
        total_mass_kg += shell.mass_kg

    return _require_positive_finite(total_mass_kg, "dry_mass_kg")


def _to_linear_drag_function(
    points: Sequence[tuple[float, float]],
    *,
    factor: float,
    label: str,
) -> Function:
    scaled: list[tuple[float, float]] = []
    prev_mach: float | None = None
    for idx, (mach, cd) in enumerate(points):
        m_val = float(mach)
        cd_val = float(cd) * factor
        if not (math.isfinite(m_val) and math.isfinite(cd_val)) or m_val < 0.0 or cd_val < 0.0:
            raise ValueError(f"{label} point [{idx}] must be finite and >= 0: {(m_val, cd_val)!r}")
        if prev_mach is not None and m_val <= prev_mach:
            raise ValueError(f"{label} Mach must strictly increase at [{idx}]")
        prev_mach = m_val
        scaled.append((m_val, cd_val))
    if len(scaled) < 2:
        raise ValueError(f"{label} requires at least 2 points, got {len(scaled)}")
    # RocketPy treats raw lists as spline by default; linear+constant matches CSV drag parity.
    return Function(scaled, interpolation="linear", extrapolation="constant")


def _in_memory_curves(
    rocket: RocketSpec,
    source: str,
) -> tuple[DragCurveSpec, DragCurveSpec]:
    """Return the materialized curves of a computed source, rejecting stale CSV assets."""
    curves = (rocket.power_off_drag, rocket.power_on_drag)
    assets = [curve.asset_name for curve in curves if curve.asset_name is not None]
    if assets:
        raise ValueError(
            f"drag_source={source!r} requires in-memory curves, got CSV assets {assets!r}"
        )
    return curves


def _resolve_drag_curve_specs(rocket: RocketSpec) -> tuple[DragCurveSpec, DragCurveSpec]:
    """Dispatch RocketSpec.drag_source into its (power_off, power_on) curve pair."""
    match rocket.drag_source:
        case "legacy_csv":
            return rocket.power_off_drag, rocket.power_on_drag
        case "analytical":
            return _in_memory_curves(rocket, "analytical")
        case "ork_sim":
            return _in_memory_curves(rocket, "ork_sim")
        case "rasaero_csv":
            return _in_memory_curves(rocket, "rasaero_csv")
        case _:
            raise ValueError(f"Unsupported drag_source: {rocket.drag_source!r}")


def _resolve_drag_functions(
    rocket: RocketSpec,
    *,
    drag_model: DragModelProtocol | None,
    drag_factor: float,
) -> tuple[Function, Function]:
    factor = _require_positive_finite(drag_factor, "drag_factor")
    if drag_model is None:
        power_off_drag, power_on_drag = _resolve_drag_curve_specs(rocket)
        return (
            _to_linear_drag_function(power_off_drag.points, factor=factor, label="power_off_drag"),
            _to_linear_drag_function(power_on_drag.points, factor=factor, label="power_on_drag"),
        )
    return (
        _to_linear_drag_function(
            drag_model.power_off_curve(), factor=factor, label="power_off_drag"
        ),
        _to_linear_drag_function(
            drag_model.power_on_curve(), factor=factor, label="power_on_drag"
        ),
    )


def _derive_trapezoidal_params(fins: FinSetSpec) -> tuple[float, float, float, float]:
    """Return (root_chord, tip_chord, span, sweep_length) preserving fin planform area."""
    if (
        fins.root_chord_m is not None
        and fins.tip_chord_m is not None
        and fins.span_m is not None
    ):
        return (
            fins.root_chord_m,
            fins.tip_chord_m,
            fins.span_m,
            0.0 if fins.sweep_length_m is None else float(fins.sweep_length_m),
        )

    pts = fins.shape_points_m
    area_m2 = _polygon_area_m2(pts)
    if len(pts) == 4:
        p0, p1, p2, p3 = pts
        root_chord = abs(p3[0] - p0[0])
        tip_chord = abs(p2[0] - p1[0])
        sweep_length = p1[0] - p0[0]
        if root_chord > 0.0 and (root_chord + tip_chord) > 0.0:
            span = (2.0 * area_m2) / (root_chord + tip_chord)
            return root_chord, tip_chord, span, sweep_length

    xs = [pt[0] for pt in pts]
    ys = [pt[1] for pt in pts]
    root_chord = _require_positive_finite(max(xs) - min(xs), "fin root_chord_m")
    span = _require_positive_finite(max(ys) - min(ys), "fin span_m")
    tip_chord = max(0.0, (2.0 * area_m2) / span - root_chord)
    return root_chord, tip_chord, span, 0.0


def _attach_fins(
    rkt: Rocket,
    *,
    fins: FinSetSpec,
    fin_geometry_mode: FinGeometryMode,
) -> None:
    if fin_geometry_mode == "freeform":
        rkt.add_free_form_fins(
            n=fins.count,
            shape_points=list(fins.shape_points_m),
            position=fins.position_m,
            cant_angle=fins.cant_angle_deg,
            radius=fins.radius_m,
            name=fins.name,
        )
        return
    if fin_geometry_mode == "trapezoidal":
        root_chord, tip_chord, span, sweep_length = _derive_trapezoidal_params(fins)
        rkt.add_trapezoidal_fins(
            n=fins.count,
            root_chord=root_chord,
            tip_chord=tip_chord,
            span=span,
            position=fins.position_m,
            cant_angle=fins.cant_angle_deg,
            sweep_length=sweep_length,
            radius=fins.radius_m,
            name=fins.name,
        )
        return
    raise ValueError(f"Unsupported fin_geometry_mode: {fin_geometry_mode!r}")


def build_rocket(
    rocket: RocketSpec,
    *,
    motor: SolidMotor | None = None,
    drag_model: DragModelProtocol | None = None,
    drag_factor: float = 1.0,
    thrust_factor: float = 1.0,
    dry_mass_kg: float | None = None,
    mass_mode: MassMode | None = None,
    fin_geometry_mode: FinGeometryMode = "freeform",
) -> Rocket:
    """Assemble a RocketPy Rocket in nose_to_tail orientation using in-memory curves."""
    if rocket.coordinate_system != _ROCKET_COORDINATE_SYSTEM:
        raise GeometryValidationError(
            f"Rocket coordinate_system must be {_ROCKET_COORDINATE_SYSTEM!r}, "
            f"got {rocket.coordinate_system!r}"
        )

    resolved_mass_kg = (
        compute_rocket_dry_mass_kg(rocket, mass_mode=mass_mode)
        if dry_mass_kg is None
        else _require_positive_finite(dry_mass_kg, "dry_mass_kg")
    )
    resolved_inertia_kg_m2 = rocket.inertia_kg_m2
    if mass_mode == "measured" and dry_mass_kg is None:
        # Keep the inertia tensor consistent with the measured dry mass.
        calculated_mass_kg = compute_rocket_dry_mass_kg(rocket, mass_mode="calculated")
        inertia_scale = resolved_mass_kg / calculated_mass_kg
        if inertia_scale != 1.0:
            resolved_inertia_kg_m2 = tuple(
                moment * inertia_scale for moment in rocket.inertia_kg_m2
            )
    resolved_motor = (
        build_solid_motor(rocket.motor, thrust_factor=thrust_factor) if motor is None else motor
    )
    power_off_fn, power_on_fn = _resolve_drag_functions(
        rocket,
        drag_model=drag_model,
        drag_factor=drag_factor,
    )

    rkt = Rocket(
        radius=rocket.radius_m,
        mass=resolved_mass_kg,
        inertia=resolved_inertia_kg_m2,
        center_of_mass_without_motor=rocket.center_of_mass_without_motor_m,
        coordinate_system_orientation=_ROCKET_COORDINATE_SYSTEM,
        power_off_drag=power_off_fn,
        power_on_drag=power_on_fn,
    )

    nose = rocket.nose_cone
    rkt.add_nose(
        length=nose.length_m,
        kind=nose.kind.value,
        position=nose.position_m,
        bluffness=nose.bluffness,
        power=nose.power,
        name=nose.name,
        base_radius=nose.base_radius_m,
    )

    _attach_fins(rkt, fins=rocket.fins, fin_geometry_mode=fin_geometry_mode)

    rail_buttons = rocket.rail_buttons
    rkt.set_rail_buttons(
        upper_button_position=rail_buttons.upper_button_position_m,
        lower_button_position=rail_buttons.lower_button_position_m,
        angular_position=rail_buttons.angular_position_deg,
        radius=rail_buttons.radius_m,
    )

    for parachute in rocket.parachutes:
        rkt.add_parachute(
            name=parachute.name,
            cd_s=parachute.cd_s_m2,
            trigger=parachute.trigger,
            sampling_rate=parachute.sampling_rate_hz,
            lag=parachute.lag_s,
            noise=parachute.noise_std,
            radius=parachute.radius_m,
        )

    rkt.add_motor(resolved_motor, position=rocket.motor_position_m)
    return rkt


__all__ = [
    "build_rocket",
    "compute_rocket_dry_mass_kg",
]
