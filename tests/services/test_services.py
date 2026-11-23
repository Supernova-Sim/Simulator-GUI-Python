"""TDD tests for Hefesto application service layer (Phase 5)."""

from __future__ import annotations

import json
import multiprocessing
import pickle
import shutil
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

import hefesto.services as services_pkg
from hefesto.domain import (
    AssetCategory,
    BallisticsResult,
    CatalogOverview,
    GeometryValidationError,
    GrainSpec,
    LaunchConfig,
    MissionPreset,
    MotorOverride,
    OutputSelection,
    RunSummary,
    SafetyCriterion,
    SafetyLimits,
    SimulationConfig,
    SimulationResult,
)
from hefesto.services import (
    DEFAULT_LIMITS_ID,
    DEFAULT_MOTOR_ID,
    DEFAULT_ROCKET_ID,
    DEFAULT_SITE_ID,
    ServiceAlert,
    SimulationServiceError,
    asset_exists,
    build_mission_from_preset,
    build_mission_from_selection,
    calculate_rocket_dry_mass_kg,
    combine_motor_overrides,
    compose_simulation_config,
    delete_run_snapshot,
    get_catalog_overview,
    list_assets,
    list_run_snapshots,
    load_motor_preset,
    load_rocket_preset,
    load_rocket_spec,
    load_run_snapshot,
    recalculate_casing,
    resolve_asset_path,
    run_ballistics_check,
    run_deterministic,
    run_motor_ballistics_for_preset,
    save_limits_preset,
    save_mission_preset,
    save_motor_preset,
    save_rocket_preset,
    save_run_snapshot,
    save_site_preset,
    summarize_rocket_structure,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = REPO_ROOT / "tests" / "golden" / "hefesto_baseline.json"


def _seed_isolated_workspace(tmp_path: Path) -> Path:
    """Copy real assets and catalog into tmp_path so tests never touch repo data/runs/."""
    shutil.copytree(REPO_ROOT / "data" / "assets", tmp_path / "data" / "assets")
    shutil.copytree(REPO_ROOT / "data" / "catalog", tmp_path / "data" / "catalog")
    return tmp_path


def test_catalog_asset_and_structure_services_compose_config_and_export_all() -> None:
    overview = get_catalog_overview()
    assert isinstance(overview, CatalogOverview)
    assert DEFAULT_ROCKET_ID in overview.rocket_presets
    assert DEFAULT_MOTOR_ID in overview.motor_presets
    assert DEFAULT_SITE_ID in overview.environment_presets
    assert "ork_parity" in overview.mission_presets
    assert len(overview.assets) == 15
    assert len(list_assets(AssetCategory.ATMOSPHERE)) == 5
    assert asset_exists(AssetCategory.MOTORS, "medusa_knsb_a.ric")
    assert resolve_asset_path(AssetCategory.DRAG, "power_off.csv").is_file()

    with pytest.raises(ValueError):
        resolve_asset_path(AssetCategory.MOTORS, "../escape.ric")

    default_cfg = compose_simulation_config()
    assert isinstance(default_cfg, SimulationConfig)
    assert default_cfg.mission.rocket.name == DEFAULT_ROCKET_ID
    assert default_cfg.mission.rocket.motor.name == DEFAULT_MOTOR_ID
    assert default_cfg.mission.environment.atmosphere_asset == "irec_era5_oper.nc"
    assert default_cfg.output_selection == OutputSelection.all()

    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    structure = summarize_rocket_structure(default_cfg.mission.rocket)
    assert structure.dry_mass_kg == pytest.approx(golden["dry_mass"]["wall_2mm_kg"], rel=1e-12)
    assert calculate_rocket_dry_mass_kg(default_cfg.mission.rocket, mass_mode="calculated") == (
        pytest.approx(golden["dry_mass"]["wall_2mm_kg"], rel=1e-12)
    )

    measured_rkt = default_cfg.mission.rocket.model_copy(update={"dry_mass_override_kg": 21.644})
    assert calculate_rocket_dry_mass_kg(measured_rkt, mass_mode="measured") == pytest.approx(21.644)
    assert calculate_rocket_dry_mass_kg(measured_rkt, mass_mode="calculated") == pytest.approx(
        golden["dry_mass"]["wall_2mm_kg"], rel=1e-12
    )
    with pytest.raises(ValueError, match="measured"):
        calculate_rocket_dry_mass_kg(default_cfg.mission.rocket, mass_mode="measured")

    # Test load_rocket_spec with explicit motor_id and MissionPreset composition in isolated root.
    alt_rocket = load_rocket_spec(DEFAULT_ROCKET_ID, motor_id="medusa_n3174")
    assert alt_rocket.motor.name == "medusa_n3174"
    assert alt_rocket.motor.motor_asset is None

    for symbol in services_pkg.__all__:
        assert hasattr(services_pkg, symbol)


def test_mission_preset_and_preset_overrides_combine_with_runtime_overrides(
    tmp_path: Path,
) -> None:
    root = _seed_isolated_workspace(tmp_path)
    base_motor = load_motor_preset(DEFAULT_MOTOR_ID, repo_root=root)
    custom_motor = base_motor.model_copy(
        update={
            "name": "medusa_custom_ov",
            "overrides": (
                MotorOverride(path="nozzle.throat", value=0.036),
                MotorOverride(path="grains.*.properties.inhibitedEnds", value="Both"),
            ),
        }
    )
    save_motor_preset(custom_motor, preset_id="medusa_custom_ov", repo_root=root)

    base_rocket = load_rocket_preset(DEFAULT_ROCKET_ID, repo_root=root)
    custom_rocket = base_rocket.model_copy(
        update={"name": "hefesto_custom", "motor_preset_name": "medusa_custom_ov"}
    )
    save_rocket_preset(custom_rocket, preset_id="hefesto_custom", repo_root=root)

    save_limits_preset(SafetyLimits(max_kn=300.0), preset_id="relaxed", repo_root=root)
    mission_preset = MissionPreset(
        name="custom_irec_86deg",
        rocket_preset_name="hefesto_custom",
        environment_preset_name=DEFAULT_SITE_ID,
        launch=LaunchConfig(inclination_deg=86.0, terminate_on_apogee=True),
        safety_limits=SafetyLimits(max_kn=280.0),
    )
    save_mission_preset(mission_preset, preset_id="custom_irec_86deg", repo_root=root)

    mission_from_preset = build_mission_from_preset("custom_irec_86deg", repo_root=root)
    assert mission_from_preset.name == "custom_irec_86deg"
    assert mission_from_preset.launch.inclination_deg == pytest.approx(86.0)
    assert mission_from_preset.safety_limits.max_kn == pytest.approx(280.0)

    cfg = compose_simulation_config(
        mission_id="custom_irec_86deg",
        motor_overrides=(MotorOverride(path="grains.0.properties.inhibitedEnds", value="Neither"),),
        repo_root=root,
    )
    combined = combine_motor_overrides(custom_motor.overrides, cfg.motor_overrides)
    assert len(combined) == 3

    result = run_deterministic(cfg, repo_root=root)
    assert result.ballistics is not None
    # Preset nozzle.throat=0.036 -> radius 0.018; runtime grain 0 index override beats wildcard.
    assert result.ballistics.throat_radius_m == pytest.approx(0.018)
    assert result.ballistics.grains[0].inhibited_ends.value == "neither"
    assert result.ballistics.grains[1].inhibited_ends.value == "both"
    assert not (root / "data" / "runs").exists()


def test_run_deterministic_matches_golden_baseline_and_handles_eng_only_non_blocking(
    tmp_path: Path,
) -> None:
    root = _seed_isolated_workspace(tmp_path)
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    expected_metrics = golden["rocketpy_baseline_88deg"]["metrics"]
    expected_safety = golden["safety_baseline_medusa_knsb_a"]

    cfg = compose_simulation_config(
        rocket_id=DEFAULT_ROCKET_ID,
        motor_id=DEFAULT_MOTOR_ID,
        site_id=DEFAULT_SITE_ID,
        limits_id=DEFAULT_LIMITS_ID,
        repo_root=root,
    )
    result = run_deterministic(cfg, repo_root=root)
    assert isinstance(result, SimulationResult)
    assert result.ballistics is not None
    assert result.safety is not None
    assert result.safety.all_passed is True
    assert result.safety.hoop_stress_pa == pytest.approx(
        expected_safety["hoop_stress_pa"], rel=1e-12
    )

    assert result.flight.apogee_agl_m == pytest.approx(expected_metrics["apogee_agl_m"], rel=1e-4)
    assert result.flight.max_mach == pytest.approx(expected_metrics["max_mach"], rel=1e-4)
    assert result.flight.min_static_margin_calibers == pytest.approx(
        expected_metrics["min_static_margin_calibers"], rel=1e-4
    )
    assert result.flight.total_impulse_ns == pytest.approx(
        expected_metrics["total_impulse_ns"], rel=1e-6
    )
    assert result.flight.dry_mass_kg == pytest.approx(expected_metrics["dry_mass_kg"], rel=1e-12)
    assert len(result.flight.altitude_agl_series) > 100
    assert len(result.flight.power_off_drag_curve) > 100
    assert len(result.flight.power_on_drag_curve) > 100

    # .eng-only motor (medusa_n3174): fail-closed safety is non-blocking; 6-DOF flight succeeds.
    eng_only_cfg = compose_simulation_config(
        rocket_id=DEFAULT_ROCKET_ID,
        motor_id="medusa_n3174",
        site_id=DEFAULT_SITE_ID,
        limits_id=DEFAULT_LIMITS_ID,
        launch=LaunchConfig(terminate_on_apogee=True),
        output_selection=OutputSelection.none(),
        repo_root=root,
    )
    eng_result = run_deterministic(eng_only_cfg, repo_root=root)
    assert eng_result.ballistics is None
    assert eng_result.safety is not None
    assert eng_result.safety.all_passed is False
    by_crit = {c.criterion: c for c in eng_result.safety.checks}
    assert by_crit[SafetyCriterion.CASE_SAFETY_FACTOR].passed is False
    assert by_crit[SafetyCriterion.CASE_SAFETY_FACTOR].value is None
    assert by_crit[SafetyCriterion.PEAK_CHAMBER_PRESSURE].passed is False
    assert by_crit[SafetyCriterion.PEAK_KN].passed is False
    assert by_crit[SafetyCriterion.PEAK_MASS_FLUX].passed is False
    assert by_crit[SafetyCriterion.PORT_TO_THROAT_RATIO].passed is True
    assert eng_result.flight.apogee_agl_m > 3000.0
    assert eng_result.flight.altitude_agl_series == ()

    # Passing motor_overrides when motor_asset is None must fail explicitly.
    bad_eng_cfg = eng_only_cfg.model_copy(
        update={"motor_overrides": (MotorOverride(path="nozzle.throat", value=0.036),)}
    )
    with pytest.raises(ValueError, match="motor_asset"):
        run_deterministic(bad_eng_cfg, repo_root=root)

    # Zero automatic writes to data/runs/.
    assert not (root / "data" / "runs").exists()


def test_casing_recalculation_mass_mode_fin_mode_and_ballistics_check(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    preset = load_motor_preset(DEFAULT_MOTOR_ID, repo_root=root)
    thicker_casing = preset.casing.model_copy(update={"wall_thickness_m": 0.005, "length_m": 1.20})
    recalc = recalculate_casing(thicker_casing, base_casing=preset.casing)
    assert recalc.dry_mass_kg > preset.casing.dry_mass_kg
    assert recalc.center_of_dry_mass_m == pytest.approx(0.60)

    manual_mass = preset.casing.model_copy(update={"dry_mass_kg": 8.25})
    recalc_manual = recalculate_casing(manual_mass, base_casing=preset.casing)
    assert recalc_manual.dry_mass_kg == pytest.approx(8.25)

    base_cfg = compose_simulation_config(
        launch=LaunchConfig(terminate_on_apogee=True),
        output_selection=OutputSelection(altitude_agl=True),
        repo_root=root,
    )
    modified_rocket = base_cfg.mission.rocket.model_copy(
        update={
            "dry_mass_override_kg": 22.0,
            "motor": base_cfg.mission.rocket.motor.model_copy(update={"casing": thicker_casing}),
        }
    )
    modified_cfg = base_cfg.model_copy(
        update={
            "mission": base_cfg.mission.model_copy(update={"rocket": modified_rocket}),
            "mass_mode": "measured",
            "fin_geometry_mode": "trapezoidal",
            "drag_factor": 1.05,
            "thrust_factor": 1.02,
        }
    )
    res = run_deterministic(modified_cfg, repo_root=root)
    assert res.flight.dry_mass_kg == pytest.approx(22.0)
    assert res.safety is not None
    assert len(res.flight.altitude_agl_series) > 50

    ballistics, safety = run_ballistics_check(DEFAULT_MOTOR_ID, repo_root=root)
    assert isinstance(ballistics, BallisticsResult)
    assert safety.all_passed is True


def test_geometry_validation_error_blocks_before_rocketpy_and_isolates_adapter_errors(
    tmp_path: Path,
) -> None:
    root = _seed_isolated_workspace(tmp_path)
    base_cfg = compose_simulation_config(
        launch=LaunchConfig(terminate_on_apogee=True),
        repo_root=root,
    )

    # 1) Axial overflow via motor_overrides must raise GeometryValidationError before RocketPy.
    axial_override_cfg = base_cfg.model_copy(
        update={"motor_overrides": (MotorOverride(path="grains.*.properties.length", value=0.25),)}
    )
    with (
        patch("hefesto.services.simulation_service.run_flight") as mock_run_flight,
        patch("hefesto.adapters.rocketpy.motor_builder.SolidMotor") as mock_solid_motor,
    ):
        with pytest.raises(GeometryValidationError, match="exceeds available casing"):
            run_deterministic(axial_override_cfg, repo_root=root)
        mock_run_flight.assert_not_called()
        mock_solid_motor.assert_not_called()

    # 2) Radial overflow via motor_overrides must raise GeometryValidationError before RocketPy.
    radial_override_cfg = base_cfg.model_copy(
        update={
            "motor_overrides": (MotorOverride(path="grains.0.properties.diameter", value=0.12),)
        }
    )
    with patch("hefesto.services.simulation_service.run_flight") as mock_run_flight:
        with pytest.raises(GeometryValidationError, match="exceeds casing inner radius"):
            run_deterministic(radial_override_cfg, repo_root=root)
        mock_run_flight.assert_not_called()

    # 3) Direct casing shortening or grain edit must also block before RocketPy.
    short_casing = base_cfg.mission.rocket.motor.casing.model_copy(update={"length_m": 0.90})
    short_cfg = base_cfg.model_copy(
        update={
            "mission": base_cfg.mission.model_copy(
                update={
                    "rocket": base_cfg.mission.rocket.model_copy(
                        update={
                            "motor": base_cfg.mission.rocket.motor.model_copy(
                                update={"casing": short_casing}
                            )
                        }
                    )
                }
            )
        }
    )
    with patch("hefesto.services.simulation_service.run_flight") as mock_run_flight:
        with pytest.raises(GeometryValidationError, match="exceeds available casing"):
            run_deterministic(short_cfg, repo_root=root)
        mock_run_flight.assert_not_called()

    oversized_grains = (
        *base_cfg.mission.rocket.motor.grains[:5],
        GrainSpec(length_m=0.16, outer_radius_m=0.056, inner_radius_m=0.027),
    )
    grain_cfg = base_cfg.model_copy(
        update={
            "mission": base_cfg.mission.model_copy(
                update={
                    "rocket": base_cfg.mission.rocket.model_copy(
                        update={
                            "motor": base_cfg.mission.rocket.motor.model_copy(
                                update={"grains": oversized_grains}
                            )
                        }
                    )
                }
            )
        }
    )
    with patch("hefesto.services.simulation_service.run_flight") as mock_run_flight:
        with pytest.raises(GeometryValidationError, match="exceeds casing inner radius"):
            run_deterministic(grain_cfg, repo_root=root)
        mock_run_flight.assert_not_called()

    # 4) OpenMotor failure raises SimulationServiceError with ServiceAlert tuple (not adapter).
    bad_throat_cfg = base_cfg.model_copy(
        update={"motor_overrides": (MotorOverride(path="nozzle.throat", value=0.0),)}
    )
    with pytest.raises(SimulationServiceError) as exc_info:
        run_deterministic(bad_throat_cfg, repo_root=root)
    assert exc_info.value.stage == "ballistics"
    assert len(exc_info.value.alerts) >= 1
    assert any(a.level == "error" for a in exc_info.value.alerts)

    # 5) NetCDF / RocketPy failure raises SimulationServiceError(stage="flight").
    enda_mission = build_mission_from_selection(site_id="irec_enda_grid", repo_root=root)
    bad_env = enda_mission.environment.model_copy(update={"ensemble_member": 99})
    bad_env_cfg = SimulationConfig(
        mission=enda_mission.model_copy(update={"environment": bad_env})
    )
    with pytest.raises(SimulationServiceError) as flight_exc:
        run_deterministic(bad_env_cfg, repo_root=root)
    assert flight_exc.value.stage == "flight"


def test_picklability_and_real_spawn_process_pool_executor(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    cfg = compose_simulation_config(
        launch=LaunchConfig(terminate_on_apogee=True),
        output_selection=OutputSelection(altitude_agl=True, mach=True),
        repo_root=root,
    )

    # Explicit pickle roundtrip of config and SimulationServiceError (preserving alerts + stage).
    assert pickle.loads(pickle.dumps(cfg)) == cfg
    err = SimulationServiceError(
        "motor error",
        alerts=(ServiceAlert(level="error", category="value", description="bad throat"),),
        stage="ballistics",
    )
    unpickled_err = pickle.loads(pickle.dumps(err))
    assert isinstance(unpickled_err, SimulationServiceError)
    assert str(unpickled_err) == "motor error"
    assert unpickled_err.stage == "ballistics"
    assert unpickled_err.alerts == err.alerts

    spawn_ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=1, mp_context=spawn_ctx) as pool:
        overview = pool.submit(get_catalog_overview, str(root)).result()
        assert isinstance(overview, CatalogOverview)
        assert DEFAULT_MOTOR_ID in overview.motor_presets

        ballistics = pool.submit(
            run_motor_ballistics_for_preset, DEFAULT_MOTOR_ID, (), repo_root=str(root)
        ).result()
        assert isinstance(ballistics, BallisticsResult)

        sim_result = pool.submit(run_deterministic, cfg, str(root)).result()
        assert isinstance(sim_result, SimulationResult)
        assert sim_result.flight.apogee_agl_m > 3500.0
        assert sim_result.safety is not None and sim_result.safety.all_passed is True

        overflow_cfg = cfg.model_copy(
            update={
                "motor_overrides": (MotorOverride(path="grains.*.properties.length", value=0.25),)
            }
        )
        with pytest.raises(GeometryValidationError, match="exceeds available casing"):
            pool.submit(run_deterministic, overflow_cfg, str(root)).result()

        err_cfg = cfg.model_copy(
            update={"motor_overrides": (MotorOverride(path="nozzle.throat", value=0.0),)}
        )
        with pytest.raises(SimulationServiceError) as worker_err:
            pool.submit(run_deterministic, err_cfg, str(root)).result()
        assert worker_err.value.stage == "ballistics"
        assert len(worker_err.value.alerts) >= 1

    assert not (root / "data" / "runs").exists()


def test_run_service_manual_crud_and_no_auto_creation_of_data_runs(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    cfg = compose_simulation_config(
        launch=LaunchConfig(terminate_on_apogee=True),
        output_selection=OutputSelection.none(),
        repo_root=root,
    )

    # Listing/loading/deleting when data/runs/ does not exist must never create data/runs/.
    assert list_run_snapshots(repo_root=root) == ()
    assert not (root / "data" / "runs").exists()
    with pytest.raises(FileNotFoundError):
        load_run_snapshot("missing_run", repo_root=root)
    with pytest.raises(FileNotFoundError):
        delete_run_snapshot("missing_run", repo_root=root)
    assert not (root / "data" / "runs").exists()

    # Running deterministic simulation must not write to data/runs/.
    result = run_deterministic(cfg, repo_root=root)
    assert not (root / "data" / "runs").exists()

    # Manual save -> list -> load -> delete CRUD.
    summary = save_run_snapshot(result, repo_root=root)
    assert isinstance(summary, RunSummary)
    assert summary.run_id == result.run_id
    assert summary.snapshot_asset == f"{result.run_id}.json"
    assert (root / "data" / "runs" / summary.snapshot_asset).is_file()

    newer = result.model_copy(
        update={
            "run_id": "run_manual_newer",
            "created_at_utc": datetime(2026, 12, 1, 12, 0, tzinfo=UTC),
        }
    )
    save_run_snapshot(newer, repo_root=root)

    summaries = list_run_snapshots(repo_root=root)
    assert [s.run_id for s in summaries] == ["run_manual_newer", result.run_id]
    assert load_run_snapshot(result.run_id, repo_root=root) == result

    delete_run_snapshot(result.run_id, repo_root=root)
    assert [s.run_id for s in list_run_snapshots(repo_root=root)] == ["run_manual_newer"]
    with pytest.raises(FileNotFoundError):
        load_run_snapshot(result.run_id, repo_root=root)
    with pytest.raises(FileNotFoundError):
        delete_run_snapshot(result.run_id, repo_root=root)

    with pytest.raises(ValueError):
        delete_run_snapshot("../escape", repo_root=root)

    # save_site_preset smoke check to ensure catalog CRUD completeness
    site = build_mission_from_selection(repo_root=root).environment
    saved_site_path = save_site_preset(site, preset_id="irec_copy", repo_root=root)
    assert saved_site_path.is_file()


def test_guided_motor_override_options_physical_summary_and_rocket_editing(
    tmp_path: Path,
) -> None:
    from hefesto.domain import (
        FinSetSpec,
        MotorOverrideOption,
        MotorPhysicalSummary,
        PointMassComponent,
        TubeComponent,
    )
    from hefesto.services import (
        list_available_motor_overrides,
        load_motor_spec,
        recalculate_rocket_structure,
        rocket_preset_from_spec,
        summarize_motor_physical_metrics,
        sync_rocket_fins,
    )

    root = _seed_isolated_workspace(tmp_path)

    # 1) Guided MotorOverride options from real .ric and .eng-only presets.
    ric_preset = load_motor_preset(DEFAULT_MOTOR_ID, repo_root=root)
    options = list_available_motor_overrides(ric_preset, repo_root=root)
    assert options
    assert all(isinstance(opt, MotorOverrideOption) for opt in options)
    by_path = {opt.path: opt for opt in options}
    assert "nozzle.throat" in by_path
    assert by_path["nozzle.throat"].group == "nozzle"
    assert by_path["nozzle.throat"].unit == "m"
    assert isinstance(by_path["nozzle.throat"].current_value, float)
    assert by_path["propellant.density"].unit == "kg/m³"
    assert "grains.*.properties.length" in by_path
    for idx in range(6):
        assert f"grains.{idx}.properties.length" in by_path
        assert f"grains.{idx}.properties.coreDiameter" in by_path

    eng_preset = load_motor_preset("medusa_n3174", repo_root=root)
    assert list_available_motor_overrides(eng_preset, repo_root=root) == ()

    # 2) MotorPhysicalSummary calculation.
    motor_spec = load_motor_spec(DEFAULT_MOTOR_ID, simulate_ric=True, repo_root=root)
    ballistics = run_motor_ballistics_for_preset(DEFAULT_MOTOR_ID, repo_root=root)
    summary = summarize_motor_physical_metrics(motor_spec, ballistics)
    assert isinstance(summary, MotorPhysicalSummary)
    assert summary.dry_mass_kg == pytest.approx(motor_spec.casing.dry_mass_kg)
    assert summary.propellant_mass_kg == pytest.approx(ballistics.propellant_mass_kg)
    assert summary.total_loaded_mass_kg == pytest.approx(
        summary.dry_mass_kg + summary.propellant_mass_kg
    )
    assert 0.0 < summary.propellant_mass_fraction < 1.0
    assert summary.casing_length_m == pytest.approx(motor_spec.casing.length_m)
    assert summary.outer_diameter_m == pytest.approx(2.0 * motor_spec.casing.outer_radius_m)
    assert summary.throat_diameter_mm == pytest.approx(2.0 * ballistics.throat_radius_m * 1000.0)
    assert summary.exit_diameter_mm == pytest.approx(
        2.0 * ballistics.nozzle_exit_radius_m * 1000.0
    )
    assert summary.expansion_ratio > 1.0
    assert summary.average_thrust_n > 0.0

    # 3) Rocket structure editing (TubeComponent, PointMassComponent) and fin sync.
    base_rocket = load_rocket_spec(DEFAULT_ROCKET_ID, repo_root=root)
    base_summary = summarize_rocket_structure(base_rocket)
    extra_junction = PointMassComponent(name="Extra Coupler Mass", mass_kg=1.0, position_m=1.2)
    edited_tube = TubeComponent(
        name="Extended Tube",
        outer_radius_m=base_rocket.radius_m,
        wall_thickness_m=0.002,
        length_m=0.30,
        density_kg_m3=1850.0,
        position_m=1.5,
    )
    edited_rocket = recalculate_rocket_structure(
        base_rocket.model_copy(
            update={"components": (*base_rocket.components, extra_junction, edited_tube)}
        )
    )
    edited_summary = summarize_rocket_structure(edited_rocket)
    assert edited_summary.dry_mass_kg > base_summary.dry_mass_kg + 1.0
    assert edited_rocket.center_of_mass_without_motor_m == pytest.approx(
        edited_summary.center_of_mass_m
    )

    trap_fins = FinSetSpec(
        name="Main Fins",
        count=3,
        position_m=2.55,
        shape_points_m=base_rocket.fins.shape_points_m,
        root_chord_m=0.22,
        tip_chord_m=0.12,
        span_m=0.15,
        sweep_length_m=0.06,
    )
    synced_rocket = sync_rocket_fins(
        edited_rocket,
        trap_fins,
        thickness_m=0.005,
        density_kg_m3=2700.0,
        fin_geometry_mode="trapezoidal",
    )
    assert synced_rocket.fins.count == 3
    assert len(synced_rocket.fins.shape_points_m) == 4
    fin_comps = [c for c in synced_rocket.components if c.kind == "fins"]
    assert len(fin_comps) == 1
    assert fin_comps[0].count == 3
    assert fin_comps[0].position_m == pytest.approx(2.55)
    assert fin_comps[0].shape_points_m == synced_rocket.fins.shape_points_m
    assert fin_comps[0].thickness_m == pytest.approx(0.005)

    # Preset conversion + compose_simulation_config with in-memory rocket_spec.
    converted_preset = rocket_preset_from_spec(synced_rocket)
    assert converted_preset.name == synced_rocket.name
    custom_cfg = compose_simulation_config(rocket_spec=synced_rocket, repo_root=root)
    assert custom_cfg.mission.rocket == synced_rocket


def test_inspect_saved_motor_catalog_database_and_execution_audit_report(
    tmp_path: Path,
) -> None:
    from hefesto.domain import (
        CatalogDatabaseInspection,
        ExecutionAuditReport,
        PointMassComponent,
        SavedMotorInspection,
        SavedRocketInspection,
    )
    from hefesto.services import (
        build_execution_audit_report,
        inspect_catalog_database,
        inspect_saved_motor,
        inspect_saved_rocket,
        recalculate_rocket_structure,
    )

    root = _seed_isolated_workspace(tmp_path)

    # 1) inspect_saved_motor on .ric + .eng preset and .eng-only preset.
    ric_info = inspect_saved_motor(DEFAULT_MOTOR_ID, repo_root=root)
    assert isinstance(ric_info, SavedMotorInspection)
    assert ric_info.source_kind == "ric_and_eng"
    assert ric_info.motor_asset == "medusa_knsb_a.ric"
    assert len(ric_info.grains) == 6
    assert ric_info.casing_outer_diameter_m == pytest.approx(2.0 * ric_info.casing.outer_radius_m)

    eng_info = inspect_saved_motor("medusa_n3174", repo_root=root)
    assert eng_info.source_kind == "eng_only"
    assert eng_info.motor_asset is None
    assert eng_info.thrust_curve_asset == "medusa_n3174.eng"
    assert len(eng_info.grains) >= 1

    # 2) inspect_saved_rocket & inspect_catalog_database.
    rkt_info = inspect_saved_rocket(DEFAULT_ROCKET_ID, repo_root=root)
    assert isinstance(rkt_info, SavedRocketInspection)
    assert rkt_info.preset_id == DEFAULT_ROCKET_ID
    assert rkt_info.tube_count >= 1

    db = inspect_catalog_database(repo_root=root)
    assert isinstance(db, CatalogDatabaseInspection)
    assert any(m.preset_id == DEFAULT_MOTOR_ID for m in db.motors)
    assert any(r.preset_id == DEFAULT_ROCKET_ID for r in db.rockets)
    assert any(s.preset_id == DEFAULT_SITE_ID for s in db.sites)
    assert any(lim.preset_id == DEFAULT_LIMITS_ID for lim in db.limits)
    assert len(db.assets) == 15
    assert db.runs == ()

    # 3) ExecutionAuditReport comparing base .ric vs applied MotorOverride + edited rocket.
    base_rocket = load_rocket_spec(DEFAULT_ROCKET_ID, repo_root=root)
    edited_rocket = recalculate_rocket_structure(
        base_rocket.model_copy(
            update={
                "components": (
                    *base_rocket.components,
                    PointMassComponent(name="Audit Payload", mass_kg=0.35, position_m=1.2),
                )
            }
        )
    )
    cfg = compose_simulation_config(
        rocket_spec=edited_rocket,
        launch=LaunchConfig(terminate_on_apogee=True),
        motor_overrides=(
            MotorOverride(path="nozzle.throat", value=0.036),
            MotorOverride(path="grains.0.properties.length", value=0.14),
        ),
        output_selection=OutputSelection.none(),
        repo_root=root,
    )
    result = run_deterministic(cfg, repo_root=root)
    assert result.executed_config == cfg

    report = build_execution_audit_report(result, cfg, repo_root=root)
    assert isinstance(report, ExecutionAuditReport)
    assert report.motor_preset_id == DEFAULT_MOTOR_ID
    assert len(report.applied_overrides) == 2
    by_path = {ov.path: ov for ov in report.applied_overrides}
    assert by_path["nozzle.throat"].applied_value == pytest.approx(0.036)
    assert by_path["nozzle.throat"].base_value != pytest.approx(0.036)
    assert by_path["nozzle.throat"].changed is True
    assert by_path["grains.0.properties.length"].applied_value == pytest.approx(0.14)
    assert by_path["grains.0.properties.length"].changed is True
    assert report.rocket_modified_in_session is True
    assert any("Quantidade de componentes" in note for note in report.rocket_modification_notes)
    assert any(
        "nose_cone" in line and cfg.mission.rocket.nose_cone.name in line
        for line in report.components_summary
    )
    assert any("Audit Payload" in line and "0.350 kg" in line for line in report.components_summary)

    # 4) Full save_run_snapshot -> list -> load -> reconstruct ExecutionAuditReport from snapshot.
    saved = save_run_snapshot(result, repo_root=root)
    assert [s.run_id for s in list_run_snapshots(repo_root=root)] == [saved.run_id]
    loaded = load_run_snapshot(saved.run_id, repo_root=root)
    rebuilt = build_execution_audit_report(loaded, repo_root=root)
    assert rebuilt == report
    assert not (REPO_ROOT / "data" / "runs").exists()


def test_casing_length_update_survives_compose_and_updates_motor_summary(tmp_path: Path) -> None:
    from hefesto.services import (
        resolve_motor_for_simulation,
        summarize_motor_physical_metrics,
        update_rocket_motor_casing_length,
    )

    root = _seed_isolated_workspace(tmp_path)
    base_rocket = load_rocket_spec(DEFAULT_ROCKET_ID, repo_root=root)
    updated_rocket, resize_res = update_rocket_motor_casing_length(
        base_rocket,
        1.30,
        mode="tubular_delta",
        material_density_kg_m3=7850.0,
        motor_position_m=2.15,
    )
    assert updated_rocket.motor.casing.length_m == pytest.approx(1.30)
    assert updated_rocket.motor_position_m == pytest.approx(2.15)
    assert updated_rocket.motor.casing.dry_mass_kg == pytest.approx(resize_res.casing.dry_mass_kg)

    cfg = compose_simulation_config(
        rocket_spec=updated_rocket,
        motor_id=updated_rocket.motor.name,
        repo_root=root,
    )
    assert cfg.mission.rocket.motor.casing.length_m == pytest.approx(1.30)
    assert cfg.mission.rocket.motor.casing.dry_mass_kg == pytest.approx(
        resize_res.casing.dry_mass_kg
    )

    resolved_motor, _ = resolve_motor_for_simulation(cfg.mission.rocket.motor, repo_root=root)
    assert resolved_motor.casing.dry_mass_kg == pytest.approx(resize_res.casing.dry_mass_kg)

    summary = summarize_motor_physical_metrics(resolved_motor)
    assert summary.casing_length_m == pytest.approx(1.30)
    assert summary.dry_mass_kg == pytest.approx(resize_res.casing.dry_mass_kg)
    assert summary.total_loaded_mass_kg == pytest.approx(
        summary.dry_mass_kg + summary.propellant_mass_kg
    )
    assert summary.propellant_mass_fraction == pytest.approx(
        summary.propellant_mass_kg / summary.total_loaded_mass_kg
    )


def test_ork_parity_mission_runs_on_isa_without_touching_the_era5_netcdf() -> None:
    config = compose_simulation_config(
        mission_id="ork_parity", output_selection=OutputSelection.none()
    )
    mission = config.mission

    assert mission.launch.inclination_deg == pytest.approx(84.0)
    assert mission.launch.heading_deg == pytest.approx(270.0)
    assert mission.launch.rail_length_m == pytest.approx(6.48)
    assert mission.atmosphere is not None
    assert mission.atmosphere.type == "isa"
    assert mission.atmosphere.elevation_m == pytest.approx(1000.0)
    assert mission.atmosphere.base_temperature_k == pytest.approx(299.15)
    assert mission.atmosphere.base_pressure_pa == pytest.approx(91000.0)
    assert mission.atmosphere.wind_speed_ms == pytest.approx(5.2)
    assert mission.atmosphere.wind_direction_deg == pytest.approx(270.0)
    # Re-imported .ork design: shell on the nose spec, OpenRocket-like dry mass.
    assert mission.rocket.nose_cone.shell is not None
    assert mission.rocket.motor_position_m == pytest.approx(2.625)

    fast_config = config.model_copy(
        update={
            "mission": mission.model_copy(
                update={
                    "launch": LaunchConfig(
                        inclination_deg=84.0,
                        heading_deg=270.0,
                        rail_length_m=6.48,
                        max_time_s=60.0,
                        terminate_on_apogee=True,
                    )
                }
            )
        }
    )
    with patch(
        "hefesto.services.simulation_service.resolve_asset_path",
        side_effect=AssertionError("ISA missions must never resolve the ERA5 asset"),
    ):
        result = run_deterministic(fast_config, repo_root=REPO_ROOT)

    flight = result.flight
    assert flight.dry_mass_kg == pytest.approx(15.769610321481428, rel=1e-12)
    assert flight.apogee_msl_m == pytest.approx(flight.apogee_agl_m + 1000.0, rel=1e-12)
    # Analytical Cd(Mach) drives the flight: within 4.5% of OpenRocket's 3393.406 m AGL.
    assert 3393.406064 * 0.955 < flight.apogee_agl_m < 3393.406064 * 1.045
    assert flight.rail_exit_velocity_ms > 25.0
