"""TDD tests for Hefesto pure domain models, DTOs, invariants, JSON, and pickle round-trips."""

from __future__ import annotations

import pickle
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from hefesto.domain import (
    AssetCategory,
    AssetEntry,
    BallisticsResult,
    CatalogOverview,
    DragCurveSpec,
    EnvironmentSpec,
    Era5DatasetKind,
    FinComponent,
    FinGeometryMode,
    FinSetSpec,
    FlightResult,
    GeometryValidationError,
    GrainInhibition,
    GrainSpec,
    LaunchConfig,
    MassMode,
    MissionPreset,
    MissionSpec,
    MotorCasingSpec,
    MotorOverride,
    MotorPreset,
    MotorSpec,
    NetCdfVariableMap,
    NoseConeKind,
    NoseConeSpec,
    NozzleSpec,
    OutputSelection,
    ParachuteSpec,
    PointMassComponent,
    RailButtonsSpec,
    RocketPreset,
    RocketSpec,
    RunSummary,
    SafetyCheck,
    SafetyCriterion,
    SafetyLimits,
    SafetyReport,
    SimulationConfig,
    SimulationResult,
    TubeComponent,
)


def _sample_tube() -> TubeComponent:
    return TubeComponent(
        name="Propulsion Module",
        outer_radius_m=0.079,
        wall_thickness_m=0.002,
        length_m=0.91,
        density_kg_m3=1850.0,
        position_m=1.895,
    )


def _sample_bulkhead() -> TubeComponent:
    return TubeComponent(
        name="Recovery Bulkhead",
        outer_radius_m=0.076,
        wall_thickness_m=0.076,
        length_m=0.012,
        density_kg_m3=2700.0,
        position_m=0.668,
    )


def _sample_point_mass() -> PointMassComponent:
    return PointMassComponent(
        name="Avionics",
        mass_kg=0.7,
        position_m=0.701,
    )


def _sample_fin_component() -> FinComponent:
    return FinComponent(
        name="Main Fins",
        count=4,
        shape_points_m=((0.0, 0.0), (0.07, 0.12), (0.21, 0.14), (0.18, 0.0)),
        thickness_m=0.004,
        density_kg_m3=2700.0,
        position_m=2.57,
    )


def _sample_grains() -> tuple[GrainSpec, ...]:
    return (
        *(
            GrainSpec(length_m=0.16, outer_radius_m=0.049345, inner_radius_m=0.0195)
            for _ in range(4)
        ),
        *(
            GrainSpec(length_m=0.16, outer_radius_m=0.049345, inner_radius_m=0.027)
            for _ in range(2)
        ),
    )


def _sample_nozzle() -> NozzleSpec:
    return NozzleSpec(
        throat_radius_m=0.017,
        exit_radius_m=0.039,
        position_m=0.016,
        throat_length_m=0.005,
        converging_angle_deg=45.0,
        diverging_angle_deg=15.0,
        efficiency=0.85,
    )


def _sample_casing() -> MotorCasingSpec:
    return MotorCasingSpec(
        inner_radius_m=0.05395,
        wall_thickness_m=0.003175,
        length_m=1.10,
        internal_clearance_m=0.04,
        yield_strength_pa=145_000_000.0,
        dry_mass_kg=7.5,
        dry_inertia_kg_m2=(0.7678260027343752, 0.7678260027343752, 0.023152005468749997),
        center_of_dry_mass_m=0.55,
    )


def _sample_motor() -> MotorSpec:
    return MotorSpec(
        name="Medusa KNSB A",
        grains=_sample_grains(),
        grain_separation_m=0.01,
        grains_center_of_mass_m=0.5403902229538684,
        propellant_name="Nakka - KNSB (2)",
        propellant_density_kg_m3=1841.0,
        nozzle=_sample_nozzle(),
        casing=_sample_casing(),
        burn_time_s=(0.0, 3.9),
        thrust_curve=((0.0, 0.0), (0.03, 3159.6675), (3.87, 1766.9398), (3.9, 0.0)),
        motor_asset="medusa_knsb_a.ric",
        thrust_curve_asset="medusa_knsb_a.eng",
    )


