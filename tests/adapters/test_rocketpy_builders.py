"""TDD tests for isolated RocketPy builders, .nc-only atmosphere, and FlightResult extraction."""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pytest

import hefesto.adapters as adapters_pkg
import hefesto.adapters.rocketpy as rocketpy_pkg
from hefesto.adapters.aerodynamics import DatabaseDragModel, DragModelProtocol
from hefesto.adapters.rocketpy import (
    OutputSelection,
    build_environment,
    build_netcdf_dictionary,
    build_rocket,
    build_solid_motor,
    compute_rocket_dry_mass_kg,
    execute_flight,
    extract_flight_result,
    run_flight,
)
from hefesto.domain import (
    AssetCategory,
    DragCurveSpec,
    Era5DatasetKind,
    FlightResult,
    GeometryValidationError,
    GrainInhibition,
    GrainSpec,
    InterpolationMethod,
    IsaAtmosphereSpec,
    LaunchConfig,
    MissionSpec,
    MotorCasingSpec,
    MotorSpec,
    NetCdfVariableMap,
    NoseConeSpec,
    NozzleSpec,
    PointMassComponent,
    RocketSpec,
)
from hefesto.storage import (
    AssetStore,
    CatalogStore,
    load_drag_curve,
    parse_eng_file,
    resolve_storage_paths,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = REPO_ROOT / "tests" / "golden" / "hefesto_baseline.json"


def _load_real_mission(
    *,
    site_id: str = "irec_oper",
    terminate_on_apogee: bool = False,
) -> tuple[MissionSpec, Path]:
    paths = resolve_storage_paths(REPO_ROOT)
    assets = AssetStore(paths)
    catalog = CatalogStore(paths, asset_store=assets)

    rocket_preset = catalog.load_rocket("hefesto_v1")
    motor_preset = catalog.load_motor(rocket_preset.motor_preset_name)
    env_spec = catalog.load_site(site_id)
    limits = catalog.load_limits("default")

    eng_path = assets.resolve_asset(AssetCategory.MOTORS, motor_preset.thrust_curve_asset or "")
    off_path = assets.resolve_asset(AssetCategory.DRAG, rocket_preset.power_off_drag_asset)
    on_path = assets.resolve_asset(AssetCategory.DRAG, rocket_preset.power_on_drag_asset)
    nc_path = assets.resolve_asset(AssetCategory.ATMOSPHERE, env_spec.atmosphere_asset)

    assert motor_preset.nozzle is not None
    assert motor_preset.propellant_density_kg_m3 is not None
    assert motor_preset.burn_time_s is not None

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
    rocket_spec = RocketSpec(
        name=rocket_preset.name,
        radius_m=rocket_preset.radius_m,
        center_of_mass_without_motor_m=rocket_preset.center_of_mass_without_motor_m,
        inertia_kg_m2=rocket_preset.inertia_kg_m2,
        motor_position_m=rocket_preset.motor_position_m,
        components=rocket_preset.components,
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
        name=f"hefesto_{site_id}",
        rocket=rocket_spec,
        environment=env_spec,
        launch=LaunchConfig(terminate_on_apogee=terminate_on_apogee),
        safety_limits=limits,
    )
    return mission, nc_path


def _sample_motor(
    *,
    casing_length_m: float = 1.10,
    internal_clearance_m: float = 0.04,
    casing_inner_radius_m: float = 0.05395,
    grain_outer_radius_m: float = 0.049345,
    inhibited_ends: GrainInhibition = GrainInhibition.NEITHER,
    interpolation_method: InterpolationMethod = InterpolationMethod.LINEAR,
) -> MotorSpec:
    grains = (
        *(
            GrainSpec(
                length_m=0.16,
                outer_radius_m=grain_outer_radius_m,
                inner_radius_m=0.0195,
                inhibited_ends=inhibited_ends,
            )
            for _ in range(4)
        ),
        *(
            GrainSpec(
                length_m=0.16,
                outer_radius_m=grain_outer_radius_m,
                inner_radius_m=0.027,
                inhibited_ends=inhibited_ends,
            )
            for _ in range(2)
        ),
    )
    return MotorSpec(
        name="Medusa KNSB A",
        grains=grains,
        grain_separation_m=0.01,
        grains_center_of_mass_m=0.5403902229538684,
        propellant_name="Nakka - KNSB (2)",
        propellant_density_kg_m3=1841.0,
        nozzle=NozzleSpec(
            throat_radius_m=0.017,
            exit_radius_m=0.039,
            position_m=0.016,
            throat_length_m=0.005,
            converging_angle_deg=45.0,
            diverging_angle_deg=15.0,
            efficiency=0.85,
        ),
        casing=MotorCasingSpec(
            inner_radius_m=casing_inner_radius_m,
            wall_thickness_m=0.003175,
            length_m=casing_length_m,
            internal_clearance_m=internal_clearance_m,
            yield_strength_pa=145_000_000.0,
            dry_mass_kg=7.5,
            dry_inertia_kg_m2=(0.7678260027343752, 0.7678260027343752, 0.023152005468749997),
            center_of_dry_mass_m=0.55,
        ),
        burn_time_s=(0.0, 3.9),
        thrust_curve=((0.0, 0.0), (0.03, 3159.6675), (3.87, 1766.9398), (3.9, 0.0)),
        interpolation_method=interpolation_method,
    )


def test_environment_builder_requires_nc_without_isa_fallback_and_supports_oper_and_enda(
    tmp_path: Path,
) -> None:
    mission_oper, oper_nc = _load_real_mission(site_id="irec_oper")
    env_oper = build_environment(mission_oper.environment, oper_nc)
    assert env_oper.elevation == pytest.approx(1401.0)
    assert env_oper.latitude == pytest.approx(32.94019)
    assert env_oper.longitude == pytest.approx(-106.92056)
    assert env_oper.pressure(1401.0) > 80_000.0

    # ENDA ensemble selects requested member without falling back to ISA.
    mission_enda, enda_nc = _load_real_mission(site_id="irec_enda_grid")
    env_m0 = build_environment(
        mission_enda.environment.model_copy(update={"ensemble_member": 0}),
        enda_nc,
    )
    env_m3 = build_environment(
        mission_enda.environment.model_copy(update={"ensemble_member": 3}),
        enda_nc,
    )
    assert env_m0.ensemble_member == 0
    assert env_m3.ensemble_member == 3
    assert env_m0.num_ensemble_members == 10
    assert (
        env_m0.wind_velocity_x(3000.0) != env_m3.wind_velocity_x(3000.0)
        or env_m0.temperature(3000.0) != env_m3.temperature(3000.0)
    )

    # NetCDF dictionary builder omits 'ensemble' for OPER and includes it for ENDA.
    oper_dict = build_netcdf_dictionary(NetCdfVariableMap(), Era5DatasetKind.OPER)
    assert "ensemble" not in oper_dict
    enda_dict = build_netcdf_dictionary(NetCdfVariableMap(), Era5DatasetKind.ENDA)
    assert enda_dict["ensemble"] == "number"

    missing_ensemble_map = NetCdfVariableMap(ensemble_number=None)
    with pytest.raises(ValueError, match="ensemble_number"):
        build_netcdf_dictionary(missing_ensemble_map, Era5DatasetKind.ENDA)

    # Non-.nc extension or missing .nc file fails closed (no ISA fallback!).
    bad_csv = tmp_path / "isa.csv"
    bad_csv.write_text("0,101325\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"\.nc"):
        build_environment(mission_oper.environment, bad_csv)

    with pytest.raises(FileNotFoundError):
        build_environment(mission_oper.environment, tmp_path / "missing.nc")

    # model_copy bypassing EnvironmentSpec validator must still fail on non-.nc asset.
    unvalidated_spec = mission_oper.environment.model_copy(
        update={"atmosphere_asset": "standard_isa.csv"}
    )
    with pytest.raises(ValueError, match=r"\.nc"):
        build_environment(unvalidated_spec, oper_nc)

    # Out-of-range ensemble member raises ValueError from RocketPy without ISA fallback.
    with pytest.raises(ValueError):
        build_environment(
            mission_enda.environment.model_copy(update={"ensemble_member": 99}),
            enda_nc,
        )


def test_motor_builder_enforces_geometry_guard_before_rocketpy_and_builds_in_memory() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    mission, _ = _load_real_mission()
    motor = build_solid_motor(mission.rocket.motor)

    assert motor.coordinate_system_orientation == "nozzle_to_combustion_chamber"
    assert motor.dry_mass == pytest.approx(
        golden["rocketpy_baseline_88deg"]["inputs"]["motor_dry_mass_kg"], rel=1e-12
    )
    assert (motor.dry_I_11, motor.dry_I_22, motor.dry_I_33) == pytest.approx(
        tuple(golden["rocketpy_baseline_88deg"]["inputs"]["motor_dry_inertia_kg_m2"]),
        rel=1e-12,
    )
    assert motor.center_of_dry_mass_position == pytest.approx(
        golden["rocketpy_baseline_88deg"]["inputs"]["motor_center_of_dry_mass_m"], rel=1e-12
    )
    assert motor.grains_center_of_mass_position == pytest.approx(
        golden["rocketpy_baseline_88deg"]["inputs"]["grains_center_of_mass_m"], rel=1e-12
    )
    assert float(motor.propellant_initial_mass) == pytest.approx(
        golden["openmotor_baselines"]["medusa_knsb_a"]["propellant_mass_kg"], rel=1e-12
    )
    assert float(motor.total_impulse) == pytest.approx(
        golden["rocketpy_baseline_88deg"]["metrics"]["total_impulse_ns"], rel=1e-7
    )
    assert motor.only_radial_burn is False

    # Thrust factor scaling & radial burn / akima mapping.
    scaled_motor = build_solid_motor(mission.rocket.motor, thrust_factor=1.15)
    assert float(scaled_motor.total_impulse) == pytest.approx(
        float(motor.total_impulse) * 1.15, rel=1e-9
    )
    radial_motor = build_solid_motor(
        _sample_motor(
            inhibited_ends=GrainInhibition.BOTH,
            interpolation_method=InterpolationMethod.AKIMA,
        )
    )
    assert radial_motor.only_radial_burn is True
    assert radial_motor.interpolate == "akima"

    with pytest.raises(ValueError, match="thrust_factor"):
        build_solid_motor(mission.rocket.motor, thrust_factor=0.0)
    with pytest.raises(ValueError, match="thrust_factor"):
        build_solid_motor(mission.rocket.motor, thrust_factor=float("nan"))

    # Axial overflow must raise GeometryValidationError BEFORE SolidMotor is called.
    axial_overflow = _sample_motor(casing_length_m=1.04, internal_clearance_m=0.04)
    with patch("hefesto.adapters.rocketpy.motor_builder.SolidMotor") as solid_motor_cls:
        with pytest.raises(GeometryValidationError, match="exceeds available casing"):
            build_solid_motor(axial_overflow)
        solid_motor_cls.assert_not_called()

    # Radial overflow must raise GeometryValidationError BEFORE SolidMotor is called.
    radial_overflow = _sample_motor(grain_outer_radius_m=0.055)
    with patch("hefesto.adapters.rocketpy.motor_builder.SolidMotor") as solid_motor_cls:
        with pytest.raises(GeometryValidationError, match="exceeds casing inner radius"):
            build_solid_motor(radial_overflow)
        solid_motor_cls.assert_not_called()


def test_rocket_builder_uses_in_memory_drag_curves_and_supports_scaling_and_protocol() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    mission, _ = _load_real_mission()
    rocket_spec = mission.rocket

    assert compute_rocket_dry_mass_kg(rocket_spec) == pytest.approx(
        golden["dry_mass"]["wall_2mm_kg"], rel=1e-12
    )

    rocket = build_rocket(rocket_spec)
    assert rocket.coordinate_system_orientation == "nose_to_tail"
    assert rocket.mass == pytest.approx(golden["dry_mass"]["wall_2mm_kg"], rel=1e-12)
    assert rocket.center_of_mass_without_motor == pytest.approx(
        golden["rocketpy_baseline_88deg"]["inputs"]["center_of_mass_without_motor_m"], rel=1e-12
    )
    assert (
        rocket.I_11_without_motor,
        rocket.I_22_without_motor,
        rocket.I_33_without_motor,
    ) == pytest.approx(
        tuple(golden["rocketpy_baseline_88deg"]["inputs"]["inertia_kg_m2"]), rel=1e-12
    )
    assert len(rocket.parachutes) == 2

    # Drag factor scales in-memory Cd without reading CSV paths from disk.
    scaled_rocket = build_rocket(rocket_spec, drag_factor=1.2)
    assert scaled_rocket.power_off_drag(0.5) == pytest.approx(
        rocket.power_off_drag(0.5) * 1.2, rel=1e-12
    )
    assert scaled_rocket.power_on_drag(0.5) == pytest.approx(
        rocket.power_on_drag(0.5) * 1.2, rel=1e-12
    )

    # Custom DragModelProtocol implementation is accepted cleanly.
    class ConstantDragModel:
        def power_off_cd(self, mach: float) -> float:
            return 0.42 + 0.0 * mach

        def power_on_cd(self, mach: float) -> float:
            return 0.39 + 0.0 * mach

        def power_off_curve(self) -> list[tuple[float, float]]:
            return [(0.0, 0.42), (2.0, 0.42)]

        def power_on_curve(self) -> list[tuple[float, float]]:
            return [(0.0, 0.39), (2.0, 0.39)]

    custom_drag = ConstantDragModel()
    assert isinstance(custom_drag, DragModelProtocol)
    custom_rocket = build_rocket(rocket_spec, drag_model=custom_drag, dry_mass_kg=20.0)
    assert custom_rocket.mass == pytest.approx(20.0)
    assert custom_rocket.power_off_drag(0.5) == pytest.approx(0.42)
    assert custom_rocket.power_on_drag(0.5) == pytest.approx(0.39)

    # Blocking motor geometry guard also prevents Rocket instantiation when rocket.motor overflows.
    overflow_rocket_spec = rocket_spec.model_copy(
        update={"motor": _sample_motor(casing_length_m=0.95, internal_clearance_m=0.0)}
    )
    with (
        patch("hefesto.adapters.rocketpy.motor_builder.SolidMotor") as solid_motor_cls,
        patch("hefesto.adapters.rocketpy.rocket_builder.Rocket") as rocket_cls,
    ):
        with pytest.raises(GeometryValidationError, match="exceeds available casing"):
            build_rocket(overflow_rocket_spec)
        solid_motor_cls.assert_not_called()
        rocket_cls.assert_not_called()

    # Non-default DatabaseDragModel scaling works identically via drag_model injection.
    db_drag = DatabaseDragModel.from_rocket(rocket_spec, drag_factor=0.9)
    db_rocket = build_rocket(rocket_spec, drag_model=db_drag)
    assert db_rocket.power_off_drag(0.5) == pytest.approx(rocket.power_off_drag(0.5) * 0.9)


def test_flight_runner_matches_golden_baseline_with_output_selection_and_no_leaks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    expected = golden["rocketpy_baseline_88deg"]["metrics"]
    mission, nc_path = _load_real_mission(site_id="irec_oper", terminate_on_apogee=False)

    backend_before = matplotlib.get_backend()
    sentinel_fig, _ = plt.subplots()
    sentinel_number = sentinel_fig.number
    figs_before = list(plt.get_fignums())

    # Default OutputSelection omits trajectory series and never leaks Flight or MPL objects.
    default_result = run_flight(mission, nc_path)
    assert isinstance(default_result, FlightResult)
    for empty_field in (
        "x_series",
        "y_series",
        "altitude_agl_series",
        "speed_series",
        "vertical_velocity_series",
        "acceleration_series",
        "mach_series",
        "cg_series",
        "cp_series",
        "static_margin_series",
        "drag_series",
        "power_off_drag_curve",
        "power_on_drag_curve",
        "thrust_series",
    ):
        assert getattr(default_result, empty_field) == ()

    assert default_result.apogee_agl_m == pytest.approx(expected["apogee_agl_m"], rel=1e-6)
    assert default_result.apogee_msl_m == pytest.approx(expected["apogee_msl_m"], rel=1e-6)
    assert default_result.apogee_time_s == pytest.approx(expected["apogee_time_s"], rel=1e-6)
    assert default_result.flight_time_s == pytest.approx(expected["flight_time_s"], rel=1e-6)
    assert default_result.max_speed_ms == pytest.approx(expected["max_speed_ms"], rel=1e-6)
    assert default_result.max_mach == pytest.approx(expected["max_mach"], rel=1e-6)
    assert default_result.rail_exit_velocity_ms == pytest.approx(
        expected["rail_exit_velocity_ms"], rel=1e-6
    )
    assert default_result.min_static_margin_calibers == pytest.approx(
        expected["min_static_margin_calibers"], rel=1e-6
    )
    assert default_result.max_static_margin_calibers is not None
    assert default_result.max_static_margin_calibers > default_result.min_static_margin_calibers
    assert default_result.total_impulse_ns == pytest.approx(expected["total_impulse_ns"], rel=1e-6)
    assert default_result.dry_mass_kg == pytest.approx(expected["dry_mass_kg"], rel=1e-12)
    assert default_result.landing_velocity_ms is not None and default_result.landing_velocity_ms > 0
    assert default_result.impact_distance_m is not None and default_result.impact_distance_m > 0

    # Selective OutputSelection populates only requested curves in memory.
    env = build_environment(mission.environment, nc_path)
    rocket = build_rocket(mission.rocket, drag_factor=1.15)
    selected_result = execute_flight(
        rocket,
        env,
        mission.launch,
        output_selection=OutputSelection(altitude_agl=True, mach=True),
    )
    assert len(selected_result.altitude_agl_series) > 100
    assert len(selected_result.mach_series) == len(selected_result.altitude_agl_series)
    for empty_field in (
        "x_series",
        "y_series",
        "speed_series",
        "vertical_velocity_series",
        "acceleration_series",
        "cg_series",
        "cp_series",
        "static_margin_series",
        "drag_series",
        "power_off_drag_curve",
        "power_on_drag_curve",
        "thrust_series",
    ):
        assert getattr(selected_result, empty_field) == ()

    # Full OutputSelection.all() with terminate_on_apogee=True extracts all 12 series + Cd curves.
    apogee_mission = mission.model_copy(
        update={"launch": LaunchConfig(terminate_on_apogee=True)}
    )
    apogee_result = run_flight(
        apogee_mission,
        nc_path,
        output_selection=OutputSelection.all(),
        drag_factor=1.15,
    )
    assert apogee_result.landing_velocity_ms is None
    assert apogee_result.impact_distance_m is None
    n_samples = len(apogee_result.altitude_agl_series)
    assert n_samples > 50
    for time_field in (
        "x_series",
        "y_series",
        "speed_series",
        "vertical_velocity_series",
        "acceleration_series",
        "mach_series",
        "cg_series",
        "cp_series",
        "static_margin_series",
        "drag_series",
        "thrust_series",
    ):
        assert len(getattr(apogee_result, time_field)) == n_samples
    assert len(apogee_result.power_off_drag_curve) > 100
    assert len(apogee_result.power_on_drag_curve) > 100
    assert apogee_result.power_off_drag_curve[0][1] == pytest.approx(
        mission.rocket.power_off_drag.points[0][1] * 1.15
    )
    assert apogee_result.power_on_drag_curve[0][1] == pytest.approx(
        mission.rocket.power_on_drag.points[0][1] * 1.15
    )

    assert matplotlib.get_backend() == backend_before
    assert plt.fignum_exists(sentinel_number), "external sentinel figure must survive run_flight"
    assert list(plt.get_fignums()) == figs_before

    # A drawing failure must warn but never discard the completed FlightResult.
    broken_rocket = build_rocket(mission.rocket)
    monkeypatch.setattr(
        broken_rocket,
        "draw",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("draw boom")),
    )
    fast_mission = mission.model_copy(
        update={"launch": LaunchConfig(terminate_on_apogee=True)}
    )
    with pytest.warns(RuntimeWarning, match="diagrama"):
        fallback_result = execute_flight(
            broken_rocket,
            env,
            fast_mission.launch,
            output_selection=OutputSelection.none(),
        )
    assert fallback_result.rocket_draw_png_b64 is None
    assert fallback_result.apogee_agl_m > 0.0
    assert matplotlib.get_backend() == backend_before
    assert plt.fignum_exists(sentinel_number)
    assert list(plt.get_fignums()) == figs_before
    plt.close(sentinel_fig)


def test_extract_flight_result_uses_effective_rail_lengths_and_handles_no_impact_stub() -> None:
    # Verify RocketPy 1.13.0 uses effective_1rl / effective_2rl (never effective1rl) cleanly.
    mission, nc_path = _load_real_mission(site_id="irec_oper", terminate_on_apogee=True)
    env = build_environment(mission.environment, nc_path)
    rocket = build_rocket(mission.rocket)

    from rocketpy import Flight

    flight = Flight(
        rocket=rocket,
        environment=env,
        rail_length=mission.launch.rail_length_m,
        inclination=mission.launch.inclination_deg,
        heading=mission.launch.heading_deg,
        terminate_on_apogee=True,
        verbose=False,
    )
    assert hasattr(flight, "effective_1rl")
    assert hasattr(flight, "effective_2rl")
    assert not hasattr(flight, "effective1rl")
    assert flight.effective_1rl > 0.0
    assert flight.effective_2rl > 0.0

    # Stub Flight verifies exact mapping of OutputSelection and impact_state fallback.
    class FakeSeries:
        def __init__(self, rows: list[list[float]]) -> None:
            self._rows = np.array(rows, dtype=float)

        def get_source(self):
            return self._rows

    stub_flight = SimpleNamespace(
        env=SimpleNamespace(elevation=1401.0),
        rocket=SimpleNamespace(
            mass=18.85,
            motor=SimpleNamespace(total_impulse=11514.4),
            center_of_mass=lambda t: 1.72 - 0.05 * t,
            cp_position=lambda mach: 2.11 + 0.02 * mach,
            _power_off_drag_input=FakeSeries([[0.0, 0.45], [1.0, 0.72]]),
            _power_on_drag_input=FakeSeries([[0.0, 0.41], [1.0, 0.65]]),
        ),
        apogee=4979.2,
        apogee_time=26.7,
        t_final=168.7,
        max_speed=305.8,
        max_mach_number=0.898,
        out_of_rail_velocity=27.05,
        min_stability_margin=2.36,
        max_stability_margin=4.02,
        impact_state=np.array(
            [450.0, -50.0, 1401.0, 0.0, 0.0, -18.3, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        ),
        impact_velocity=-18.3,
        x_impact=450.0,
        y_impact=-50.0,
        x=FakeSeries([[0.0, 0.0], [1.0, 2.5]]),
        y=FakeSeries([[0.0, 0.0], [1.0, -1.5]]),
        altitude=FakeSeries([[0.0, 0.0], [1.0, 100.0]]),
        speed=FakeSeries([[0.0, 0.0], [1.0, 82.0]]),
        vz=FakeSeries([[0.0, 0.0], [1.0, 80.0]]),
        acceleration=FakeSeries([[0.0, 0.0], [1.0, 75.0]]),
        mach_number=FakeSeries([[0.0, 0.0], [1.0, 0.3]]),
        stability_margin=FakeSeries([[0.0, 2.36], [1.0, 2.50]]),
        aerodynamic_drag=FakeSeries([[0.0, 0.0], [1.0, 42.0]]),
        net_thrust=FakeSeries([[0.0, 0.0], [1.0, 3100.0]]),
    )
    extracted = extract_flight_result(stub_flight, selection=OutputSelection.all())  # type: ignore[arg-type]
    assert extracted.apogee_agl_m == pytest.approx(3578.2)
    assert extracted.landing_velocity_ms == pytest.approx(18.3)
    assert extracted.impact_distance_m == pytest.approx(math.hypot(450.0, -50.0))
    assert extracted.x_series == ((0.0, 0.0), (1.0, 2.5))
    assert extracted.y_series == ((0.0, 0.0), (1.0, -1.5))
    assert extracted.altitude_agl_series == ((0.0, 0.0), (1.0, 100.0))
    assert extracted.speed_series == ((0.0, 0.0), (1.0, 82.0))
    assert extracted.vertical_velocity_series == ((0.0, 0.0), (1.0, 80.0))
    assert extracted.acceleration_series == ((0.0, 0.0), (1.0, 75.0))
    assert extracted.mach_series == ((0.0, 0.0), (1.0, 0.3))
    assert extracted.cg_series[0] == pytest.approx((0.0, 1.72))
    assert extracted.cg_series[1] == pytest.approx((1.0, 1.67))
    assert extracted.cp_series[0] == pytest.approx((0.0, 2.11))
    assert extracted.cp_series[1] == pytest.approx((1.0, 2.116))
    assert extracted.static_margin_series == ((0.0, 2.36), (1.0, 2.50))
    assert extracted.drag_series == ((0.0, 0.0), (1.0, 42.0))
    assert extracted.power_off_drag_curve == ((0.0, 0.45), (1.0, 0.72))
    assert extracted.power_on_drag_curve == ((0.0, 0.41), (1.0, 0.65))
    assert extracted.thrust_series == ((0.0, 0.0), (1.0, 3100.0))

    # No-impact stub (1-element impact_state) maps landing/impact metrics to None.
    stub_flight.impact_state = np.array([0.0])
    no_impact = extract_flight_result(stub_flight, selection=OutputSelection.none())  # type: ignore[arg-type]
    assert no_impact.landing_velocity_ms is None
    assert no_impact.impact_distance_m is None
    assert no_impact.altitude_agl_series == ()
    assert no_impact.drag_series == ()
    assert no_impact.thrust_series == ()

    # Dry mass override & validation checks on rocket_builder.
    overridden_spec = mission.rocket.model_copy(update={"dry_mass_override_kg": 21.5})
    assert compute_rocket_dry_mass_kg(overridden_spec) == pytest.approx(21.5)
    with pytest.raises(ValueError, match="drag_factor"):
        build_rocket(mission.rocket, drag_factor=0.0)
    with pytest.raises(ValueError, match="dry_mass_kg"):
        build_rocket(mission.rocket, dry_mass_kg=-1.0)
    with pytest.raises(ValueError, match="atmosphere_path"):
        build_environment(mission.environment, "   ")

    # Package exports sanity check
    for symbol in rocketpy_pkg.__all__:
        assert hasattr(rocketpy_pkg, symbol)
    for symbol in adapters_pkg.__all__:
        assert hasattr(adapters_pkg, symbol)
    assert DragCurveSpec.__name__ == "DragCurveSpec"
    assert NoseConeSpec.__name__ == "NoseConeSpec"


def test_rocket_builder_respects_mass_mode_and_fin_geometry_mode() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    mission, nc_path = _load_real_mission(site_id="irec_oper", terminate_on_apogee=True)

    # MassMode="measured" requires dry_mass_override_kg; MassMode="calculated" ignores it.
    with pytest.raises(ValueError, match="measured"):
        compute_rocket_dry_mass_kg(mission.rocket, mass_mode="measured")
    with pytest.raises(ValueError, match="measured"):
        build_rocket(mission.rocket, mass_mode="measured")

    measured_rocket = mission.rocket.model_copy(update={"dry_mass_override_kg": 21.644})
    assert compute_rocket_dry_mass_kg(measured_rocket, mass_mode="measured") == pytest.approx(
        21.644
    )
    assert compute_rocket_dry_mass_kg(measured_rocket, mass_mode="calculated") == pytest.approx(
        golden["dry_mass"]["wall_2mm_kg"], rel=1e-12
    )
    assert build_rocket(measured_rocket, mass_mode="measured").mass == pytest.approx(21.644)
    assert build_rocket(measured_rocket, mass_mode="calculated").mass == pytest.approx(
        golden["dry_mass"]["wall_2mm_kg"], rel=1e-12
    )

    # FinGeometryMode="trapezoidal" derives area-preserving trapezoidal fins or uses explicit dims.
    trap_derived_rkt = build_rocket(mission.rocket, fin_geometry_mode="trapezoidal")
    assert len(trap_derived_rkt.aerodynamic_surfaces) >= 2
    explicit_fins = mission.rocket.fins.model_copy(
        update={
            "root_chord_m": 0.18,
            "tip_chord_m": 0.07458606,
            "span_m": 0.13999711,
            "sweep_length_m": 0.10051811,
        }
    )
    trap_explicit_spec = mission.rocket.model_copy(update={"fins": explicit_fins})
    trap_result = run_flight(
        mission.model_copy(update={"rocket": trap_explicit_spec}),
        nc_path,
        mass_mode="calculated",
        fin_geometry_mode="trapezoidal",
        output_selection=OutputSelection(altitude_agl=True),
    )
    assert trap_result.apogee_agl_m > 3000.0
    assert len(trap_result.altitude_agl_series) > 50

    with pytest.raises(ValueError, match="mass_mode"):
        compute_rocket_dry_mass_kg(mission.rocket, mass_mode="invalid")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="fin_geometry_mode"):
        build_rocket(mission.rocket, fin_geometry_mode="elliptical")  # type: ignore[arg-type]


def test_compute_rocket_dry_mass_includes_nose_shell_and_matches_physics_layer() -> None:
    from hefesto.physics import derive_dry_mass

    mission, _ = _load_real_mission()
    rocket = mission.rocket
    shell = PointMassComponent(name="Nose Shell", mass_kg=0.5442113886585497, position_m=0.2777)
    with_shell = rocket.model_copy(
        update={"nose_cone": rocket.nose_cone.model_copy(update={"shell": shell})}
    )

    assert compute_rocket_dry_mass_kg(with_shell) == pytest.approx(
        compute_rocket_dry_mass_kg(rocket) + shell.mass_kg, rel=1e-12
    )
    # Cross-layer parity: adapters duplicate the component sum (no physics import allowed).
    assert compute_rocket_dry_mass_kg(with_shell) == pytest.approx(
        derive_dry_mass(with_shell), rel=1e-12
    )
    assert build_rocket(with_shell).mass == pytest.approx(derive_dry_mass(with_shell), rel=1e-12)


def test_isa_environment_reproduces_ork_reference_profile_and_keeps_era5_default() -> None:
    from hefesto.adapters.rocketpy.environment_builder import build_isa_profiles, build_isa_wind

    isa = IsaAtmosphereSpec(
        elevation_m=1000.0,
        base_temperature_k=299.15,
        base_pressure_pa=91000.0,
        wind_speed_ms=5.2,
        wind_direction_deg=270.0,
    )
    pressure, temperature = build_isa_profiles(isa, max_height_m=20000.0)
    heights = [height for height, _ in pressure]
    assert heights[0] == 0.0 and heights[-1] == pytest.approx(20000.0)
    assert all(left[1] > right[1] for left, right in zip(pressure, pressure[1:], strict=False))
    assert all(
        left[1] >= right[1] for left, right in zip(temperature, temperature[1:], strict=False)
    )
    # Sampled at the launch elevation: exactly the configured base state.
    assert temperature[0][1] == pytest.approx(299.15 + 0.0065 * 1000.0, rel=1e-12)
    assert temperature[12][1] == pytest.approx(299.15, rel=1e-12)
    assert pressure[12][1] == pytest.approx(91000.0, rel=1e-12)
    assert len({value for height, value in temperature if height > 11_000.0}) == 1
    assert build_isa_wind(isa) == pytest.approx((-5.2, 0.0), abs=1e-12)

    mission, _ = _load_real_mission(site_id="ork_reference")
    env = build_environment(mission.environment, None, isa=isa)
    assert env.elevation == pytest.approx(1000.0)
    assert env.temperature(1000.0) == pytest.approx(299.15, rel=1e-6)
    assert env.pressure(1000.0) == pytest.approx(91000.0, rel=1e-6)
    assert env.density(1000.0) == pytest.approx(1.0597, rel=1e-3)
    assert env.wind_velocity_x(1000.0) == pytest.approx(-5.2, rel=1e-9)
    assert env.wind_velocity_y(1000.0) == pytest.approx(0.0, abs=1e-9)

    # Default path is still ERA5-only and fails closed without a .nc file.
    with pytest.raises(ValueError, match=r".nc"):
        build_environment(mission.environment, None)


def test_build_rocket_scales_inertia_tensor_with_measured_dry_mass() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    mission, _ = _load_real_mission()
    calculated_dry_mass_kg = compute_rocket_dry_mass_kg(
        mission.rocket, mass_mode="calculated"
    )
    assert calculated_dry_mass_kg == pytest.approx(
        golden["dry_mass"]["wall_2mm_kg"], rel=1e-12
    )

    measured_mass_kg = 21.644
    measured_rocket = mission.rocket.model_copy(
        update={"dry_mass_override_kg": measured_mass_kg}
    )
    inertia_scale = measured_mass_kg / calculated_dry_mass_kg
    built = build_rocket(measured_rocket, mass_mode="measured")

    assert built.mass == pytest.approx(measured_mass_kg)
    assert built.I_11_without_motor == pytest.approx(
        measured_rocket.inertia_kg_m2[0] * inertia_scale, rel=1e-12
    )
    assert built.I_33_without_motor == pytest.approx(
        measured_rocket.inertia_kg_m2[2] * inertia_scale, rel=1e-12
    )
    assert built.I_11_without_motor > measured_rocket.inertia_kg_m2[0]

    # Calculated mode and the Golden Master keep the catalog tensor untouched.
    calculated_built = build_rocket(measured_rocket, mass_mode="calculated")
    assert calculated_built.I_11_without_motor == pytest.approx(
        measured_rocket.inertia_kg_m2[0], rel=1e-12
    )
    assert calculated_built.I_33_without_motor == pytest.approx(
        measured_rocket.inertia_kg_m2[2], rel=1e-12
    )
    golden_rocket = build_rocket(mission.rocket)
    assert golden_rocket.I_11_without_motor == pytest.approx(
        mission.rocket.inertia_kg_m2[0], rel=1e-12
    )

    # A measured mass equal to the calculated mass is a no-op for inertia.
    same_mass = mission.rocket.model_copy(
        update={"dry_mass_override_kg": calculated_dry_mass_kg}
    )
    same_built = build_rocket(same_mass, mass_mode="measured")
    assert same_built.I_11_without_motor == pytest.approx(
        same_mass.inertia_kg_m2[0], rel=1e-12
    )
