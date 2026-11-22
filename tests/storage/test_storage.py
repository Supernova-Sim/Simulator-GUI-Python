"""TDD tests for Hefesto storage layer (paths, assets, parsers, catalog, runs)."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hefesto.domain import (
    AssetCategory,
    CatalogOverview,
    DragCurveSpec,
    EnvironmentSpec,
    Era5DatasetKind,
    FinComponent,
    FinSetSpec,
    FlightResult,
    GrainSpec,
    LaunchConfig,
    MissionPreset,
    MotorCasingSpec,
    MotorPreset,
    NoseConeSpec,
    NozzleSpec,
    ParachuteSpec,
    PointMassComponent,
    RailButtonsSpec,
    RocketPreset,
    RunSummary,
    SafetyLimits,
    SimulationResult,
    TubeComponent,
)
from hefesto.storage import (
    ASSET_EXTENSION_WHITELIST,
    AssetStore,
    CatalogStore,
    RunStore,
    StoragePaths,
    atomic_write_text,
    load_drag_curve,
    parse_csv_curve,
    parse_csv_text,
    parse_eng_file,
    parse_eng_text,
    resolve_safe_relative_path,
    resolve_storage_paths,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = REPO_ROOT / "tests" / "golden" / "hefesto_baseline.json"


def _trapezoid_integral(points: list[tuple[float, float]]) -> float:
    return sum(
        0.5 * (y0 + y1) * (x1 - x0)
        for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False)
    )


def _sample_motor_preset(name: str = "medusa_knsb_a") -> MotorPreset:
    return MotorPreset(
        name=name,
        motor_asset="medusa_knsb_a.ric",
        thrust_curve_asset="medusa_knsb_a.eng",
        casing=MotorCasingSpec(
            inner_radius_m=0.05395,
            wall_thickness_m=0.003175,
            length_m=1.10,
            internal_clearance_m=0.04,
            yield_strength_pa=145_000_000.0,
            dry_mass_kg=7.5,
            dry_inertia_kg_m2=(0.7678260027343752, 0.7678260027343752, 0.023152005468749997),
            center_of_dry_mass_m=0.55,
        ),
        grain_separation_m=0.01,
        grains_center_of_mass_m=0.5403902229538684,
        nozzle_position_m=0.016,
        propellant_name="Nakka - KNSB (2)",
        propellant_density_kg_m3=1841.0,
        fallback_grains=(
            *(
                GrainSpec(length_m=0.16, outer_radius_m=0.049345, inner_radius_m=0.0195)
                for _ in range(4)
            ),
            *(
                GrainSpec(length_m=0.16, outer_radius_m=0.049345, inner_radius_m=0.027)
                for _ in range(2)
            ),
        ),
        nozzle=NozzleSpec(
            throat_radius_m=0.017,
            exit_radius_m=0.039,
            position_m=0.016,
            throat_length_m=0.005,
            converging_angle_deg=45.0,
            diverging_angle_deg=15.0,
            efficiency=0.85,
        ),
        burn_time_s=(0.0, 3.9),
    )


def _sample_rocket_preset(name: str = "hefesto_v1") -> RocketPreset:
    return RocketPreset(
        name=name,
        radius_m=0.079,
        center_of_mass_without_motor_m=1.2333,
        inertia_kg_m2=(12.297744243637531, 12.297744243637531, 0.08243211389076663),
        motor_position_m=2.78,
        components=(
            TubeComponent(
                name="Propulsion Module",
                outer_radius_m=0.079,
                wall_thickness_m=0.002,
                length_m=0.91,
                density_kg_m3=1850.0,
                position_m=1.895,
            ),
            PointMassComponent(name="Avionics", mass_kg=0.7, position_m=0.701),
            FinComponent(
                name="Main Fins",
                count=4,
                shape_points_m=((0.0, 0.0), (0.07, 0.12), (0.21, 0.14), (0.18, 0.0)),
                thickness_m=0.004,
                density_kg_m3=2700.0,
                position_m=2.57,
            ),
        ),
        nose_cone=NoseConeSpec(length_m=0.45, position_m=0.0),
        fins=FinSetSpec(
            name="Main Fins",
            count=4,
            position_m=2.57,
            shape_points_m=((0.0, 0.0), (0.07, 0.12), (0.21, 0.14), (0.18, 0.0)),
        ),
        rail_buttons=RailButtonsSpec(
            upper_button_position_m=1.39,
            lower_button_position_m=2.30,
            angular_position_deg=45.0,
            radius_m=0.02,
        ),
        parachutes=(
            ParachuteSpec(name="reefed", cd_s_m2=0.85, trigger="apogee", lag_s=1.0, radius_m=0.6),
            ParachuteSpec(name="unreefed", cd_s_m2=1.5, trigger=450.0, lag_s=1.0, radius_m=1.9),
        ),
        power_off_drag_asset="power_off.csv",
        power_on_drag_asset="power_on.csv",
        motor_preset_name="medusa_knsb_a",
    )


def _sample_environment(asset: str = "irec_era5_oper.nc") -> EnvironmentSpec:
    return EnvironmentSpec(
        name="Spaceport America (IREC)",
        atmosphere_asset=asset,
        dataset_kind=Era5DatasetKind.OPER,
        date_utc=(2026, 6, 15, 12),
        latitude_deg=32.94019,
        longitude_deg=-106.92056,
        elevation_m=1401.0,
    )


def _sample_simulation_result(run_id: str, created_at_utc: datetime) -> SimulationResult:
    return SimulationResult(
        run_id=run_id,
        created_at_utc=created_at_utc,
        mission_name="irec_nominal_88deg",
        motor_name="Medusa KNSB A",
        flight=FlightResult(
            apogee_agl_m=3578.2,
            apogee_msl_m=4979.2,
            apogee_time_s=26.7,
            flight_time_s=168.7,
            max_speed_ms=305.8,
            max_mach=0.898,
            rail_exit_velocity_ms=27.05,
            min_static_margin_calibers=2.36,
            total_impulse_ns=11514.4,
            dry_mass_kg=18.85,
        ),
    )


def test_storage_paths_and_safe_path_resolution(tmp_path: Path) -> None:
    paths = resolve_storage_paths(tmp_path)
    assert isinstance(paths, StoragePaths)
    assert paths.repo_root == tmp_path.resolve()
    assert paths.data_dir == tmp_path.resolve() / "data"
    assert paths.assets_dir == tmp_path.resolve() / "data" / "assets"
    assert paths.catalog_dir == tmp_path.resolve() / "data" / "catalog"
    assert paths.runs_dir == tmp_path.resolve() / "data" / "runs"
    assert paths.asset_category_dir(AssetCategory.MOTORS) == paths.assets_dir / "motors"

    base = tmp_path / "sandbox"
    base.mkdir()
    safe_target = resolve_safe_relative_path(base, "sub/file.csv")
    assert safe_target == (base / "sub" / "file.csv").resolve()

    for bad_path in (
        "",
        "   ",
        ".",
        "..",
        "../outside.txt",
        "sub/../../outside.txt",
        r"..\outside.txt",
        "/etc/passwd",
        "C:\\windows\\system.ini",
        "bad\x00name.csv",
    ):
        with pytest.raises(ValueError):
            resolve_safe_relative_path(base, bad_path)

    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    symlink = base / "escape.txt"
    symlink.symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        resolve_safe_relative_path(base, "escape.txt")

    target_file = tmp_path / "nested" / "atomic.json"
    written = atomic_write_text(target_file, '{"ok": true}\n')
    assert written == target_file
    assert target_file.read_text(encoding="utf-8") == '{"ok": true}\n'
    assert [p.name for p in target_file.parent.iterdir()] == ["atomic.json"]


def test_asset_store_enforces_whitelist_anti_traversal_and_lists_real_assets(
    tmp_path: Path,
) -> None:
    # Real repository assets check
    real_store = AssetStore(resolve_storage_paths(REPO_ROOT))
    entries = real_store.list_assets()
    assert len(entries) == 14
    assert len(real_store.list_assets(AssetCategory.MOTORS)) == 7
    assert len(real_store.list_assets(AssetCategory.DRAG)) == 2
    assert len(real_store.list_assets(AssetCategory.ATMOSPHERE)) == 5
    assert real_store.resolve_asset(AssetCategory.MOTORS, "medusa_knsb_a.eng").is_file()
    assert real_store.resolve_asset(AssetCategory.MOTORS, "medusa_knsb_a.ric").is_file()
    assert real_store.resolve_asset(AssetCategory.DRAG, "power_off.csv").is_file()
    assert real_store.resolve_asset(AssetCategory.ATMOSPHERE, "irec_era5_oper.nc").is_file()

    # Extension whitelist & anti-traversal on isolated store
    paths = resolve_storage_paths(tmp_path)
    (paths.asset_category_dir(AssetCategory.MOTORS)).mkdir(parents=True)
    (paths.asset_category_dir(AssetCategory.DRAG)).mkdir(parents=True)
    (paths.asset_category_dir(AssetCategory.ATMOSPHERE)).mkdir(parents=True)
    (paths.asset_category_dir(AssetCategory.MOTORS) / "evil.yaml").write_text("a: 1\n", "utf-8")
    (paths.asset_category_dir(AssetCategory.ATMOSPHERE) / "isa.csv").write_text("0,1\n", "utf-8")
    (paths.asset_category_dir(AssetCategory.DRAG) / "note.txt").write_text("hi\n", "utf-8")
    outside_eng = tmp_path / "outside.eng"
    outside_eng.write_text("M 1 1 P 1 1\n0 0\n1 10\n", "utf-8")
    (paths.asset_category_dir(AssetCategory.MOTORS) / "link.eng").symlink_to(outside_eng)

    isolated = AssetStore(paths)
    assert ASSET_EXTENSION_WHITELIST[AssetCategory.ATMOSPHERE] == frozenset({".nc"})
    assert isolated.list_assets() == ()

    with pytest.raises(ValueError, match="extension"):
        isolated.resolve_asset(AssetCategory.MOTORS, "evil.yaml")
    with pytest.raises(ValueError, match="extension"):
        isolated.resolve_asset(AssetCategory.ATMOSPHERE, "isa.csv")
    with pytest.raises(ValueError, match="extension"):
        isolated.resolve_asset(AssetCategory.DRAG, "note.txt")
    with pytest.raises(ValueError):
        isolated.resolve_asset(AssetCategory.MOTORS, "../outside.eng")
    with pytest.raises(ValueError, match="escapes"):
        isolated.resolve_asset(AssetCategory.MOTORS, "link.eng")
    with pytest.raises(FileNotFoundError):
        isolated.resolve_asset(AssetCategory.MOTORS, "missing.eng")


def test_parse_eng_file_eliminates_first_point_nan_and_handles_all_repo_motors() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    store = AssetStore(resolve_storage_paths(REPO_ROOT))

    medusa_a = parse_eng_file(store.resolve_asset(AssetCategory.MOTORS, "medusa_knsb_a.eng"))
    assert medusa_a[0] == (0.0, 0.0)
    assert medusa_a[1] == pytest.approx((0.03, 3159.6675))
    assert all(math.isfinite(t) and math.isfinite(f) for t, f in medusa_a)
    assert all(t1 > t0 for (t0, _), (t1, _) in zip(medusa_a, medusa_a[1:], strict=False))
    assert _trapezoid_integral(medusa_a) == pytest.approx(
        golden["rocketpy_baseline_88deg"]["metrics"]["total_impulse_ns"], rel=1e-9
    )

    # medusa_n2792_v1.eng has a blank line after header, starts at t=0.03, and ends with ';'
    medusa_n2792 = parse_eng_file(store.resolve_asset(AssetCategory.MOTORS, "medusa_n2792_v1.eng"))
    assert medusa_n2792[0] == (0.0, 0.0)
    assert medusa_n2792[1] == pytest.approx((0.03, 3063.9315))
    assert medusa_n2792[-1] == pytest.approx((3.75, 0.0))
    assert _trapezoid_integral(medusa_n2792) == pytest.approx(
        golden["openmotor_baselines"]["medusa_n2792_v1"]["total_impulse_ns"], rel=1e-6
    )

    # medusa_n3002_v2.eng starts at (0, 0.01): must NOT duplicate t=0.0!
    medusa_n3002 = parse_eng_file(store.resolve_asset(AssetCategory.MOTORS, "medusa_n3002_v2.eng"))
    assert medusa_n3002[0] == pytest.approx((0.0, 0.01))
    assert medusa_n3002[1] == pytest.approx((0.03, 3210.4593))
    assert _trapezoid_integral(medusa_n3002) == pytest.approx(
        golden["openmotor_baselines"]["medusa_n3002_v2"]["total_impulse_ns"], rel=1e-5
    )

    medusa_n3174 = parse_eng_file(store.resolve_asset(AssetCategory.MOTORS, "medusa_n3174.eng"))
    assert medusa_n3174[0] == (0.0, 0.0)
    assert medusa_n3174[1] == pytest.approx((0.03, 3619.0619))
    assert medusa_n3174[-1] == pytest.approx((3.9, 0.0))

    # Leading comments & inline comments supported cleanly
    parsed_commented = parse_eng_text(
        "; RASP comment\n\nM100 50 500 0 1.0 2.0 Team\n\n0.1 500 ; ignition\n0.5 0.0\n"
    )
    assert parsed_commented == [(0.0, 0.0), (0.1, 500.0), (0.5, 0.0)]

    for bad_eng in (
        "",
        "0.0 0.0\n1.0 10.0\n",  # missing RASP header
        "M100 50 500 0 1.0 2.0 Team\n0.0 0.0\n0.0 10.0\n",  # duplicate t=0
        "M100 50 500 0 1.0 2.0 Team\n0.0 nan\n1.0 10.0\n",  # NaN thrust
        "M100 50 500 0 1.0 2.0 Team\n0.0 0.0\n0.5 10.0\n0.4 5.0\n",  # non-monotonic time
        "M100 50 500 0 1.0 2.0 Team\n0.0 -5.0\n1.0 10.0\n",  # negative thrust
        "M100 50 500 0 1.0 2.0 Team\n0.0 0.0\n",  # < 2 points
    ):
        with pytest.raises(ValueError):
            parse_eng_text(bad_eng)


def test_parse_csv_curve_handles_drag_assets_and_rejects_malformed_data() -> None:
    store = AssetStore(resolve_storage_paths(REPO_ROOT))
    power_off_path = store.resolve_asset(AssetCategory.DRAG, "power_off.csv")
    power_on_path = store.resolve_asset(AssetCategory.DRAG, "power_on.csv")

    pts_off = parse_csv_curve(power_off_path)
    pts_on = parse_csv_curve(power_on_path)
    assert len(pts_off) == 2500
    assert len(pts_on) == 2500
    assert pts_off[0] == pytest.approx((0.01, 0.453689802610909))
    assert pts_off[-1] == pytest.approx((25.0, 0.49949028596811))

    drag_spec = load_drag_curve(power_off_path, asset_name="power_off.csv")
    assert isinstance(drag_spec, DragCurveSpec)
    assert drag_spec.asset_name == "power_off.csv"
    assert len(drag_spec.points) == 2500

    with_header = parse_csv_text("# comment\nmach,cd\n\n0.0,0.45\n0.8,0.50\n1.2,0.85\n")
    assert with_header == [(0.0, 0.45), (0.8, 0.50), (1.2, 0.85)]

    for bad_csv in (
        "",
        "mach,cd\n0.0,0.5\n",
        "0.0,nan\n1.0,0.5\n",
        "0.0,0.5\n0.0,0.6\n",
        "0.0,-0.1\n1.0,0.5\n",
        "0.0,0.5,1.0\n1.0,0.5,2.0\n",
    ):
        with pytest.raises(ValueError):
            parse_csv_text(bad_csv)


def test_catalog_store_crud_overview_and_security_guards(tmp_path: Path) -> None:
    paths = resolve_storage_paths(tmp_path)
    (paths.asset_category_dir(AssetCategory.MOTORS)).mkdir(parents=True)
    (paths.asset_category_dir(AssetCategory.MOTORS) / "medusa_knsb_a.eng").write_text(
        "Medusa 100 1000 P 10 18 Test\n0 0\n1 100\n", encoding="utf-8"
    )

    store = CatalogStore(paths)
    motor = _sample_motor_preset()
    rocket = _sample_rocket_preset()
    site = _sample_environment()
    limits = SafetyLimits(max_kn=240.0)
    mission = MissionPreset(
        name="irec_nominal_88deg",
        rocket_preset_name="hefesto_v1",
        environment_preset_name="irec_oper",
        launch=LaunchConfig(),
        safety_limits=limits,
    )

    store.save_motor(motor)
    store.save_rocket(rocket)
    store.save_site(site, preset_id="irec_oper")
    store.save_limits(limits, preset_id="default")
    store.save_mission(mission)

    assert store.load_motor("medusa_knsb_a") == motor
    assert store.load_rocket("hefesto_v1") == rocket
    assert store.load_site("irec_oper") == site
    assert store.load_limits("default") == limits
    assert store.load_mission("irec_nominal_88deg") == mission

    overview = store.overview()
    assert isinstance(overview, CatalogOverview)
    assert overview.motor_presets == ("medusa_knsb_a",)
    assert overview.rocket_presets == ("hefesto_v1",)
    assert overview.environment_presets == ("irec_oper",)
    assert overview.mission_presets == ("irec_nominal_88deg",)
    assert len(overview.assets) == 1
    assert overview.assets[0].relative_path == "medusa_knsb_a.eng"

    # Extra fields in catalog JSON must fail validation (extra="forbid")
    bad_limits_file = paths.limits_catalog_dir / "bad.json"
    bad_limits_file.write_text('{"max_kn": 250.0, "unknown_field": 1}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        store.load_limits("bad")

    # Path traversal in preset IDs rejected
    with pytest.raises(ValueError):
        store.load_motor("../secret")
    with pytest.raises(FileNotFoundError):
        store.load_rocket("nonexistent")


def test_run_store_writes_atomically_on_demand_and_returns_run_summaries(
    tmp_path: Path,
) -> None:
    paths = resolve_storage_paths(tmp_path)
    run_store = RunStore(paths)

    # Instantiating RunStore must NOT create data/runs/ eagerly.
    assert not paths.runs_dir.exists()
    assert run_store.list_runs() == ()
    assert not paths.runs_dir.exists()

    older = _sample_simulation_result("run_20261122_001", datetime(2026, 11, 22, 4, 0, tzinfo=UTC))
    newer = _sample_simulation_result("run_20261122_002", datetime(2026, 11, 22, 5, 0, tzinfo=UTC))

    summary_older = run_store.save_run(older)
    summary_newer = run_store.save_run(newer)
    assert paths.runs_dir.is_dir()
    assert isinstance(summary_older, RunSummary)
    assert summary_older.snapshot_asset == "run_20261122_001.json"
    assert summary_newer.snapshot_asset == "run_20261122_002.json"

    assert run_store.load_run("run_20261122_001") == older
    summaries = run_store.list_runs()
    assert [s.run_id for s in summaries] == ["run_20261122_002", "run_20261122_001"]

    with pytest.raises(ValueError):
        run_store.load_run("../escape")
    with pytest.raises(FileNotFoundError):
        run_store.load_run("missing_run")


def test_repository_catalog_presets_exist_and_reference_only_relative_assets() -> None:
    paths = resolve_storage_paths(REPO_ROOT)
    asset_store = AssetStore(paths)
    catalog_store = CatalogStore(paths, asset_store=asset_store)

    overview = catalog_store.overview()
    assert "hefesto_v1" in overview.rocket_presets
    assert {"medusa_knsb_a", "medusa_n2792_v1", "medusa_n3002_v2", "medusa_n3174"} <= set(
        overview.motor_presets
    )
    assert {
        "irec_oper",
        "irec_enda",
        "irec_enda_grid",
        "iacanga_lasc_oper",
        "iacanga_lasc_enda",
    } <= set(overview.environment_presets)
    assert "default" in catalog_store.list_limits()

    # Check every rocket preset has valid relative drag assets and references an existing motor
    for rocket_id in overview.rocket_presets:
        rocket = catalog_store.load_rocket(rocket_id)
        assert asset_store.resolve_asset(AssetCategory.DRAG, rocket.power_off_drag_asset).is_file()
        assert asset_store.resolve_asset(AssetCategory.DRAG, rocket.power_on_drag_asset).is_file()
        assert rocket.motor_preset_name in overview.motor_presets

    # Check every motor preset resolves all declared relative motor/thrust assets
    for motor_id in overview.motor_presets:
        motor = catalog_store.load_motor(motor_id)
        if motor.motor_asset is not None:
            assert asset_store.resolve_asset(AssetCategory.MOTORS, motor.motor_asset).is_file()
        if motor.thrust_curve_asset is not None:
            thrust_path = asset_store.resolve_asset(AssetCategory.MOTORS, motor.thrust_curve_asset)
            assert thrust_path.is_file()
            points = parse_eng_file(thrust_path)
            assert len(points) >= 2

    # Check every site preset resolves a valid .nc asset (no ISA fallback)
    for site_id in overview.environment_presets:
        site = catalog_store.load_site(site_id)
        assert asset_store.resolve_asset(AssetCategory.ATMOSPHERE, site.atmosphere_asset).is_file()

    # Verify raw catalog JSON text contains zero absolute paths
    for json_file in paths.catalog_dir.rglob("*.json"):
        raw = json_file.read_text(encoding="utf-8")
        assert "/mnt/" not in raw
        assert "/home/" not in raw
        assert "data/assets" not in raw
        assert "data/entrada" not in raw

    # Verify default limits load cleanly
    default_limits = catalog_store.load_limits("default")
    assert default_limits == SafetyLimits()