def _sample_nose() -> NoseConeSpec:
    return NoseConeSpec(
        length_m=0.45,
        kind=NoseConeKind.LV_HAACK,
        position_m=0.0,
        name="Nose Cone",
    )


def _sample_fins() -> FinSetSpec:
    return FinSetSpec(
        name="Main Fins",
        count=4,
        position_m=2.57,
        shape_points_m=((0.0, 0.0), (0.07, 0.12), (0.21, 0.14), (0.18, 0.0)),
        cant_angle_deg=0.0,
    )


def _sample_rail_buttons() -> RailButtonsSpec:
    return RailButtonsSpec(
        upper_button_position_m=1.39,
        lower_button_position_m=2.30,
        angular_position_deg=45.0,
        radius_m=0.02,
    )


def _sample_parachutes() -> tuple[ParachuteSpec, ...]:
    return (
        ParachuteSpec(name="reefed", cd_s_m2=0.85, trigger="apogee", lag_s=1.0, radius_m=0.6),
        ParachuteSpec(name="unreefed", cd_s_m2=1.5, trigger=450.0, lag_s=1.0, radius_m=1.9),
    )


def _sample_drag(asset_name: str) -> DragCurveSpec:
    return DragCurveSpec(
        asset_name=asset_name,
        points=((0.01, 0.4536898), (0.5, 0.48), (1.2, 0.85)),
    )


def _sample_rocket() -> RocketSpec:
    return RocketSpec(
        name="Hefesto V1",
        radius_m=0.079,
        center_of_mass_without_motor_m=1.2333,
        inertia_kg_m2=(12.297744243637531, 12.297744243637531, 0.08243211389076663),
        motor_position_m=2.78,
        components=(
            _sample_tube(),
            _sample_bulkhead(),
            _sample_point_mass(),
            _sample_fin_component(),
        ),
        nose_cone=_sample_nose(),
        fins=_sample_fins(),
        rail_buttons=_sample_rail_buttons(),
        parachutes=_sample_parachutes(),
        power_off_drag=_sample_drag("power_off.csv"),
        power_on_drag=_sample_drag("power_on.csv"),
        motor=_sample_motor(),
    )


def _sample_environment() -> EnvironmentSpec:
    return EnvironmentSpec(
        name="Spaceport America (IREC)",
        atmosphere_asset="irec_era5_oper.nc",
        dataset_kind=Era5DatasetKind.OPER,
        date_utc=(2026, 6, 15, 12),
        latitude_deg=32.94019,
        longitude_deg=-106.92056,
        elevation_m=1401.0,
    )


def _sample_safety_report() -> SafetyReport:
    limits = SafetyLimits()
    checks = (
        SafetyCheck(
            criterion=SafetyCriterion.CASE_SAFETY_FACTOR,
            name="Case safety factor",
            value=2.790298252502025,
            min_limit=limits.min_case_safety_factor,
            unit="",
            passed=True,
            detail="hoop_stress=51.97 MPa",
        ),
        SafetyCheck(
            criterion=SafetyCriterion.PEAK_CHAMBER_PRESSURE,
            name="Peak chamber pressure",
            value=3058226.56,
            max_limit=limits.max_chamber_pressure_pa,
            unit="Pa",
            passed=True,
            detail="within ceiling",
        ),
        SafetyCheck(
            criterion=SafetyCriterion.PEAK_KN,
            name="Peak Kn",
            value=244.5852064,
            max_limit=limits.max_kn,
            unit="",
            passed=True,
            detail="within ceiling",
        ),
        SafetyCheck(
            criterion=SafetyCriterion.PEAK_MASS_FLUX,
            name="Peak mass flux",
            value=1400.6633182,
            max_limit=limits.max_mass_flux_kg_m2_s,
            unit="kg/(m^2*s)",
            passed=True,
            detail="within ceiling",
        ),
        SafetyCheck(
            criterion=SafetyCriterion.PORT_TO_THROAT_RATIO,
            name="Aft port-to-throat ratio",
            value=2.52249135,
            min_limit=limits.min_port_to_throat_ratio,
            unit="",
            passed=True,
            detail="above minimum",
        ),
    )
    return SafetyReport(limits=limits, checks=checks, hoop_stress_pa=51_965_770.99597878)


