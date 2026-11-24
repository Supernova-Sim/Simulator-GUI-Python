"""Service-layer tests for evaluate_simulation_flight_safety and legacy snapshots."""

from __future__ import annotations

from datetime import UTC, datetime

from hefesto.domain import (
    FlightResult,
    FlightSafetyStatus,
    SimulationResult,
)
from hefesto.services import (
    compose_simulation_config,
    evaluate_simulation_flight_safety,
)


def test_evaluate_simulation_flight_safety_handles_legacy_snapshot_without_new_fields() -> None:
    legacy_payload = {
        "run_id": "legacy-run-001",
        "created_at_utc": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        "mission_name": "legacy_mission",
        "motor_name": "Medusa",
        "flight": {
            "apogee_agl_m": 2500.0,
            "apogee_msl_m": 3900.0,
            "apogee_time_s": 22.0,
            "flight_time_s": 22.0,
            "max_speed_ms": 240.0,
            "max_mach": 0.72,
            "rail_exit_velocity_ms": 22.0,
            "min_static_margin_calibers": 2.0,
            "total_impulse_ns": 10_000.0,
            "dry_mass_kg": 18.85,
        },
    }
    sim_result = SimulationResult.model_validate(legacy_payload)
    report = evaluate_simulation_flight_safety(sim_result)
    by_key = {c.key: c for c in report.checks}

    assert by_key["fin_flutter"].status == FlightSafetyStatus.NOT_EVALUATED
    assert by_key["rail_exit_velocity"].status == FlightSafetyStatus.PASS
    assert by_key["static_margin"].status == FlightSafetyStatus.PASS
    assert by_key["parachute_opening_shock"].status == FlightSafetyStatus.NOT_EVALUATED


def test_evaluate_simulation_flight_safety_uses_executed_config_when_present() -> None:
    config = compose_simulation_config()
    fins_with_g = config.mission.rocket.fins.model_copy(
        update={
            "thickness_m": 0.004,
            "shear_modulus_pa": 4.1e9,
            "material_name": "Fibra de Vidro G10",
            "root_chord_m": 0.18,
            "tip_chord_m": 0.14,
            "span_m": 0.14,
        }
    )
    updated_rocket = config.mission.rocket.model_copy(update={"fins": fins_with_g})
    updated_mission = config.mission.model_copy(update={"rocket": updated_rocket})
    updated_config = config.model_copy(update={"mission": updated_mission})

    flight = FlightResult(
        apogee_agl_m=2800.0,
        apogee_msl_m=4200.0,
        apogee_time_s=24.0,
        flight_time_s=24.0,
        max_speed_ms=220.0,
        max_mach=0.65,
        rail_exit_velocity_ms=25.0,
        min_static_margin_calibers=1.9,
        out_of_rail_static_margin_calibers=2.2,
        total_impulse_ns=12_000.0,
        dry_mass_kg=18.85,
        max_dynamic_pressure_pa=25_000.0,
        max_axial_acceleration_g=12.0,
        apogee_horizontal_speed_ms=10.0,
        burnout_tilt_deg=6.0,
        max_speed_ambient_pressure_pa=80_000.0,
        max_speed_sound_speed_ms=330.0,
        rail_exit_wind_speed_ms=3.0,
    )
    sim_result = SimulationResult(
        run_id="run-with-config",
        created_at_utc=datetime(2026, 11, 23, tzinfo=UTC),
        mission_name=updated_mission.name,
        motor_name=updated_rocket.motor.name,
        flight=flight,
        executed_config=updated_config,
    )

    report = evaluate_simulation_flight_safety(sim_result)
    assert report.fin_flutter_velocity_ms is not None
    assert report.fin_flutter_safety_factor is not None
    assert report.twr is not None
    assert report.max_q_kpa == 25.0
