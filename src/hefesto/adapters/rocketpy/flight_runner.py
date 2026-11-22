"""RocketPy 6-DOF Flight execution and pure FlightResult extraction without Flight/MPL leaks."""

from __future__ import annotations

import math
import warnings
from pathlib import Path
from typing import Any

from rocketpy import Environment, Flight, Rocket

from hefesto.adapters.aerodynamics import DragModelProtocol
from hefesto.adapters.rocketpy.environment_builder import build_environment
from hefesto.adapters.rocketpy.rocket_builder import build_rocket
from hefesto.domain import (
    FinGeometryMode,
    FlightResult,
    LaunchConfig,
    MassMode,
    MissionSpec,
    OutputSelection,
)


def _extract_series(source_obj: Any, *, label: str) -> tuple[tuple[float, float], ...]:
    get_source = getattr(source_obj, "get_source", None)
    raw_rows = get_source() if callable(get_source) else source_obj
    series: list[tuple[float, float]] = []
    for idx, row in enumerate(raw_rows):
        t_val = float(row[0])
        y_val = float(row[1])
        if not (math.isfinite(t_val) and math.isfinite(y_val)):
            raise ValueError(f"Non-finite point in {label} at [{idx}]: {(t_val, y_val)!r}")
        series.append((t_val, y_val))
    return tuple(series)


def _extract_if(
    enabled: bool,
    source_obj: Any,
    *,
    label: str,
) -> tuple[tuple[float, float], ...]:
    return _extract_series(source_obj, label=label) if enabled else ()


def _extract_cg_and_cp_series(
    flight: Flight,
    *,
    extract_cg: bool,
    extract_cp: bool,
) -> tuple[tuple[tuple[float, float], ...], tuple[tuple[float, float], ...]]:
    if not (extract_cg or extract_cp):
        return (), ()

    mach_rows = _extract_series(flight.mach_number, label="mach_number")
    cg_series: list[tuple[float, float]] = []
    cp_series: list[tuple[float, float]] = []
    for idx, (t_val, mach_val) in enumerate(mach_rows):
        if extract_cg:
            cg_val = float(flight.rocket.center_of_mass(t_val))
            if not math.isfinite(cg_val):
                raise ValueError(f"Non-finite point in cg_series at [{idx}]: {(t_val, cg_val)!r}")
            cg_series.append((t_val, cg_val))
        if extract_cp:
            cp_val = float(flight.rocket.cp_position(mach_val))
            if not math.isfinite(cp_val):
                raise ValueError(f"Non-finite point in cp_series at [{idx}]: {(t_val, cp_val)!r}")
            cp_series.append((t_val, cp_val))
    return tuple(cg_series), tuple(cp_series)


def _extract_drag_curve_input(
    rocket_obj: Any,
    attr_name: str,
    *,
    label: str,
) -> tuple[tuple[float, float], ...]:
    curve_obj = getattr(rocket_obj, attr_name, None)
    if curve_obj is None:
        return ()
    get_source = getattr(curve_obj, "get_source", None)
    if callable(get_source):
        raw_source = get_source()
        if callable(raw_source):
            return ()
        return _extract_series(raw_source, label=label)
    return _extract_series(curve_obj, label=label)