def _sample_ballistics_result() -> BallisticsResult:
    return BallisticsResult(
        motor_name="Medusa KNSB A",
        grains=_sample_grains(),
        propellant_density_kg_m3=1841.0,
        throat_radius_m=0.017,
        nozzle_exit_radius_m=0.039,
        burn_time_s=(0.0, 3.8999999999999893),
        total_impulse_ns=11514.40619119084,
        max_thrust_n=3425.4490206754954,
        propellant_mass_kg=10.762788308893114,
        peak_chamber_pressure_pa=3058226.560004312,
        peak_kn=244.58520640319318,
        peak_mass_flux_kg_m2_s=1400.6633182068554,
        delivered_isp_s=109.09279583496946,
        aft_port_to_throat_ratio=2.5224913494809686,
        min_port_to_throat_ratio=1.315743944636678,
        thrust_curve=((0.0, 0.0), (0.03, 3159.6675), (3.9, 0.0)),
        pressure_curve=((0.0, 101325.0), (0.03, 2800000.0)),
        kn_curve=((0.0, 150.0), (0.03, 240.0)),
    )


def _sample_flight_result() -> FlightResult:
    return FlightResult(
        apogee_agl_m=3578.203646273967,
        apogee_msl_m=4979.203646273967,
        apogee_time_s=26.718324509230904,
        flight_time_s=168.74358250760554,
        max_speed_ms=305.8368305097546,
        max_mach=0.898553288997534,
        rail_exit_velocity_ms=27.05325152020802,
        min_static_margin_calibers=2.3617646744652694,
        max_static_margin_calibers=3.95,
        total_impulse_ns=11514.406191,
        dry_mass_kg=18.85049031412732,
        landing_velocity_ms=6.5,
        impact_distance_m=850.0,
        x_series=((0.0, 0.0), (26.7, 22.8)),
        y_series=((0.0, 0.0), (26.7, -28.8)),
        altitude_agl_series=((0.0, 0.0), (26.7, 3578.2)),
        speed_series=((0.0, 0.0), (3.9, 305.8)),
        vertical_velocity_series=((0.0, 0.0), (3.9, 290.0)),
        acceleration_series=((0.0, 0.0), (3.9, 85.0)),
        mach_series=((0.0, 0.0), (3.9, 0.898)),
        cg_series=((0.0, 1.72), (3.9, 1.52)),
        cp_series=((0.0, 2.11), (3.9, 2.14)),
        static_margin_series=((0.0, 2.36), (3.9, 3.10)),
        drag_series=((0.0, 0.0), (3.9, 145.0)),
        power_off_drag_curve=((0.0, 0.45), (0.9, 0.55)),
        power_on_drag_curve=((0.0, 0.41), (0.9, 0.50)),
        thrust_series=((0.0, 0.0), (1.0, 3200.0)),
    )


