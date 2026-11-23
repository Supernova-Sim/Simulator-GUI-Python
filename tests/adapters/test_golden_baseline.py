"""Golden baseline parity tests against tests/golden/hefesto_baseline.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import hefesto.adapters as adapters_pkg
from hefesto.adapters import (
    OutputSelection,
    build_rocket,
    build_solid_motor,
    compute_rocket_dry_mass_kg,
    run_flight,
    run_openmotor_ric,
)
from hefesto.domain import (
    AssetCategory,
    LaunchConfig,
    MissionSpec,
    MotorSpec,
    RocketSpec,
    SafetyCriterion,
    TubeComponent,
)
from hefesto.physics import derive_dry_mass, evaluate_motor_safety
from hefesto.storage import (
    AssetStore,
    CatalogStore,
    load_drag_curve,
    parse_eng_file,
    resolve_storage_paths,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = REPO_ROOT / "tests" / "golden" / "hefesto_baseline.json"

pytestmark = pytest.mark.slow


def _build_mission_from_catalog(
    *,
    wall_thickness_m: float | None = None,
    use_ric_ballistics: bool = False,
) -> tuple[MissionSpec, Path]:
    paths = resolve_storage_paths(REPO_ROOT)
    assets = AssetStore(paths)
    catalog = CatalogStore(paths, asset_store=assets)

    rocket_preset = catalog.load_rocket("hefesto_v1")
    motor_preset = catalog.load_motor(rocket_preset.motor_preset_name)
    env_spec = catalog.load_site("irec_oper")
    limits = catalog.load_limits("default")

    off_path = assets.resolve_asset(AssetCategory.DRAG, rocket_preset.power_off_drag_asset)
    on_path = assets.resolve_asset(AssetCategory.DRAG, rocket_preset.power_on_drag_asset)
    nc_path = assets.resolve_asset(AssetCategory.ATMOSPHERE, env_spec.atmosphere_asset)

    if use_ric_ballistics:
        assert motor_preset.motor_asset is not None
        ric_path = assets.resolve_asset(AssetCategory.MOTORS, motor_preset.motor_asset)
        ballistics = run_openmotor_ric(ric_path, motor_name=motor_preset.name)
        assert motor_preset.nozzle is not None
        motor_spec = MotorSpec(
            name=motor_preset.name,
            grains=ballistics.grains,
            grain_separation_m=motor_preset.grain_separation_m,
            grains_center_of_mass_m=motor_preset.grains_center_of_mass_m,
            propellant_name=motor_preset.propellant_name,
            propellant_density_kg_m3=ballistics.propellant_density_kg_m3,
            nozzle=motor_preset.nozzle,
            casing=motor_preset.casing,
            burn_time_s=ballistics.burn_time_s,
            thrust_curve=ballistics.thrust_curve,
            motor_asset=motor_preset.motor_asset,
            thrust_curve_asset=motor_preset.thrust_curve_asset,
        )
    else:
        assert motor_preset.thrust_curve_asset is not None
        assert motor_preset.nozzle is not None
        assert motor_preset.propellant_density_kg_m3 is not None
        assert motor_preset.burn_time_s is not None
        eng_path = assets.resolve_asset(AssetCategory.MOTORS, motor_preset.thrust_curve_asset)
        motor_spec = MotorSpec(
            name=motor_preset.name,
            grains=motor_preset.fallback_grains,
            grain_separation_m=motor_preset.grain_separation_m,
            grains_center_of_mass_m=motor_preset.grains_center_of_mass_m,
            propellant_name=motor_preset.propellant_name,
            propellant_density_kg_m3=motor_preset.propellant_density_kg_m3,
            nozzle=motor_preset.nozzle,
            casing=motor_preset.casing,
            burn_time_s=motor_preset.burn_time_s,
            thrust_curve=tuple(parse_eng_file(eng_path)),
            motor_asset=motor_preset.motor_asset,
            thrust_curve_asset=motor_preset.thrust_curve_asset,
        )

    components = rocket_preset.components
    if wall_thickness_m is not None:
        components = tuple(
            comp.model_copy(update={"wall_thickness_m": wall_thickness_m})
            if isinstance(comp, TubeComponent) and comp.wall_thickness_m == 0.002
            else comp
            for comp in components
        )

    rocket_spec = RocketSpec(
        name=rocket_preset.name,
        radius_m=rocket_preset.radius_m,
        center_of_mass_without_motor_m=rocket_preset.center_of_mass_without_motor_m,
        inertia_kg_m2=rocket_preset.inertia_kg_m2,
        motor_position_m=rocket_preset.motor_position_m,
        components=components,
        dry_mass_override_kg=rocket_preset.dry_mass_override_kg,
        nose_cone=rocket_preset.nose_cone,
        fins=rocket_preset.fins,
        rail_buttons=rocket_preset.rail_buttons,
        parachutes=rocket_preset.parachutes,
        power_off_drag=load_drag_curve(off_path, asset_name=rocket_preset.power_off_drag_asset),
        power_on_drag=load_drag_curve(on_path, asset_name=rocket_preset.power_on_drag_asset),
        motor=motor_spec,
    )
    mission = MissionSpec(
        name="golden_irec_88deg",
        rocket=rocket_spec,
        environment=env_spec,
        launch=LaunchConfig(inclination_deg=88.0, heading_deg=90.0, rail_length_m=6.0),
        safety_limits=limits,
    )
    return mission, nc_path


def test_golden_dry_mass_parity_for_2mm_and_3mm_walls() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["dry_mass"]

    mission_2mm, _ = _build_mission_from_catalog(wall_thickness_m=None)
    mission_3mm, _ = _build_mission_from_catalog(wall_thickness_m=0.003)

    assert compute_rocket_dry_mass_kg(mission_2mm.rocket) == pytest.approx(
        golden["wall_2mm_kg"], rel=1e-12
    )
    assert derive_dry_mass(mission_2mm.rocket) == pytest.approx(golden["wall_2mm_kg"], rel=1e-12)
    assert compute_rocket_dry_mass_kg(mission_2mm.rocket) == pytest.approx(
        golden["wall_2mm_reference_kg"], abs=5e-4
    )

    assert compute_rocket_dry_mass_kg(mission_3mm.rocket) == pytest.approx(
        golden["wall_3mm_kg"], rel=1e-12
    )
    assert derive_dry_mass(mission_3mm.rocket) == pytest.approx(golden["wall_3mm_kg"], rel=1e-12)
    assert compute_rocket_dry_mass_kg(mission_3mm.rocket) == pytest.approx(
        golden["wall_3mm_reference_kg"], abs=2e-3
    )


def test_golden_rocketpy_88deg_flight_parity_from_eng_and_ric() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["rocketpy_baseline_88deg"]
    expected_inputs = golden["inputs"]
    expected_metrics = golden["metrics"]

    mission_eng, nc_path = _build_mission_from_catalog(use_ric_ballistics=False)
    assert mission_eng.environment.atmosphere_asset == expected_inputs["atmosphere_asset"]
    assert mission_eng.rocket.motor.thrust_curve_asset == expected_inputs["thrust_curve_asset"]
    assert mission_eng.rocket.power_off_drag.asset_name == expected_inputs["power_off_drag_asset"]
    assert mission_eng.rocket.power_on_drag.asset_name == expected_inputs["power_on_drag_asset"]
    assert list(mission_eng.environment.date_utc) == expected_inputs["date_utc"]
    assert mission_eng.environment.latitude_deg == pytest.approx(expected_inputs["latitude_deg"])
    assert mission_eng.environment.longitude_deg == pytest.approx(expected_inputs["longitude_deg"])
    assert mission_eng.environment.elevation_m == pytest.approx(expected_inputs["elevation_m"])
    assert mission_eng.launch.inclination_deg == pytest.approx(expected_inputs["inclination_deg"])
    assert mission_eng.launch.heading_deg == pytest.approx(expected_inputs["heading_deg"])
    assert mission_eng.launch.rail_length_m == pytest.approx(expected_inputs["rail_length_m"])
    assert mission_eng.rocket.coordinate_system == expected_inputs["rocket_coordinate_system"]
    assert mission_eng.rocket.motor.coordinate_system == expected_inputs["motor_coordinate_system"]

    solid_motor = build_solid_motor(mission_eng.rocket.motor)
    assert solid_motor.dry_mass == pytest.approx(expected_inputs["motor_dry_mass_kg"], rel=1e-12)
    assert (solid_motor.dry_I_11, solid_motor.dry_I_22, solid_motor.dry_I_33) == pytest.approx(
        tuple(expected_inputs["motor_dry_inertia_kg_m2"]), rel=1e-12
    )
    assert solid_motor.center_of_dry_mass_position == pytest.approx(
        expected_inputs["motor_center_of_dry_mass_m"], rel=1e-12
    )
    assert solid_motor.grains_center_of_mass_position == pytest.approx(
        expected_inputs["grains_center_of_mass_m"], rel=1e-12
    )

    rocket = build_rocket(mission_eng.rocket, motor=solid_motor)
    assert rocket.mass == pytest.approx(expected_inputs["dry_mass_kg"], rel=1e-12)
    assert rocket.center_of_mass_without_motor == pytest.approx(
        expected_inputs["center_of_mass_without_motor_m"], rel=1e-12
    )
    assert (
        rocket.I_11_without_motor,
        rocket.I_22_without_motor,
        rocket.I_33_without_motor,
    ) == pytest.approx(tuple(expected_inputs["inertia_kg_m2"]), rel=1e-12)

    flight_eng = run_flight(mission_eng, nc_path, output_selection=OutputSelection.all())
    for metric_key, expected_value in expected_metrics.items():
        actual_value = getattr(flight_eng, metric_key)
        assert actual_value == pytest.approx(expected_value, rel=1e-6), (
            f"Mismatch on {metric_key}: {actual_value} != {expected_value}"
        )

    assert len(flight_eng.altitude_agl_series) > 100
    assert len(flight_eng.vertical_velocity_series) == len(flight_eng.altitude_agl_series)
    assert len(flight_eng.mach_series) == len(flight_eng.altitude_agl_series)
    assert len(flight_eng.static_margin_series) == len(flight_eng.altitude_agl_series)

    # Full .ric -> OpenMotor -> SolidMotor -> Rocket -> Flight parity.
    mission_ric, _ = _build_mission_from_catalog(use_ric_ballistics=True)
    flight_ric = run_flight(mission_ric, nc_path)
    assert flight_ric.apogee_agl_m == pytest.approx(expected_metrics["apogee_agl_m"], rel=1e-4)
    assert flight_ric.max_mach == pytest.approx(expected_metrics["max_mach"], rel=1e-4)
    assert flight_ric.min_static_margin_calibers == pytest.approx(
        expected_metrics["min_static_margin_calibers"], rel=1e-4
    )
    assert flight_ric.total_impulse_ns == pytest.approx(
        expected_metrics["total_impulse_ns"], rel=1e-6
    )


def test_golden_openmotor_and_safety_baselines_parity() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    paths = resolve_storage_paths(REPO_ROOT)
    assets = AssetStore(paths)
    catalog = CatalogStore(paths, asset_store=assets)

    for motor_id, expected in golden["openmotor_baselines"].items():
        ric_path = assets.resolve_asset(AssetCategory.MOTORS, expected["motor_asset"])
        eng_path = assets.resolve_asset(AssetCategory.MOTORS, expected["thrust_curve_asset"])

        ballistics = run_openmotor_ric(ric_path, motor_name=motor_id)
        assert len(ballistics.grains) == expected["grain_count"]
        assert ballistics.burn_time_s == pytest.approx(tuple(expected["burn_time_s"]), rel=1e-12)
        assert ballistics.total_impulse_ns == pytest.approx(expected["total_impulse_ns"], rel=1e-12)
        assert ballistics.max_thrust_n == pytest.approx(expected["max_thrust_n"], rel=1e-12)
        assert ballistics.propellant_mass_kg == pytest.approx(
            expected["propellant_mass_kg"], rel=1e-12
        )
        assert ballistics.peak_chamber_pressure_pa == pytest.approx(
            expected["peak_chamber_pressure_pa"], rel=1e-12
        )
        assert ballistics.peak_kn == pytest.approx(expected["peak_kn"], rel=1e-12)
        assert ballistics.peak_mass_flux_kg_m2_s == pytest.approx(
            expected["peak_mass_flux_kg_m2_s"], rel=1e-12
        )
        assert ballistics.delivered_isp_s == pytest.approx(expected["delivered_isp_s"], rel=1e-12)

        if "aft_port_to_throat_ratio" in expected:
            assert ballistics.aft_port_to_throat_ratio == pytest.approx(
                expected["aft_port_to_throat_ratio"], rel=1e-12
            )
            assert ballistics.min_port_to_throat_ratio == pytest.approx(
                expected["min_port_to_throat_ratio"], rel=1e-12
            )

        eng_points = parse_eng_file(eng_path)
        eng_impulse = sum(
            0.5 * (f0 + f1) * (t1 - t0)
            for (t0, f0), (t1, f1) in zip(eng_points, eng_points[1:], strict=False)
        )
        assert eng_impulse == pytest.approx(expected["total_impulse_ns"], rel=1e-5)

    # Safety baseline check on Medusa KNSB A.
    safety_gold = golden["safety_baseline_medusa_knsb_a"]
    medusa_preset = catalog.load_motor("medusa_knsb_a")
    default_limits = catalog.load_limits("default")
    medusa_ric = assets.resolve_asset(AssetCategory.MOTORS, "medusa_knsb_a.ric")
    medusa_ballistics = run_openmotor_ric(medusa_ric, motor_name="medusa_knsb_a")

    report = evaluate_motor_safety(medusa_ballistics, medusa_preset.casing, limits=default_limits)
    assert report.all_passed is True
    assert report.hoop_stress_pa == pytest.approx(safety_gold["hoop_stress_pa"], rel=1e-12)

    by_crit = {check.criterion: check for check in report.checks}
    assert by_crit[SafetyCriterion.CASE_SAFETY_FACTOR].value == pytest.approx(
        safety_gold["checks"]["case_safety_factor"]["value"], rel=1e-12
    )
    assert by_crit[SafetyCriterion.PEAK_CHAMBER_PRESSURE].value == pytest.approx(
        safety_gold["checks"]["peak_chamber_pressure_mpa"]["value"] * 1e6, rel=1e-12
    )
    assert by_crit[SafetyCriterion.PEAK_KN].value == pytest.approx(
        safety_gold["checks"]["peak_kn"]["value"], rel=1e-12
    )
    assert by_crit[SafetyCriterion.PEAK_MASS_FLUX].value == pytest.approx(
        safety_gold["checks"]["peak_mass_flux_kg_m2_s"]["value"], rel=1e-12
    )
    assert by_crit[SafetyCriterion.PORT_TO_THROAT_RATIO].value == pytest.approx(
        safety_gold["checks"]["aft_port_to_throat_ratio"]["value"], rel=1e-12
    )
    assert all(check.passed for check in report.checks)

    for symbol in adapters_pkg.__all__:
        assert hasattr(adapters_pkg, symbol)
