"""Unit tests for the pure Flight Safety Envelope physics module."""

from __future__ import annotations

import math

import pytest

from hefesto.domain import (
    FIN_MATERIAL_SHEAR_MODULUS_PA,
    DragCurveSpec,
    FinSetSpec,
    FlightResult,
    FlightSafetyStatus,
    GrainSpec,
    MotorCasingSpec,
    MotorSpec,
    NoseConeSpec,
    NozzleSpec,
    ParachuteDeployTelemetry,
    RailButtonsSpec,
    RocketSpec,
    TubeComponent,
)
from hefesto.physics import (
    STANDARD_GRAVITY_M_S2,
    compute_fin_flutter_velocity_ms,
    evaluate_flight_safety,
)


def _sample_motor() -> MotorSpec:
    grain = GrainSpec(length_m=0.20, outer_radius_m=0.04, inner_radius_m=0.015)
    return MotorSpec(
        name="TestMotor",
        grains=(grain, grain),
        grain_separation_m=0.005,
        grains_center_of_mass_m=0.25,
        propellant_name="KNSB",
        propellant_density_kg_m3=1840.0,
        nozzle=NozzleSpec(throat_radius_m=0.010, exit_radius_m=0.020),
        casing=MotorCasingSpec(
            inner_radius_m=0.042,
            wall_thickness_m=0.003,
            length_m=0.50,
            yield_strength_pa=145e6,
            dry_mass_kg=2.0,
            dry_inertia_kg_m2=(0.05, 0.05, 0.005),
            center_of_dry_mass_m=0.25,
        ),
        burn_time_s=(0.0, 2.0),
        thrust_curve=((0.0, 0.0), (0.1, 1000.0), (1.9, 1000.0), (2.0, 0.0)),
    )


def _sample_rocket(
    *, shear_modulus_pa: float | None = 4.1e9, thickness_m: float | None = 0.004
) -> RocketSpec:
    drag = DragCurveSpec(points=((0.0, 0.4), (2.0, 0.5)))
    return RocketSpec(
        name="TestRocket",
        radius_m=0.05,
        center_of_mass_without_motor_m=0.80,
        inertia_kg_m2=(1.5, 1.5, 0.02),
        motor_position_m=1.10,
        components=(
            TubeComponent(
                name="Airframe",
                length_m=1.20,
                outer_radius_m=0.05,
                wall_thickness_m=0.002,
                density_kg_m3=1800.0,
                position_m=0.30,
            ),
        ),
        nose_cone=NoseConeSpec(length_m=0.30),
        fins=FinSetSpec(
            count=4,
            position_m=1.20,
            shape_points_m=((0.0, 0.0), (0.05, 0.15), (0.15, 0.15), (0.20, 0.0)),
            root_chord_m=0.20,
            tip_chord_m=0.10,
            span_m=0.15,
            thickness_m=thickness_m,
            shear_modulus_pa=shear_modulus_pa,
            material_name="Fibra de Vidro G10" if shear_modulus_pa is not None else None,
        ),
        rail_buttons=RailButtonsSpec(upper_button_position_m=0.60, lower_button_position_m=1.30),
        power_off_drag=drag,
        power_on_drag=drag,
        motor=_sample_motor(),
    )


def _sample_flight(**overrides: object) -> FlightResult:
    defaults: dict[str, object] = {
        "apogee_agl_m": 1500.0,
        "apogee_msl_m": 2000.0,
        "apogee_time_s": 18.0,
        "flight_time_s": 90.0,
        "max_speed_ms": 180.0,
        "max_mach": 0.54,
        "rail_exit_velocity_ms": 24.0,
        "min_static_margin_calibers": 2.0,
        "out_of_rail_static_margin_calibers": 2.1,
        "total_impulse_ns": 1900.0,
        "dry_mass_kg": 10.0,
        "landing_velocity_ms": 6.0,
        "total_impact_speed_ms": 6.2,
        "max_dynamic_pressure_pa": 18_500.0,
        "max_axial_acceleration_g": 11.0,
        "apogee_horizontal_speed_ms": 12.0,
        "burnout_tilt_deg": 8.0,
        "max_speed_ambient_pressure_pa": 90_000.0,
        "max_speed_sound_speed_ms": 335.0,
        "rail_exit_wind_speed_ms": 3.5,
        "parachute_deploy_events": (
            ParachuteDeployTelemetry(
                name="Drogue",
                cd_s=0.4,
                deploy_altitude_agl_m=1490.0,
                deploy_speed_ms=14.0,
                deploy_air_density_kg_m3=1.0,
            ),
        ),
    }
    defaults.update(overrides)
    return FlightResult.model_validate(defaults)


def test_fin_flutter_matches_manual_naca_4197_si_reference() -> None:
    # c_r=0.20, c_t=0.10, s=0.15 => S_fin=0.0225, AR=1.0, lambda=0.5, t/c_r=0.02
    vf = compute_fin_flutter_velocity_ms(
        root_chord_m=0.20,
        tip_chord_m=0.10,
        span_m=0.15,
        thickness_m=0.004,
        shear_modulus_pa=4.1e9,
        ambient_pressure_pa=90_000.0,
        speed_of_sound_ms=335.0,
    )
    expected = 335.0 * math.sqrt((4.1e9 * 3.0 * (0.02**3)) / (1.3371 * 1.0 * 1.5 * 90_000.0))
    assert vf == pytest.approx(expected, rel=1e-12)
    # Confirm absence of an erroneous extra factor of 2 in denominator.
    assert vf != pytest.approx(expected / math.sqrt(2.0), rel=1e-3)