def _all_domain_instances() -> list[BaseModel]:
    launch = LaunchConfig()
    motor_preset = MotorPreset(
        name="medusa_knsb_a",
        motor_asset="medusa_knsb_a.ric",
        thrust_curve_asset="medusa_knsb_a.eng",
        casing=_sample_casing(),
        grain_separation_m=0.01,
        grains_center_of_mass_m=0.5403902229538684,
        nozzle_position_m=0.016,
        overrides=(MotorOverride(path="nozzle.throat", value=0.034),),
    )
    rocket_preset = RocketPreset(
        name="hefesto_v1",
        radius_m=0.079,
        center_of_mass_without_motor_m=1.2333,
        inertia_kg_m2=(12.297744243637531, 12.297744243637531, 0.08243211389076663),
        motor_position_m=2.78,
        components=(
            _sample_tube(),
            _sample_bulkhead(),
            _sample_point_mass(),
            _sample_fin_component(),
        ),
        nose_cone=_sample_nose(),
        fins=_sample_fins(),
        rail_buttons=_sample_rail_buttons(),
        parachutes=_sample_parachutes(),
        power_off_drag_asset="power_off.csv",
        power_on_drag_asset="power_on.csv",
        motor_preset_name="medusa_knsb_a",
    )
    mission_preset = MissionPreset(
        name="irec_nominal_88deg",
        rocket_preset_name="hefesto_v1",
        environment_preset_name="irec_oper",
        launch=launch,
        safety_limits=SafetyLimits(),
    )
    mission_spec = MissionSpec(
        name="irec_nominal_88deg",
        rocket=_sample_rocket(),
        environment=_sample_environment(),
        launch=launch,
        safety_limits=SafetyLimits(),
    )
    catalog_overview = CatalogOverview(
        assets=(
            AssetEntry(
                category=AssetCategory.MOTORS,
                relative_path="medusa_knsb_a.ric",
                name="medusa_knsb_a",
                file_format="ric",
            ),
            AssetEntry(
                category=AssetCategory.DRAG,
                relative_path="power_off.csv",
                name="power_off",
                file_format="csv",
            ),
            AssetEntry(
                category=AssetCategory.ATMOSPHERE,
                relative_path="irec_era5_oper.nc",
                name="irec_era5_oper",
                file_format="nc",
            ),
        ),
        motor_presets=("medusa_knsb_a",),
        rocket_presets=("hefesto_v1",),
        environment_presets=("irec_oper",),
        mission_presets=("irec_nominal_88deg",),
    )
    ballistics = _sample_ballistics_result()
    flight = _sample_flight_result()
    safety_report = _sample_safety_report()
    sim_result = SimulationResult(
        run_id="run_20261122_001",
        created_at_utc=datetime(2026, 11, 22, 5, 0, tzinfo=UTC),
        mission_name="irec_nominal_88deg",
        motor_name="Medusa KNSB A",
        flight=flight,
        ballistics=ballistics,
        safety=safety_report,
    )
    run_summary = sim_result.to_summary(snapshot_asset="run_20261122_001.json")
    output_selection = OutputSelection.all()
    sim_config = SimulationConfig(
        mission=mission_spec,
        mass_mode="calculated",
        fin_geometry_mode="freeform",
        drag_factor=1.05,
        thrust_factor=0.98,
        motor_overrides=(MotorOverride(path="nozzle.throat", value=0.034),),
        output_selection=output_selection,
    )

    return [
        _sample_tube(),
        _sample_bulkhead(),
        _sample_point_mass(),
        _sample_fin_component(),
        _sample_grains()[0],
        _sample_nozzle(),
        _sample_casing(),
        MotorOverride(path="nozzle.throat", value=0.034),
        _sample_motor(),
        _sample_nose(),
        _sample_fins(),
        _sample_rail_buttons(),
        _sample_parachutes()[0],
        _sample_drag("power_off.csv"),
        SafetyLimits(),
        safety_report.checks[0],
        SafetyCheck(
            criterion=SafetyCriterion.PEAK_KN,
            name="Peak Kn",
            value=None,
            max_limit=250.0,
            passed=False,
            detail="fail-closed invalid input",
        ),
        safety_report,
        _sample_rocket(),
        NetCdfVariableMap(),
        _sample_environment(),
        EnvironmentSpec(
            name="IREC ENDA",
            atmosphere_asset="irec_era5_enda.nc",
            dataset_kind=Era5DatasetKind.ENDA,
            ensemble_member=0,
            date_utc=(2026, 6, 15, 12),
            latitude_deg=32.94019,
            longitude_deg=-106.92056,
            elevation_m=1401.0,
        ),
        AssetEntry(
            category=AssetCategory.MOTORS,
            relative_path="medusa_knsb_a.ric",
            name="medusa_knsb_a",
            file_format="ric",
        ),
        motor_preset,
        rocket_preset,
        launch,
        mission_preset,
        mission_spec,
        output_selection,
        sim_config,
        catalog_overview,
        ballistics,
        flight,
        sim_result,
        run_summary,
    ]


