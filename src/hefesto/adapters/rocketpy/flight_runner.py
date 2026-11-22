"""RocketPy 6-DOF Flight execution and pure FlightResult extraction without Flight/MPL leaks."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rocketpy import Environment, Flight, Rocket

from hefesto.adapters.aerodynamics import DragModelProtocol
from hefesto.adapters.rocketpy.environment_builder import build_environment
from hefesto.adapters.rocketpy.rocket_builder import build_rocket
from hefesto.domain import FlightResult, LaunchConfig, MissionSpec


@dataclass(frozen=True)
class OutputSelection:
    """Boolean selector controlling which trajectory curves are extracted into FlightResult."""

    altitude_agl: bool = False
    vertical_velocity: bool = False
    mach: bool = False
    static_margin: bool = False

    @classmethod
    def all(cls) -> OutputSelection:
        """Enable extraction of all trajectory curves."""
        return cls(
            altitude_agl=True,
            vertical_velocity=True,
            mach=True,
            static_margin=True,
        )

    @classmethod
    def none(cls) -> OutputSelection:
        """Disable all optional trajectory curves (scalar metrics only)."""
        return cls()


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
        altitude_series = (
            _extract_series(flight.altitude, label="altitude_agl_series")
            if resolved.altitude_agl
            else ()
        )
        vz_series = (
            _extract_series(flight.vz, label="vertical_velocity_series")
            if resolved.vertical_velocity
            else ()
        )
        mach_series = (
            _extract_series(flight.mach_number, label="mach_series")
            if resolved.mach
            else ()
        )
        static_margin_series = (
            _extract_series(flight.stability_margin, label="static_margin_series")
            if resolved.static_margin
            else ()
        )

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
        altitude_agl_series=altitude_series,
        vertical_velocity_series=vz_series,
        mach_series=mach_series,
        static_margin_series=static_margin_series,
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
) -> FlightResult:
    """Build Environment, SolidMotor, and Rocket from MissionSpec and execute 6-DOF flight."""
    environment = build_environment(mission.environment, atmosphere_path)
    rocket = build_rocket(
        mission.rocket,
        drag_model=drag_model,
        drag_factor=drag_factor,
        thrust_factor=thrust_factor,
        dry_mass_kg=dry_mass_kg,
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
