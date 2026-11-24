"""RocketPy 6-DOF Flight execution and pure FlightResult extraction without Flight/MPL leaks."""

from __future__ import annotations

import base64
import math
import tempfile
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
    ParachuteDeployTelemetry,
)

_STANDARD_GRAVITY_M_S2 = 9.80665


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


def _safe_call_float(obj: Any, attr_name: str, arg: float) -> float | None:
    fn = getattr(obj, attr_name, None)
    if not callable(fn):
        return None
    try:
        return _optional_finite_float(fn(arg))
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        return None


def _extract_parachute_events(
    flight: Flight,
    elevation_m: float,
) -> tuple[ParachuteDeployTelemetry, ...]:
    raw_events = getattr(flight, "parachute_events", None)
    if not raw_events:
        return ()
    t_final = _optional_finite_float(getattr(flight, "t_final", None))
    extracted: list[ParachuteDeployTelemetry] = []
    for item in raw_events:
        try:
            trigger_time_s = float(item[0])
            parachute = item[1]
            lag_s = float(getattr(parachute, "lag", 0.0) or 0.0)
            deploy_t = trigger_time_s + max(0.0, lag_s)
            if t_final is not None:
                deploy_t = min(deploy_t, t_final)
            alt_agl = _safe_call_float(flight, "altitude", deploy_t)
            speed_ms = _safe_call_float(flight, "speed", deploy_t)
            cd_s = _optional_finite_float(getattr(parachute, "cd_s", None))
            if alt_agl is None or speed_ms is None or cd_s is None or cd_s <= 0.0:
                continue
            density = _safe_call_float(flight.env, "density", alt_agl + elevation_m)
            if density is None or density <= 0.0:
                continue
            name = str(getattr(parachute, "name", "Parachute") or "Parachute")
            extracted.append(
                ParachuteDeployTelemetry(
                    name=name,
                    cd_s=cd_s,
                    deploy_altitude_agl_m=alt_agl,
                    deploy_speed_ms=abs(speed_ms),
                    deploy_air_density_kg_m3=density,
                )
            )
        except (IndexError, KeyError, TypeError, ValueError):
            continue
    return tuple(extracted)


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
    apogee_time_s = float(flight.apogee_time)
    flight_time_s = float(flight.t_final)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        max_dynamic_pressure_pa = _optional_finite_float(
            getattr(flight, "max_dynamic_pressure", None)
        )
        max_accel_ms2 = _optional_finite_float(getattr(flight, "max_acceleration", None))
        max_axial_acceleration_g = (
            abs(max_accel_ms2) / _STANDARD_GRAVITY_M_S2 if max_accel_ms2 is not None else None
        )
        apogee_horizontal_speed_ms = _safe_call_float(flight, "horizontal_speed", apogee_time_s)
        if apogee_horizontal_speed_ms is None:
            apogee_horizontal_speed_ms = _optional_finite_float(
                getattr(flight, "apogee_freestream_speed", None)
            )
        if apogee_horizontal_speed_ms is not None:
            apogee_horizontal_speed_ms = abs(apogee_horizontal_speed_ms)

        burn_out_time_s = _optional_finite_float(
            getattr(getattr(flight.rocket, "motor", None), "burn_out_time", None)
        )
        burnout_tilt_deg: float | None = None
        if burn_out_time_s is not None:
            elev_deg = _safe_call_float(
                flight, "attitude_angle", min(burn_out_time_s, flight_time_s)
            )
            if elev_deg is not None:
                burnout_tilt_deg = abs(90.0 - elev_deg)

        out_of_rail_static_margin_calibers = _optional_finite_float(
            getattr(flight, "out_of_rail_stability_margin", None)
        )

        max_speed_time_s = _optional_finite_float(getattr(flight, "max_speed_time", None))
        max_speed_altitude_asl_m: float | None = None
        max_speed_ambient_pressure_pa: float | None = None
        max_speed_sound_speed_ms: float | None = None
        if max_speed_time_s is not None:
            alt_agl_vmax = _safe_call_float(flight, "altitude", max_speed_time_s)
            if alt_agl_vmax is not None:
                max_speed_altitude_asl_m = alt_agl_vmax + elevation_m
                max_speed_ambient_pressure_pa = _safe_call_float(
                    flight.env, "pressure", max_speed_altitude_asl_m
                )
                max_speed_sound_speed_ms = _safe_call_float(
                    flight.env, "speed_of_sound", max_speed_altitude_asl_m
                )

        rail_time_s = _optional_finite_float(getattr(flight, "out_of_rail_time", None))
        rail_alt_msl = elevation_m
        if rail_time_s is not None:
            rail_alt_agl = _safe_call_float(flight, "altitude", rail_time_s)
            if rail_alt_agl is not None:
                rail_alt_msl = rail_alt_agl + elevation_m
        wx_rail = _safe_call_float(flight.env, "wind_velocity_x", rail_alt_msl)
        wy_rail = _safe_call_float(flight.env, "wind_velocity_y", rail_alt_msl)
        rail_exit_wind_speed_ms = (
            math.hypot(wx_rail, wy_rail) if wx_rail is not None and wy_rail is not None else None
        )

        parachute_deploy_events = _extract_parachute_events(flight, elevation_m)

        total_impact_speed_ms: float | None = None
        if has_impact:
            vx_imp = _safe_call_float(flight, "vx", flight_time_s)
            vy_imp = _safe_call_float(flight, "vy", flight_time_s)
            vz_imp = _safe_call_float(flight, "vz", flight_time_s)
            if vx_imp is not None and vy_imp is not None and vz_imp is not None:
                total_impact_speed_ms = math.hypot(vx_imp, vy_imp, vz_imp)
            else:
                total_impact_speed_ms = landing_velocity_ms

    return FlightResult(
        apogee_agl_m=apogee_msl_m - elevation_m,
        apogee_msl_m=apogee_msl_m,
        apogee_time_s=apogee_time_s,
        flight_time_s=flight_time_s,
        max_speed_ms=float(flight.max_speed),
        max_mach=float(flight.max_mach_number),
        rail_exit_velocity_ms=float(flight.out_of_rail_velocity),
        min_static_margin_calibers=min_static_margin,
        max_static_margin_calibers=max_static_margin,
        total_impulse_ns=float(flight.rocket.motor.total_impulse),
        dry_mass_kg=float(flight.rocket.mass),
        landing_velocity_ms=landing_velocity_ms,
        impact_distance_m=impact_distance_m,
        max_dynamic_pressure_pa=max_dynamic_pressure_pa,
        max_axial_acceleration_g=max_axial_acceleration_g,
        apogee_horizontal_speed_ms=apogee_horizontal_speed_ms,
        burnout_tilt_deg=burnout_tilt_deg,
        out_of_rail_static_margin_calibers=out_of_rail_static_margin_calibers,
        max_speed_altitude_asl_m=max_speed_altitude_asl_m,
        max_speed_ambient_pressure_pa=max_speed_ambient_pressure_pa,
        max_speed_sound_speed_ms=max_speed_sound_speed_ms,
        rail_exit_wind_speed_ms=rail_exit_wind_speed_ms,
        parachute_deploy_events=parachute_deploy_events,
        total_impact_speed_ms=total_impact_speed_ms,
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


def _render_rocket_draw_png_b64(rocket: Rocket) -> str | None:
    """Render RocketPy's rocket.draw() diagram to a base64 PNG without leaking MPL state."""
    draw_fn = getattr(rocket, "draw", None)
    if not callable(draw_fn):
        return None
    import matplotlib
    import matplotlib.pyplot as plt

    previous_backend = matplotlib.get_backend()
    figures_before = set(plt.get_fignums())
    switched_backend = previous_backend.lower() != "agg"
    try:
        if switched_backend:
            plt.switch_backend("Agg")
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "rocket_draw.png"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                draw_fn(filename=str(out_path))
            if not out_path.exists():
                return None
            return base64.b64encode(out_path.read_bytes()).decode("ascii")
    finally:
        # RocketPy saves via plt.savefig + plt.close(); only reap figures this call created.
        for figure_number in set(plt.get_fignums()) - figures_before:
            plt.close(figure_number)
        if switched_backend:
            try:
                plt.switch_backend(previous_backend)
            except Exception as exc:
                warnings.warn(
                    f"Falha ao restaurar o backend matplotlib {previous_backend!r}: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
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
    result = extract_flight_result(flight, selection=output_selection)
    try:
        draw_b64 = _render_rocket_draw_png_b64(rocket)
    except Exception as exc:
        warnings.warn(
            f"Falha ao gerar o diagrama do foguete (FlightResult preservado): {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
        draw_b64 = None
    if draw_b64 is not None:
        return result.model_copy(update={"rocket_draw_png_b64": draw_b64})
    return result


def run_flight(
    mission: MissionSpec,
    atmosphere_path: Path | str | None = None,
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
    environment = build_environment(
        mission.environment, atmosphere_path, isa=mission.atmosphere
    )
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