def test_all_models_are_frozen_and_forbid_extra_fields() -> None:
    for model in _all_domain_instances():
        assert model.model_config.get("frozen") is True
        assert model.model_config.get("extra") == "forbid"

        cls = type(model)
        payload = model.model_dump()
        payload["unexpected_extra_field"] = "forbidden"
        with pytest.raises(ValidationError):
            cls.model_validate(payload)

        first_field = next(iter(cls.model_fields))
        with pytest.raises(ValidationError):
            setattr(model, first_field, getattr(model, first_field))


def test_all_models_and_dtos_support_json_and_pickle_roundtrip() -> None:
    for model in _all_domain_instances():
        cls = type(model)
        json_text = model.model_dump_json()
        from_json = cls.model_validate_json(json_text)
        assert from_json == model

        from_pickle = pickle.loads(pickle.dumps(model))
        assert from_pickle == model


def test_geometry_validation_error_is_domain_exception_and_picklable() -> None:
    err = GeometryValidationError("Grain stack 1.0500 m exceeds available casing 1.0000 m")
    assert isinstance(err, Exception)
    restored = pickle.loads(pickle.dumps(err))
    assert isinstance(restored, GeometryValidationError)
    assert str(restored) == str(err)


def test_motor_spec_allows_grain_casing_overflow_for_physics_guard() -> None:
    base_motor = _sample_motor()
    short_casing = base_motor.casing.model_dump() | {
        "length_m": 0.90,
        "internal_clearance_m": 0.0,
    }
    overflow_motor = MotorSpec.model_validate({**base_motor.model_dump(), "casing": short_casing})
    assert overflow_motor.grain_count == 6
    assert overflow_motor.grain_stack_length_m == pytest.approx(6 * 0.16 + 5 * 0.01)
    assert overflow_motor.grain_stack_length_m > overflow_motor.casing.available_grain_length_m

    tight_casing = base_motor.casing.model_dump() | {"inner_radius_m": 0.045}
    radial_overflow = MotorSpec.model_validate(
        {**base_motor.model_dump(), "casing": tight_casing}
    )
    assert radial_overflow.max_grain_outer_radius_m > radial_overflow.casing.inner_radius_m


def test_components_and_inertia_invariants() -> None:
    assert _sample_tube().inner_radius_m == pytest.approx(0.077)
    assert _sample_bulkhead().inner_radius_m == pytest.approx(0.0)
    assert _sample_casing().outer_radius_m == pytest.approx(0.057125)

    with pytest.raises(ValidationError):
        TubeComponent(
            name="Invalid Wall",
            outer_radius_m=0.05,
            wall_thickness_m=0.06,
            length_m=0.5,
            density_kg_m3=1850.0,
            position_m=0.5,
        )

    with pytest.raises(ValidationError):
        FinComponent(
            name="Degenerate",
            count=4,
            shape_points_m=((0.0, 0.0), (0.1, 0.1)),
            thickness_m=0.004,
            density_kg_m3=2700.0,
        )

    with pytest.raises(ValidationError):
        MotorCasingSpec(
            inner_radius_m=0.05,
            wall_thickness_m=0.003,
            length_m=1.0,
            internal_clearance_m=0.0,
            yield_strength_pa=145e6,
            dry_mass_kg=7.5,
            dry_inertia_kg_m2=(0.8, 0.7, 0.02),
            center_of_dry_mass_m=0.5,
        )

    rocket_payload = _sample_rocket().model_dump()
    with pytest.raises(ValidationError):
        RocketSpec.model_validate({**rocket_payload, "inertia_kg_m2": (12.0, 11.0, 0.08)})