def _optional_finite_float(value: Any) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def extract_flight_result(
    flight: Flight,
    *,
    selection: OutputSelection | None = None,
) -> FlightResult:
    """Extract pure domain FlightResult metrics and selected series without leaking Flight/MPL."""
    resolved = OutputSelection.none() if selection is None else selection

    # RocketPy can emit RuntimeWarning in polation_1d when apogee termination repeats a timestamp.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        min_static_margin = float(flight.min_stability_margin)
        max_static_margin = _optional_finite_float(getattr(flight, "max_stability_margin", None))
        x_series = _extract_if(resolved.x, flight.x, label="x_series")
        y_series = _extract_if(resolved.y, flight.y, label="y_series")
        altitude_series = _extract_if(
            resolved.altitude_agl, flight.altitude, label="altitude_agl_series"
        )
        speed_series = _extract_if(resolved.speed, flight.speed, label="speed_series")
        vz_series = _extract_if(
            resolved.vertical_velocity, flight.vz, label="vertical_velocity_series"
        )
        acceleration_series = _extract_if(
            resolved.acceleration, flight.acceleration, label="acceleration_series"
        )
        mach_series = _extract_if(resolved.mach, flight.mach_number, label="mach_series")
        cg_series, cp_series = _extract_cg_and_cp_series(
            flight, extract_cg=resolved.cg, extract_cp=resolved.cp
        )
        static_margin_series = _extract_if(
            resolved.static_margin, flight.stability_margin, label="static_margin_series"
        )
        drag_series = _extract_if(resolved.drag, flight.aerodynamic_drag, label="drag_series")
        power_off_drag_curve = (
            _extract_drag_curve_input(
                flight.rocket, "_power_off_drag_input", label="power_off_drag_curve"
            )
            if resolved.drag
            else ()
        )
        power_on_drag_curve = (
            _extract_drag_curve_input(
                flight.rocket, "_power_on_drag_input", label="power_on_drag_curve"
            )
            if resolved.drag
            else ()
        )
        thrust_series = _extract_if(resolved.thrust, flight.net_thrust, label="thrust_series")

    impact_state = getattr(flight, "impact_state", None)
    has_impact = impact_state is not None and len(impact_state) > 1
    landing_velocity_ms = abs(float(flight.impact_velocity)) if has_impact else None
    impact_distance_m = (
        float(math.hypot(float(flight.x_impact), float(flight.y_impact))) if has_impact else None
    )

    apogee_msl_m = float(flight.apogee)
    elevation_m = float(flight.env.elevation)

    return FlightResult(
        apogee_agl_m=apogee_msl_m - elevation_m,
        apogee_msl_m=apogee_msl_m,
        apogee_time_s=float(flight.apogee_time),
        flight_time_s=float(flight.t_final),
        max_speed_ms=float(flight.max_speed),
        max_mach=float(flight.max_mach_number),
        rail_exit_velocity_ms=float(flight.out_of_rail_velocity),
        min_static_margin_calibers=min_static_margin,
        max_static_margin_calibers=max_static_margin,
        total_impulse_ns=float(flight.rocket.motor.total_impulse),
        dry_mass_kg=float(flight.rocket.mass),
        landing_velocity_ms=landing_velocity_ms,
        impact_distance_m=impact_distance_m,
        x_series=x_series,
        y_series=y_series,
        altitude_agl_series=altitude_series,
        speed_series=speed_series,
        vertical_velocity_series=vz_series,
        acceleration_series=acceleration_series,
        mach_series=mach_series,
        cg_series=cg_series,
        cp_series=cp_series,
        static_margin_series=static_margin_series,
        drag_series=drag_series,
        power_off_drag_curve=power_off_drag_curve,
        power_on_drag_curve=power_on_drag_curve,
        thrust_series=thrust_series,
    )


def execute_flight(
    rocket: Rocket,
    environment: Environment,
    launch: LaunchConfig,
    *,
    output_selection: OutputSelection | None = None,
) -> FlightResult:
    """Execute a 6-DOF RocketPy Flight and return pure FlightResult without leaking Flight."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        flight = Flight(
            rocket=rocket,
            environment=environment,
            rail_length=launch.rail_length_m,
            inclination=launch.inclination_deg,
            heading=launch.heading_deg,
            max_time=launch.max_time_s,
            terminate_on_apogee=launch.terminate_on_apogee,
            rtol=launch.rtol,
            ode_solver=launch.ode_solver,
            verbose=False,
        )
    return extract_flight_result(flight, selection=output_selection)


def run_flight(
    mission: MissionSpec,
    atmosphere_path: Path | str,
    *,
    output_selection: OutputSelection | None = None,
    drag_model: DragModelProtocol | None = None,
    drag_factor: float = 1.0,
    thrust_factor: float = 1.0,
    dry_mass_kg: float | None = None,
    mass_mode: MassMode | None = None,
    fin_geometry_mode: FinGeometryMode = "freeform",
) -> FlightResult:
    """Build Environment, SolidMotor, and Rocket from MissionSpec and execute 6-DOF flight."""
    environment = build_environment(mission.environment, atmosphere_path)
    rocket = build_rocket(
        mission.rocket,
        drag_model=drag_model,
        drag_factor=drag_factor,
        thrust_factor=thrust_factor,
        dry_mass_kg=dry_mass_kg,
        mass_mode=mass_mode,
        fin_geometry_mode=fin_geometry_mode,
    )
    return execute_flight(
        rocket,
        environment,
        mission.launch,
        output_selection=output_selection,
    )


__all__ = [
    "OutputSelection",
    "execute_flight",
    "extract_flight_result",
    "run_flight",
]