def test_fin_flutter_sensitivities_thickness_ar_shear_pressure() -> None:
    base = compute_fin_flutter_velocity_ms(
        root_chord_m=0.20,
        tip_chord_m=0.10,
        span_m=0.15,
        thickness_m=0.004,
        shear_modulus_pa=FIN_MATERIAL_SHEAR_MODULUS_PA["Fibra de Vidro G10"],
        ambient_pressure_pa=90_000.0,
        speed_of_sound_ms=335.0,
    )
    thicker = compute_fin_flutter_velocity_ms(
        root_chord_m=0.20,
        tip_chord_m=0.10,
        span_m=0.15,
        thickness_m=0.006,
        shear_modulus_pa=FIN_MATERIAL_SHEAR_MODULUS_PA["Fibra de Vidro G10"],
        ambient_pressure_pa=90_000.0,
        speed_of_sound_ms=335.0,
    )
    stiffer = compute_fin_flutter_velocity_ms(
        root_chord_m=0.20,
        tip_chord_m=0.10,
        span_m=0.15,
        thickness_m=0.004,
        shear_modulus_pa=FIN_MATERIAL_SHEAR_MODULUS_PA["Alumínio 6061-T6"],
        ambient_pressure_pa=90_000.0,
        speed_of_sound_ms=335.0,
    )
    higher_span = compute_fin_flutter_velocity_ms(
        root_chord_m=0.20,
        tip_chord_m=0.10,
        span_m=0.25,
        thickness_m=0.004,
        shear_modulus_pa=FIN_MATERIAL_SHEAR_MODULUS_PA["Fibra de Vidro G10"],
        ambient_pressure_pa=90_000.0,
        speed_of_sound_ms=335.0,
    )
    lower_pressure = compute_fin_flutter_velocity_ms(
        root_chord_m=0.20,
        tip_chord_m=0.10,
        span_m=0.15,
        thickness_m=0.004,
        shear_modulus_pa=FIN_MATERIAL_SHEAR_MODULUS_PA["Fibra de Vidro G10"],
        ambient_pressure_pa=45_000.0,
        speed_of_sound_ms=335.0,
    )
    assert thicker > base
    assert stiffer > base
    assert higher_span < base
    assert lower_pressure == pytest.approx(base * math.sqrt(2.0), rel=1e-12)


def test_fin_flutter_not_evaluated_when_shear_modulus_is_none() -> None:
    rocket = _sample_rocket(shear_modulus_pa=None)
    flight = _sample_flight()
    report = evaluate_flight_safety(flight, rocket=rocket)
    flutter = next(c for c in report.checks if c.key == "fin_flutter")
    assert flutter.status == FlightSafetyStatus.NOT_EVALUATED
    assert report.fin_flutter_velocity_ms is None
    assert "Configuração" in flutter.recommendation


def test_weathercocking_and_superstability_detection() -> None:
    rocket = _sample_rocket()
    flight = _sample_flight(
        out_of_rail_static_margin_calibers=4.2,
        apogee_horizontal_speed_ms=44.0,
        burnout_tilt_deg=29.0,
    )
    report = evaluate_flight_safety(flight, rocket=rocket)
    by_key = {c.key: c for c in report.checks}

    assert by_key["static_margin"].status == FlightSafetyStatus.WARN
    assert "superestabilidade" in by_key["static_margin"].recommendation.lower()
    assert by_key["apogee_horizontal_speed"].status == FlightSafetyStatus.FAIL
    assert by_key["burnout_tilt"].status == FlightSafetyStatus.WARN
    assert report.overall_status == FlightSafetyStatus.FAIL


def test_twr_rail_aoa_opening_shock_and_impact_checks() -> None:
    rocket = _sample_rocket()
    # Force low rail exit velocity + strong wind + heavy opening shock + fast impact.
    flight = _sample_flight(
        rail_exit_velocity_ms=14.0,
        rail_exit_wind_speed_ms=6.0,
        total_impulse_ns=600.0,  # avg thrust = 300 N over 2s -> TWR < 4.0
        total_impact_speed_ms=11.5,
        parachute_deploy_events=(
            ParachuteDeployTelemetry(
                name="Main",
                cd_s=2.0,
                deploy_altitude_agl_m=300.0,
                deploy_speed_ms=65.0,
                deploy_air_density_kg_m3=1.2,
            ),
        ),
    )
    report = evaluate_flight_safety(flight, rocket=rocket)
    by_key = {c.key: c for c in report.checks}

    assert by_key["twr"].status == FlightSafetyStatus.FAIL
    assert by_key["rail_exit_velocity"].status == FlightSafetyStatus.FAIL
    expected_aoa = math.degrees(math.atan2(6.0, 14.0))
    assert report.rail_aoa_deg == pytest.approx(expected_aoa, rel=1e-9)
    assert by_key["rail_aoa"].status == FlightSafetyStatus.FAIL

    expected_shock_n = 0.5 * 1.2 * (65.0**2) * 2.0 * 1.3
    expected_shock_g = expected_shock_n / (10.0 * STANDARD_GRAVITY_M_S2)
    assert report.max_parachute_shock_n == pytest.approx(expected_shock_n, rel=1e-9)
    assert report.max_parachute_shock_g == pytest.approx(expected_shock_g, rel=1e-9)
    assert by_key["parachute_opening_shock"].status == FlightSafetyStatus.FAIL
    assert by_key["impact_speed"].status == FlightSafetyStatus.FAIL