def test_coordinate_systems_and_si_angles_are_enforced() -> None:
    rocket = _sample_rocket()
    motor = _sample_motor()
    assert rocket.coordinate_system == "nose_to_tail"
    assert motor.coordinate_system == "nozzle_to_combustion_chamber"

    with pytest.raises(ValidationError):
        RocketSpec.model_validate({**rocket.model_dump(), "coordinate_system": "tail_to_nose"})

    with pytest.raises(ValidationError):
        MotorSpec.model_validate(
            {**motor.model_dump(), "coordinate_system": "combustion_chamber_to_nozzle"}
        )

    with pytest.raises(ValidationError):
        RailButtonsSpec(
            upper_button_position_m=2.3,
            lower_button_position_m=1.39,
            angular_position_deg=45.0,
        )


def test_motor_validation_and_nan_inf_rejection() -> None:
    grain = GrainSpec.model_validate(
        {
            "length_m": 0.16,
            "outer_radius_m": 0.049345,
            "inner_radius_m": 0.0195,
            "inhibited_ends": "Neither",
        }
    )
    assert grain.inhibited_ends == GrainInhibition.NEITHER

    with pytest.raises(ValidationError):
        GrainSpec(length_m=0.16, outer_radius_m=0.04, inner_radius_m=0.04)

    with pytest.raises(ValidationError):
        NozzleSpec(throat_radius_m=0.04, exit_radius_m=0.02)

    with pytest.raises(ValidationError):
        PointMassComponent(name="NaN Mass", mass_kg=float("nan"), position_m=0.5)

    with pytest.raises(ValidationError):
        PointMassComponent(name="Inf Mass", mass_kg=float("inf"), position_m=0.5)

    motor_payload = _sample_motor().model_dump()
    with pytest.raises(ValidationError):
        MotorSpec.model_validate(
            {**motor_payload, "thrust_curve": ((0.0, 0.0), (1.0, 100.0), (0.5, 50.0))}
        )


def test_environment_nc_only_and_dataset_kind_rules() -> None:
    with pytest.raises(ValidationError):
        EnvironmentSpec(
            atmosphere_asset="standard_isa.csv",
            date_utc=(2026, 6, 15, 12),
            latitude_deg=32.94019,
            longitude_deg=-106.92056,
            elevation_m=1401.0,
        )

    with pytest.raises(ValidationError):
        EnvironmentSpec(
            atmosphere_asset="/abs/path/irec_era5_oper.nc",
            date_utc=(2026, 6, 15, 12),
            latitude_deg=32.94019,
            longitude_deg=-106.92056,
            elevation_m=1401.0,
        )

    with pytest.raises(ValidationError):
        EnvironmentSpec(
            atmosphere_asset="irec_era5_oper.nc",
            dataset_kind=Era5DatasetKind.OPER,
            ensemble_member=0,
            date_utc=(2026, 6, 15, 12),
            latitude_deg=32.94019,
            longitude_deg=-106.92056,
            elevation_m=1401.0,
        )

    enda_env = EnvironmentSpec(
        atmosphere_asset="irec_era5_enda.nc",
        dataset_kind=Era5DatasetKind.ENDA,
        ensemble_member=3,
        date_utc=(2026, 6, 15, 12),
        latitude_deg=32.94019,
        longitude_deg=-106.92056,
        elevation_m=1401.0,
    )
    assert enda_env.ensemble_member == 3

    with pytest.raises(ValidationError):
        EnvironmentSpec(
            atmosphere_asset="irec_era5_oper.nc",
            date_utc=(2026, 2, 30, 12),
            latitude_deg=32.94019,
            longitude_deg=-106.92056,
            elevation_m=1401.0,
        )


def test_safety_checks_fail_closed_and_require_all_five_criteria() -> None:
    with pytest.raises(ValidationError):
        SafetyCheck(
            criterion=SafetyCriterion.PEAK_KN,
            name="Peak Kn",
            value=None,
            max_limit=250.0,
            passed=True,
        )

    report = _sample_safety_report()
    assert report.all_passed is True
    assert len(report.checks) == 5

    with pytest.raises(ValidationError):
        SafetyReport(limits=report.limits, checks=report.checks[:4])

    duplicated = (*report.checks[:4], report.checks[0])
    with pytest.raises(ValidationError):
        SafetyReport(limits=report.limits, checks=duplicated)

    with pytest.raises(ValidationError):
        SafetyLimits(min_case_safety_factor=3.0, target_case_safety_factor=2.0)

    with pytest.raises(ValidationError):
        ParachuteSpec(name="bad_trigger", cd_s_m2=1.0, trigger=0.0)


def test_catalog_overview_and_relative_assets() -> None:
    with pytest.raises(ValidationError):
        AssetEntry(
            category=AssetCategory.MOTORS,
            relative_path="../escape.ric",
            name="escape",
            file_format="ric",
        )

    with pytest.raises(ValidationError):
        MotorPreset(
            name="empty_motor",
            casing=_sample_casing(),
            grain_separation_m=0.01,
            grains_center_of_mass_m=0.54,
        )

    overview = CatalogOverview(
        assets=(
            AssetEntry(
                category=AssetCategory.MOTORS,
                relative_path="medusa_knsb_a.ric",
                name="medusa_knsb_a",
                file_format="ric",
            ),
            AssetEntry(
                category=AssetCategory.DRAG,
                relative_path="power_off.csv",
                name="power_off",
                file_format="csv",
            ),
        ),
        motor_presets=("medusa_knsb_a",),
    )
    assert len(overview.assets_for(AssetCategory.MOTORS)) == 1
    assert overview.assets_for(AssetCategory.ATMOSPHERE) == ()


def test_run_summary_rejects_absolute_snapshot_path() -> None:
    with pytest.raises(ValidationError):
        RunSummary(
            run_id="run_1",
            created_at_utc=datetime(2026, 11, 22, 5, 0, tzinfo=UTC),
            mission_name="irec_nominal_88deg",
            motor_name="Medusa KNSB A",
            apogee_agl_m=3578.2,
            max_mach=0.898,
            min_static_margin_calibers=2.36,
            safety_passed=True,
            snapshot_asset="/tmp/abs.json",
        )


def test_simulation_config_mass_fin_modes_and_output_selection() -> None:
    mass_mode: MassMode = "calculated"
    fin_mode: FinGeometryMode = "trapezoidal"
    mission = MissionSpec(
        name="irec_nominal_88deg",
        rocket=_sample_rocket(),
        environment=_sample_environment(),
    )
    cfg = SimulationConfig(mission=mission, mass_mode=mass_mode, fin_geometry_mode=fin_mode)
    assert cfg.output_selection == OutputSelection.all()
    assert OutputSelection.none() == OutputSelection()
    assert SimulationConfig.model_validate_json(cfg.model_dump_json()) == cfg
    assert pickle.loads(pickle.dumps(cfg)) == cfg

    # Measured mass mode requires dry_mass_override_kg on rocket.
    with pytest.raises(ValidationError, match="dry_mass_override_kg"):
        SimulationConfig(mission=mission, mass_mode="measured")

    measured_rocket = mission.rocket.model_copy(update={"dry_mass_override_kg": 21.644})
    measured_cfg = SimulationConfig(
        mission=mission.model_copy(update={"rocket": measured_rocket}),
        mass_mode="measured",
    )
    assert measured_cfg.mission.rocket.dry_mass_override_kg == pytest.approx(21.644)

    with pytest.raises(ValidationError):
        SimulationConfig.model_validate({**cfg.model_dump(), "mass_mode": "invalid"})
    with pytest.raises(ValidationError):
        SimulationConfig.model_validate({**cfg.model_dump(), "fin_geometry_mode": "elliptical"})
    with pytest.raises(ValidationError):
        SimulationConfig(mission=mission, drag_factor=0.0)
    with pytest.raises(ValidationError):
        SimulationConfig(mission=mission, thrust_factor=-1.0)
