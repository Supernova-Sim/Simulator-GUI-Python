"""TDD tests for Hefesto physics constants, geometry guards, structure, and inertia."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from hefesto.domain import (
    DragCurveSpec,
    FinComponent,
    FinSetSpec,
    GeometryValidationError,
    GrainSpec,
    MotorCasingSpec,
    MotorSpec,
    NoseConeKind,
    NoseConeSpec,
    NozzleSpec,
    ParachuteSpec,
    PointMassComponent,
    RailButtonsSpec,
    RocketSpec,
    TubeComponent,
)
from hefesto.physics.constants import (
    ALUMINUM_DENSITY_KG_M3,
    COMPOSITE_DENSITY_KG_M3,
    DEFAULT_CASE_YIELD_STRENGTH_PA,
    DEFAULT_DERIVATIVE_STEP_M,
    DEFAULT_FIN_THICKNESS_M,
    DEFAULT_MAX_CHAMBER_PRESSURE_PA,
    DEFAULT_MAX_KN,
    DEFAULT_MAX_MASS_FLUX_KG_M2_S,
    DEFAULT_MIN_CASE_SAFETY_FACTOR,
    DEFAULT_MIN_PORT_TO_THROAT_RATIO,
    DEFAULT_NOSE_CONE_SLICES,
    DEFAULT_TARGET_CASE_SAFETY_FACTOR,
    DEFAULT_WALL_THICKNESS_M,
    INCHES_PER_METER,
    KNSB_PROPELLANT_DENSITY_KG_M3,
    MOTOR_COORDINATE_SYSTEM,
    PA_PER_MPA,
    ROCKET_COORDINATE_SYSTEM,
    STANDARD_GRAVITY_M_S2,
)
from hefesto.physics.geometry import (
    EffectiveGrainGeometry,
    PolygonProperties,
    RasaeroFinGeometry,
    compute_grain_stack_length,
    compute_polygon_properties,
    derive_effective_grain_geometry,
    fin_to_rasaero,
    hollow_cylinder_volume_m3,
    nose_cone_radius_at,
    nose_cone_slope_at,
    trapezoidal_fin_points_m,
    validate_grain_casing_dimensions,
    validate_grain_casing_fit,
)
from hefesto.physics.inertia import (
    InertiaContribution,
    compute_center_of_mass_m,
    compute_motor_casing_dry_inertia_kg_m2,
    compute_steiner_inertia_kg_m2,
    fin_set_inertia_kg_m2,
    hollow_cylinder_inertia_kg_m2,
    point_mass_inertia_kg_m2,
)
from hefesto.physics.structure import (
    ComponentMassProperties,
    MotorMassProperties,
    StructureSummary,
    ThrustCurveSummary,
    aggregate_structure,
    compute_grain_stack_cg_m,
    derive_component_properties,
    derive_dry_mass,
    derive_fin_component_properties,
    derive_motor_casing_properties,
    derive_nose_cone_properties,
    derive_point_mass_properties,
    derive_rocket_structure,
    derive_tube_properties,
    summarize_thrust_curve,
)

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "golden" / "hefesto_baseline.json"


def _medusa_grains() -> tuple[GrainSpec, ...]:
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


def _medusa_motor(
    *,
    casing_length_m: float = 1.10,
    internal_clearance_m: float = 0.04,
    casing_inner_radius_m: float = 0.05395,
    grain_separation_m: float = 0.01,
    grains: tuple[GrainSpec, ...] | None = None,
) -> MotorSpec:
    resolved_grains = _medusa_grains() if grains is None else grains
    return MotorSpec(
        name="Medusa KNSB A",
        grains=resolved_grains,
        grain_separation_m=grain_separation_m,
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
        motor_asset="medusa_knsb_a.ric",
        thrust_curve_asset="medusa_knsb_a.eng",
    )


def _hefesto_components(wall_thickness_m: float = 0.002) -> tuple[
    TubeComponent | PointMassComponent | FinComponent, ...
]:
    comp = COMPOSITE_DENSITY_KG_M3
    alu = ALUMINUM_DENSITY_KG_M3
    return (
        TubeComponent(
            name="Avionics Module",
            outer_radius_m=0.079,
            wall_thickness_m=wall_thickness_m,
            length_m=0.54,
            density_kg_m3=comp,
            position_m=0.72,
        ),
        TubeComponent(
            name="Payload Module",
            outer_radius_m=0.079,
            wall_thickness_m=wall_thickness_m,
            length_m=0.45,
            density_kg_m3=comp,
            position_m=1.215,
        ),
        TubeComponent(
            name="Propulsion Module",
            outer_radius_m=0.079,
            wall_thickness_m=wall_thickness_m,
            length_m=0.91,
            density_kg_m3=comp,
            position_m=1.895,
        ),
        TubeComponent(
            name="Fins Module",
            outer_radius_m=0.079,
            wall_thickness_m=wall_thickness_m,
            length_m=0.40,
            density_kg_m3=comp,
            position_m=2.55,
        ),
        TubeComponent(
            name="Avionics/Payload Coupler",
            outer_radius_m=0.076,
            wall_thickness_m=wall_thickness_m,
            length_m=0.20,
            density_kg_m3=alu,
            position_m=0.99,
        ),
        TubeComponent(
            name="Payload/Propulsion Coupler",
            outer_radius_m=0.076,
            wall_thickness_m=wall_thickness_m,
            length_m=0.20,
            density_kg_m3=alu,
            position_m=1.44,
        ),
        TubeComponent(
            name="Propulsion/Fins Coupler",
            outer_radius_m=0.076,
            wall_thickness_m=wall_thickness_m,
            length_m=0.20,
            density_kg_m3=alu,
            position_m=2.35,
        ),
        TubeComponent(
            name="Upper Retainer 1",
            outer_radius_m=0.073,
            wall_thickness_m=0.01,
            length_m=0.012,
            density_kg_m3=alu,
            position_m=0.94,
        ),
        TubeComponent(
            name="Lower Retainer 1",
            outer_radius_m=0.073,
            wall_thickness_m=0.01,
            length_m=0.012,
            density_kg_m3=alu,
            position_m=1.04,
        ),
        TubeComponent(
            name="Upper Retainer 2",
            outer_radius_m=0.073,
            wall_thickness_m=0.01,
            length_m=0.012,
            density_kg_m3=alu,
            position_m=1.39,
        ),
        TubeComponent(
            name="Lower Centering Ring 1",
            outer_radius_m=0.073,
            wall_thickness_m=0.0105,
            length_m=0.012,
            density_kg_m3=alu,
            position_m=2.30,
        ),
        TubeComponent(
            name="Upper Centering Ring 1",
            outer_radius_m=0.073,
            wall_thickness_m=0.0105,
            length_m=0.012,
            density_kg_m3=alu,
            position_m=2.40,
        ),
        TubeComponent(
            name="Upper Centering Ring 2",
            outer_radius_m=0.076,
            wall_thickness_m=0.019,
            length_m=0.015,
            density_kg_m3=alu,
            position_m=2.6225,
        ),
        TubeComponent(
            name="Middle Centering Ring 2",
            outer_radius_m=0.076,
            wall_thickness_m=0.019,
            length_m=0.015,
            density_kg_m3=alu,
            position_m=2.6625,
        ),
        TubeComponent(
            name="Lower Centering Ring 2",
            outer_radius_m=0.076,
            wall_thickness_m=0.019,
            length_m=0.015,
            density_kg_m3=alu,
            position_m=2.7025,
        ),
        TubeComponent(
            name="Recovery Bulkhead",
            outer_radius_m=0.076,
            wall_thickness_m=0.076,
            length_m=0.012,
            density_kg_m3=alu,
            position_m=0.668,
        ),
        TubeComponent(
            name="Lower Bulkhead",
            outer_radius_m=0.073,
            wall_thickness_m=0.073,
            length_m=0.020,
            density_kg_m3=alu,
            position_m=1.49,
        ),
        PointMassComponent(name="Unreefed Parachute", mass_kg=0.65, position_m=0.43),
        PointMassComponent(name="Reefed Parachute", mass_kg=0.65, position_m=0.43),
        PointMassComponent(name="Recovery System", mass_kg=1.767, position_m=0.63),
        PointMassComponent(name="Avionics", mass_kg=0.70, position_m=0.701),
        PointMassComponent(name="Payload", mass_kg=1.40, position_m=0.202),
        PointMassComponent(name="Ballast Mass", mass_kg=2.60, position_m=1.368),
        PointMassComponent(name="Rail Buttons Set", mass_kg=0.0476, position_m=1.845),
        PointMassComponent(name="Nose Cone Mass", mass_kg=1.30, position_m=0.283),
        FinComponent(
            name="Main Fins",
            count=4,
            shape_points_m=((0.0, 0.0), (0.07, 0.12), (0.21, 0.14), (0.18, 0.0)),
            thickness_m=DEFAULT_FIN_THICKNESS_M,
            density_kg_m3=alu,
            position_m=2.57,
        ),
    )


def _hefesto_rocket(*, wall_thickness_m: float = 0.002) -> RocketSpec:
    return RocketSpec(
        name="Hefesto V1",
        radius_m=0.079,
        center_of_mass_without_motor_m=1.2333,
        inertia_kg_m2=(12.297744243637531, 12.297744243637531, 0.08243211389076663),
        motor_position_m=2.78,
        components=_hefesto_components(wall_thickness_m=wall_thickness_m),
        nose_cone=NoseConeSpec(length_m=0.45, kind=NoseConeKind.LV_HAACK, position_m=0.0),
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
        power_off_drag=DragCurveSpec(asset_name="power_off.csv", points=((0.0, 0.45), (1.0, 0.8))),
        power_on_drag=DragCurveSpec(asset_name="power_on.csv", points=((0.0, 0.45), (1.0, 0.8))),
        motor=_medusa_motor(),
    )


def test_constants_match_si_and_engineering_defaults() -> None:
    assert INCHES_PER_METER == pytest.approx(1.0 / 0.0254)
    assert PA_PER_MPA == 1_000_000.0
    assert STANDARD_GRAVITY_M_S2 == pytest.approx(9.80665)
    assert DEFAULT_NOSE_CONE_SLICES == 200
    assert DEFAULT_DERIVATIVE_STEP_M == pytest.approx(1e-7)
    assert COMPOSITE_DENSITY_KG_M3 == pytest.approx(1850.0)
    assert ALUMINUM_DENSITY_KG_M3 == pytest.approx(2700.0)
    assert KNSB_PROPELLANT_DENSITY_KG_M3 == pytest.approx(1841.0)
    assert DEFAULT_WALL_THICKNESS_M == pytest.approx(0.002)
    assert DEFAULT_FIN_THICKNESS_M == pytest.approx(0.004)
    assert DEFAULT_CASE_YIELD_STRENGTH_PA == pytest.approx(145e6)
    assert DEFAULT_MIN_CASE_SAFETY_FACTOR == pytest.approx(2.0)
    assert DEFAULT_TARGET_CASE_SAFETY_FACTOR == pytest.approx(3.0)
    assert DEFAULT_MAX_CHAMBER_PRESSURE_PA == pytest.approx(8.0e6)
    assert DEFAULT_MAX_KN == pytest.approx(250.0)
    assert DEFAULT_MAX_MASS_FLUX_KG_M2_S == pytest.approx(1406.0)
    assert DEFAULT_MIN_PORT_TO_THROAT_RATIO == pytest.approx(2.0)
    assert ROCKET_COORDINATE_SYSTEM == "nose_to_tail"
    assert MOTOR_COORDINATE_SYSTEM == "nozzle_to_combustion_chamber"


def test_validate_grain_casing_fit_passes_nominal_and_exact_boundary() -> None:
    nominal = _medusa_motor()
    validate_grain_casing_fit(nominal)

    # Exact axial boundary (3 * 0.1 = 0.30000000000000004 in float) must not falsely overflow.
    exact_grains = tuple(
        GrainSpec(length_m=0.1, outer_radius_m=0.05, inner_radius_m=0.02) for _ in range(3)
    )
    exact_motor = _medusa_motor(
        grains=exact_grains,
        grain_separation_m=0.0,
        casing_length_m=0.34,
        internal_clearance_m=0.04,
        casing_inner_radius_m=0.05,
    )
    validate_grain_casing_fit(exact_motor)


def test_validate_grain_casing_fit_raises_blocking_error_on_axial_and_radial_overflow() -> None:
    # Axial overflow due to casing shorter than grain stack (1.01 m vs 1.00 m).
    short_casing_motor = _medusa_motor(casing_length_m=1.00, internal_clearance_m=0.0)
    with pytest.raises(GeometryValidationError, match="exceeds available casing"):
        validate_grain_casing_fit(short_casing_motor)

    # Axial overflow triggered by internal clearance reducing available length below 1.01 m.
    tight_clearance_motor = _medusa_motor(casing_length_m=1.10, internal_clearance_m=0.10)
    with pytest.raises(GeometryValidationError, match="exceeds available casing"):
        validate_grain_casing_fit(tight_clearance_motor)

    # Axial overflow triggered by grain separation.
    wide_gap_motor = _medusa_motor(
        casing_length_m=1.10,
        internal_clearance_m=0.04,
        grain_separation_m=0.03,
    )
    with pytest.raises(GeometryValidationError, match="exceeds available casing"):
        validate_grain_casing_fit(wide_gap_motor)

    # Radial overflow even if only one grain in the stack exceeds casing inner radius.
    mixed_grains = (
        *_medusa_grains()[:5],
        GrainSpec(length_m=0.16, outer_radius_m=0.055, inner_radius_m=0.027),
    )
    radial_overflow_motor = _medusa_motor(grains=mixed_grains, casing_inner_radius_m=0.05395)
    with pytest.raises(GeometryValidationError, match="exceeds casing inner radius"):
        validate_grain_casing_fit(radial_overflow_motor)

    with pytest.raises(GeometryValidationError):
        validate_grain_casing_dimensions(
            grains=_medusa_grains(),
            grain_separation_m=0.01,
            casing_length_m=1.05,
            casing_inner_radius_m=0.05395,
            internal_clearance_m=0.05,
        )


def test_tube_and_point_mass_derivations_match_exact_formulas() -> None:
    tube = TubeComponent(
        name="Propulsion Tube",
        outer_radius_m=0.079,
        wall_thickness_m=0.002,
        length_m=0.91,
        density_kg_m3=1850.0,
        position_m=1.895,
    )
    props = derive_tube_properties(tube, extra_mass_kg=0.25)
    r_e = 0.079
    r_i = 0.077
    expected_vol = math.pi * (r_e**2 - r_i**2) * 0.91
    expected_mass = expected_vol * 1850.0 + 0.25
    expected_ixx = 0.5 * expected_mass * (r_e**2 + r_i**2)
    expected_iyy = (expected_mass / 12.0) * (3.0 * (r_e**2 + r_i**2) + 0.91**2)

    assert isinstance(props, ComponentMassProperties)
    assert hollow_cylinder_volume_m3(r_e, r_i, 0.91) == pytest.approx(expected_vol)
    assert props.mass_kg == pytest.approx(expected_mass)
    assert props.cg_m == pytest.approx(1.895)
    assert props.i_longitudinal_local_kg_m2 == pytest.approx(expected_ixx)
    assert props.i_transverse_local_kg_m2 == pytest.approx(expected_iyy)

    pm = PointMassComponent(name="Avionics", mass_kg=0.7, position_m=0.701)
    pm_default = derive_point_mass_properties(pm)
    assert pm_default.mass_kg == pytest.approx(0.7)
    assert pm_default.cg_m == pytest.approx(0.701)
    assert pm_default.i_longitudinal_local_kg_m2 == 0.0
    assert pm_default.i_transverse_local_kg_m2 == 0.0

    pm_cyl = derive_point_mass_properties(pm, equivalent_radius_m=0.05, length_m=0.2)
    assert pm_cyl.i_longitudinal_local_kg_m2 == pytest.approx(0.5 * 0.7 * 0.05**2)
    assert pm_cyl.i_transverse_local_kg_m2 == pytest.approx(
        (0.7 / 12.0) * (3.0 * 0.05**2 + 0.2**2)
    )
    assert point_mass_inertia_kg_m2(0.7, 0.05, 0.2) == pytest.approx(
        (pm_cyl.i_transverse_local_kg_m2, pm_cyl.i_longitudinal_local_kg_m2)
    )


def test_nose_cone_midpoint_integration_matches_conical_analytical_and_profiles() -> None:
    length = 0.45
    radius = 0.079
    thickness = 0.003
    density = 1850.0
    conical_spec = NoseConeSpec(length_m=length, kind=NoseConeKind.CONICAL, position_m=0.0)
    derived = derive_nose_cone_properties(
        conical_spec,
        wall_thickness_m=thickness,
        density_kg_m3=density,
        base_radius_m=radius,
        slices=DEFAULT_NOSE_CONE_SLICES,
    )

    slant = math.hypot(length, radius)
    analytical_mass = math.pi * radius * slant * thickness * density
    analytical_cg = (2.0 / 3.0) * length
    analytical_ixx = 0.5 * analytical_mass * radius**2
    analytical_iyy = analytical_mass * ((length**2) / 18.0 + (radius**2) / 4.0)

    assert derived.mass_kg == pytest.approx(analytical_mass, rel=1e-4)
    assert derived.cg_m == pytest.approx(analytical_cg, rel=1e-4)
    assert derived.i_longitudinal_local_kg_m2 == pytest.approx(analytical_ixx, rel=1e-4)
    assert derived.i_transverse_local_kg_m2 == pytest.approx(analytical_iyy, rel=1e-4)

    # Extra ballast mass shifts CG and i_transverse_local, NOT i_longitudinal_local.
    ballast_spec = NoseConeSpec(
        length_m=length,
        kind=NoseConeKind.LV_HAACK,
        position_m=0.10,
        base_radius_m=radius,
    )
    no_ballast = derive_nose_cone_properties(
        ballast_spec,
        wall_thickness_m=thickness,
        density_kg_m3=density,
    )
    with_ballast = derive_nose_cone_properties(
        ballast_spec,
        wall_thickness_m=thickness,
        density_kg_m3=density,
        extra_mass_kg=0.5,
        extra_mass_position_m=0.05,
    )
    assert with_ballast.mass_kg == pytest.approx(no_ballast.mass_kg + 0.5)
    assert with_ballast.i_longitudinal_local_kg_m2 == pytest.approx(
        no_ballast.i_longitudinal_local_kg_m2
    )
    assert with_ballast.cg_m < no_ballast.cg_m
    assert with_ballast.i_transverse_local_kg_m2 > no_ballast.i_transverse_local_kg_m2

    # Check ogive and lvhaack boundary radii and positive slopes.
    for kind in (NoseConeKind.CONICAL, NoseConeKind.LV_HAACK, NoseConeKind.OGIVE):
        assert nose_cone_radius_at(0.0, length, radius, kind) == pytest.approx(0.0, abs=1e-12)
        assert nose_cone_radius_at(length, length, radius, kind) == pytest.approx(radius)
        assert nose_cone_slope_at(0.5 * length, length, radius, kind) > 0.0
    assert DEFAULT_DERIVATIVE_STEP_M == pytest.approx(1e-7)


def test_shoelace_polygon_fin_properties_and_rasaero_conversion() -> None:
    # Rectangle [0, 2] x [0, 3]: area=6, centroid=(1, 1.5), winding-order invariant.
    ccw = ((0.0, 0.0), (2.0, 0.0), (2.0, 3.0), (0.0, 3.0))
    cw = tuple(reversed(ccw))
    poly_ccw = compute_polygon_properties(ccw)
    poly_cw = compute_polygon_properties(cw)
    assert isinstance(poly_ccw, PolygonProperties)
    assert poly_ccw.area_m2 == pytest.approx(6.0)
    assert poly_ccw.centroid_x_m == pytest.approx(1.0)
    assert poly_ccw.centroid_y_m == pytest.approx(1.5)
    assert poly_cw.area_m2 == pytest.approx(poly_ccw.area_m2)
    assert poly_cw.centroid_x_m == pytest.approx(poly_ccw.centroid_x_m)
    assert poly_cw.centroid_y_m == pytest.approx(poly_ccw.centroid_y_m)

    # Collinear points must raise GeometryValidationError.
    with pytest.raises(GeometryValidationError):
        compute_polygon_properties(((0.0, 0.0), (1.0, 0.0), (2.0, 0.0)))

    # Hefesto fin set derivation.
    fin_comp = FinComponent(
        name="Main Fins",
        count=4,
        shape_points_m=((0.0, 0.0), (0.07, 0.12), (0.21, 0.14), (0.18, 0.0)),
        thickness_m=0.004,
        density_kg_m3=2700.0,
        position_m=2.57,
    )
    fin_props = derive_fin_component_properties(fin_comp, rocket_radius_m=0.079)
    poly = compute_polygon_properties(fin_comp.shape_points_m)
    expected_mass = 4 * poly.area_m2 * 0.004 * 2700.0
    r_c = 0.079 + poly.centroid_y_m
    assert fin_props.mass_kg == pytest.approx(expected_mass)
    assert fin_props.cg_m == pytest.approx(2.57 + poly.centroid_x_m)
    assert fin_props.i_longitudinal_local_kg_m2 == pytest.approx(expected_mass * r_c**2)
    assert fin_props.i_transverse_local_kg_m2 == pytest.approx(0.5 * expected_mass * r_c**2)
    assert fin_set_inertia_kg_m2(expected_mass, r_c) == pytest.approx(
        (fin_props.i_transverse_local_kg_m2, fin_props.i_longitudinal_local_kg_m2)
    )

    # Trapezoidal polygon builder & RASAero conversion.
    trap = trapezoidal_fin_points_m(
        root_chord_m=0.20,
        tip_chord_m=0.10,
        sweep_length_m=0.05,
        span_le_m=0.12,
        span_te_m=0.14,
    )
    assert trap == ((0.0, 0.0), (0.05, 0.12), (0.15000000000000002, 0.14), (0.20, 0.0))
    for mode, expected_span_m in (("le", 0.12), ("te", 0.14), ("mean", 0.13)):
        rasaero = fin_to_rasaero(
            root_chord_m=0.20,
            tip_chord_m=0.10,
            sweep_length_m=0.05,
            span_le_m=0.12,
            span_te_m=0.14,
            span_mode=mode,
        )
        assert isinstance(rasaero, RasaeroFinGeometry)
        assert rasaero.root_chord_in == pytest.approx(0.20 * INCHES_PER_METER)
        assert rasaero.tip_chord_in == pytest.approx(0.10 * INCHES_PER_METER)
        assert rasaero.sweep_distance_in == pytest.approx(0.05 * INCHES_PER_METER)
        assert rasaero.span_in == pytest.approx(expected_span_m * INCHES_PER_METER)


def test_steiner_theorem_and_rocket_dry_mass_match_golden_baseline() -> None:
    # Split a uniform hollow tube in two halves and confirm Steiner gives identical inertia.
    full = TubeComponent(
        name="Full Tube",
        outer_radius_m=0.08,
        wall_thickness_m=0.004,
        length_m=1.0,
        density_kg_m3=1850.0,
        position_m=1.5,
    )
    half_a = TubeComponent(
        name="Half A",
        outer_radius_m=0.08,
        wall_thickness_m=0.004,
        length_m=0.5,
        density_kg_m3=1850.0,
        position_m=1.25,
    )
    half_b = TubeComponent(
        name="Half B",
        outer_radius_m=0.08,
        wall_thickness_m=0.004,
        length_m=0.5,
        density_kg_m3=1850.0,
        position_m=1.75,
    )
    full_props = derive_tube_properties(full)
    split_summary = aggregate_structure(
        [derive_tube_properties(half_a), derive_tube_properties(half_b)]
    )
    assert isinstance(split_summary, StructureSummary)
    assert split_summary.dry_mass_kg == pytest.approx(full_props.mass_kg)
    assert split_summary.center_of_mass_m == pytest.approx(1.5)
    assert split_summary.inertia_kg_m2 == pytest.approx(
        (
            full_props.i_transverse_local_kg_m2,
            full_props.i_transverse_local_kg_m2,
            full_props.i_longitudinal_local_kg_m2,
        )
    )

    # Check direct Steiner helper with explicit InertiaContribution list.
    contributions = [
        InertiaContribution("m1", 2.0, 1.0, 0.1, 0.02),
        InertiaContribution("m2", 2.0, 3.0, 0.3, 0.04),
    ]
    assert compute_center_of_mass_m(contributions) == pytest.approx(2.0)
    i_t, i_t2, i_l = compute_steiner_inertia_kg_m2(contributions)
    assert i_t == i_t2 == pytest.approx(0.1 + 2.0 * 1.0**2 + 0.3 + 2.0 * 1.0**2)
    assert i_l == pytest.approx(0.06)

    # Golden baseline dry mass check (2 mm and 3 mm wall thickness).
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    rocket_2mm = _hefesto_rocket(wall_thickness_m=0.002)
    rocket_3mm = _hefesto_rocket(wall_thickness_m=0.003)
    assert derive_dry_mass(rocket_2mm) == pytest.approx(
        golden["dry_mass"]["wall_2mm_kg"], rel=1e-12
    )
    assert derive_dry_mass(rocket_3mm) == pytest.approx(
        golden["dry_mass"]["wall_3mm_kg"], rel=1e-12
    )

    # Override dry mass takes precedence over component sum.
    overridden = RocketSpec.model_validate(
        {**rocket_2mm.model_dump(), "dry_mass_override_kg": 20.5}
    )
    assert derive_dry_mass(overridden) == pytest.approx(20.5)

    # Full structure summary has axisymmetric (I_t, I_t, I_l) and matches component dispatch.
    summary = derive_rocket_structure(rocket_2mm)
    assert summary.dry_mass_kg == pytest.approx(golden["dry_mass"]["wall_2mm_kg"], rel=1e-12)
    assert summary.inertia_kg_m2[0] == pytest.approx(summary.inertia_kg_m2[1])
    assert summary.inertia_kg_m2[0] > summary.inertia_kg_m2[2] > 0.0
    assert derive_component_properties(rocket_2mm.components[0], rocket_2mm.radius_m).mass_kg > 0.0


def test_motor_effective_grain_casing_dry_inertia_and_thrust_summary_match_golden() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    grains = _medusa_grains()

    assert compute_grain_stack_length(grains, 0.01) == pytest.approx(1.01)
    effective = derive_effective_grain_geometry(grains, grain_separation_m=0.01)
    assert isinstance(effective, EffectiveGrainGeometry)
    assert effective.grain_count == 6
    assert effective.total_propellant_length_m == pytest.approx(0.96)
    assert effective.stack_length_m == pytest.approx(1.01)
    assert effective.effective_height_m == pytest.approx(0.16)
    assert effective.effective_outer_radius_m == pytest.approx(0.049345)
    assert effective.effective_inner_radius_m == pytest.approx(0.02228227995515719, rel=1e-12)

    # Grain CG in forward-to-nozzle coordinates (start_offset = margin_forward_side = 0.075)
    # converts in nozzle_to_combustion_chamber to case_length - cg_from_forward.
    cg_from_forward = compute_grain_stack_cg_m(
        grains,
        grain_separation_m=0.01,
        propellant_density_kg_m3=1841.0,
        start_offset_m=0.075,
    )
    assert 1.10 - cg_from_forward == pytest.approx(
        golden["rocketpy_baseline_88deg"]["inputs"]["grains_center_of_mass_m"], rel=1e-12
    )

    # Casing hollow cylinder dry inertia matches Medusa golden motor inertia bit-for-bit.
    i_t, i_l = hollow_cylinder_inertia_kg_m2(
        mass_kg=7.5,
        outer_radius_m=0.05395 + 0.003175,
        inner_radius_m=0.05395,
        length_m=1.10,
    )
    expected_motor_inertia = tuple(
        golden["rocketpy_baseline_88deg"]["inputs"]["motor_dry_inertia_kg_m2"]
    )
    assert (i_t, i_t, i_l) == pytest.approx(expected_motor_inertia, rel=1e-12)
    assert compute_motor_casing_dry_inertia_kg_m2(
        dry_mass_kg=7.5,
        inner_radius_m=0.05395,
        wall_thickness_m=0.003175,
        length_m=1.10,
    ) == pytest.approx(expected_motor_inertia, rel=1e-12)

    motor_props = derive_motor_casing_properties(
        grains=grains,
        grain_separation_m=0.01,
        propellant_density_kg_m3=1841.0,
        case_inner_radius_m=0.05395,
        case_wall_thickness_m=0.003175,
        margin_forward_side_m=0.075,
        margin_nozzle_side_m=0.015,
        dry_mass_override_kg=7.5,
        coordinate_order="forward_to_nozzle",
    )
    assert isinstance(motor_props, MotorMassProperties)
    assert motor_props.case_length_m == pytest.approx(1.10)
    assert motor_props.case_outer_radius_m == pytest.approx(0.05395 + 0.003175)
    assert motor_props.propellant_mass_kg == pytest.approx(
        golden["openmotor_baselines"]["medusa_knsb_a"]["propellant_mass_kg"], rel=1e-12
    )
    assert motor_props.dry_mass_kg == pytest.approx(7.5)
    assert motor_props.loaded_mass_kg == pytest.approx(7.5 + motor_props.propellant_mass_kg)
    assert motor_props.center_of_dry_mass_m == pytest.approx(0.55)
    assert motor_props.grains_center_of_mass_m == pytest.approx(
        golden["rocketpy_baseline_88deg"]["inputs"]["grains_center_of_mass_m"], rel=1e-12
    )
    assert motor_props.dry_inertia_kg_m2 == pytest.approx(expected_motor_inertia, rel=1e-12)

    # Parametric casing dry mass from dimensions (without override).
    parametric_motor = derive_motor_casing_properties(
        grains=grains,
        grain_separation_m=0.01,
        propellant_density_kg_m3=1841.0,
        case_inner_radius_m=0.05395,
        case_wall_thickness_m=0.003175,
        case_length_m=1.10,
        internal_clearance_m=0.04,
        case_density_kg_m3=2700.0,
        nozzle_mass_kg=0.8,
        dry_mass_extra_kg=0.2,
    )
    r_o = 0.05395 + 0.003175
    expected_shell_mass = math.pi * (r_o**2 - 0.05395**2) * 1.10 * 2700.0 + 0.8 + 0.2
    assert parametric_motor.dry_mass_kg == pytest.approx(expected_shell_mass)

    # Overflow inside derive_motor_casing_properties must also raise GeometryValidationError.
    with pytest.raises(GeometryValidationError):
        derive_motor_casing_properties(
            grains=grains,
            grain_separation_m=0.01,
            propellant_density_kg_m3=1841.0,
            case_inner_radius_m=0.05395,
            case_wall_thickness_m=0.003175,
            case_length_m=1.00,
        )

    # Thrust curve trapezoidal integration summary.
    curve = ((0.0, 0.0), (1.0, 1000.0), (3.0, 1000.0), (4.0, 0.0))
    summary = summarize_thrust_curve(curve)
    assert isinstance(summary, ThrustCurveSummary)
    assert summary.total_impulse_ns == pytest.approx(3000.0)
    assert summary.burn_time_s == pytest.approx((0.0, 4.0))
    assert summary.max_thrust_n == pytest.approx(1000.0)


def test_edge_cases_and_validation_guards() -> None:
    # Nose cone edge cases: powerseries, Von Karman, missing radius, out-of-bounds x, zero wall.
    ps_spec = NoseConeSpec(
        length_m=0.40, kind=NoseConeKind.POWERSERIES, power=0.5, base_radius_m=0.05
    )
    assert nose_cone_radius_at(0.10, 0.40, 0.05, NoseConeKind.POWERSERIES, power=0.5) == (
        pytest.approx(0.025)
    )
    assert nose_cone_radius_at(0.20, 0.40, 0.05, NoseConeKind.VON_KARMAN) == pytest.approx(
        nose_cone_radius_at(0.20, 0.40, 0.05, NoseConeKind.LV_HAACK)
    )
    ps_props = derive_nose_cone_properties(ps_spec, wall_thickness_m=0.002, density_kg_m3=1850.0)
    assert ps_props.mass_kg > 0.0

    zero_wall = derive_nose_cone_properties(
        NoseConeSpec(length_m=0.40, kind=NoseConeKind.CONICAL, position_m=0.25, base_radius_m=0.05),
        wall_thickness_m=0.0,
        density_kg_m3=1850.0,
    )
    assert zero_wall.mass_kg == 0.0
    assert zero_wall.cg_m == pytest.approx(0.25)

    with pytest.raises(GeometryValidationError):
        derive_nose_cone_properties(
            NoseConeSpec(length_m=0.40, kind=NoseConeKind.CONICAL),
            wall_thickness_m=0.002,
            density_kg_m3=1850.0,
        )
    with pytest.raises(GeometryValidationError):
        nose_cone_radius_at(0.50, 0.40, 0.05, NoseConeKind.CONICAL)
    with pytest.raises(GeometryValidationError):
        nose_cone_radius_at(0.20, 0.40, 0.05, NoseConeKind.POWERSERIES, power=None)
    with pytest.raises(GeometryValidationError):
        nose_cone_radius_at(0.20, 0.40, 0.05, "elliptical")

    # Off-CG Steiner shift and motor inertia override validation.
    items = [InertiaContribution("body", 10.0, 1.0, 2.0, 0.1)]
    shifted = compute_steiner_inertia_kg_m2(items, reference_cg_m=2.5)
    assert shifted == pytest.approx((2.0 + 10.0 * 1.5**2, 2.0 + 10.0 * 1.5**2, 0.1))

    assert compute_motor_casing_dry_inertia_kg_m2(
        7.5, 0.05, 0.003, 1.0, override_inertia_kg_m2=(0.8, 0.8, 0.02)
    ) == (0.8, 0.8, 0.02)
    with pytest.raises(ValueError):
        compute_motor_casing_dry_inertia_kg_m2(
            7.5, 0.05, 0.003, 1.0, override_inertia_kg_m2=(0.8, 0.7, 0.02)
        )

    # Rocket structure aggregation with explicit nose cone shell component.
    rocket = _hefesto_rocket()
    nose_shell = derive_nose_cone_properties(
        rocket.nose_cone,
        wall_thickness_m=0.002,
        density_kg_m3=1850.0,
        base_radius_m=rocket.radius_m,
    )
    with_nose = derive_rocket_structure(rocket, nose_cone=nose_shell)
    without_nose = derive_rocket_structure(rocket)
    assert with_nose.dry_mass_kg == pytest.approx(without_nose.dry_mass_kg + nose_shell.mass_kg)

    # Motor casing CG in nozzle_to_combustion_chamber grain order.
    reversed_grains = tuple(reversed(_medusa_grains()))
    nozzle_ordered = derive_motor_casing_properties(
        grains=reversed_grains,
        grain_separation_m=0.01,
        propellant_density_kg_m3=1841.0,
        case_inner_radius_m=0.05395,
        case_wall_thickness_m=0.003175,
        margin_forward_side_m=0.075,
        margin_nozzle_side_m=0.015,
        dry_mass_override_kg=7.5,
        coordinate_order="nozzle_to_combustion_chamber",
    )
    assert nozzle_ordered.grains_center_of_mass_m == pytest.approx(0.5403902229538684, rel=1e-12)

    # Invalid thrust curves raise ValueError.
    with pytest.raises(ValueError):
        summarize_thrust_curve(((0.0, 0.0),))
    with pytest.raises(ValueError):
        summarize_thrust_curve(((0.0, 0.0), (1.0, 100.0), (0.5, 50.0)))
    with pytest.raises(ValueError):
        summarize_thrust_curve(((0.0, -5.0), (1.0, 100.0)))


def test_derive_rocket_structure_counts_imported_nose_shell_exactly_once() -> None:
    rocket = _hefesto_rocket()
    baseline = derive_rocket_structure(rocket)
    assert rocket.nose_cone.shell is None

    shell = PointMassComponent(name="Nose Shell", mass_kg=0.5442113886585497, position_m=0.2777)
    with_shell = rocket.model_copy(
        update={"nose_cone": rocket.nose_cone.model_copy(update={"shell": shell})}
    )
    structure = derive_rocket_structure(with_shell)

    assert structure.dry_mass_kg == pytest.approx(baseline.dry_mass_kg + shell.mass_kg, rel=1e-12)
    assert derive_dry_mass(with_shell) == pytest.approx(structure.dry_mass_kg, rel=1e-12)
    # Shell sits ahead of the dry CG: CG moves forward and transverse inertia grows.
    assert structure.center_of_mass_m < baseline.center_of_mass_m
    assert structure.inertia_kg_m2[0] > baseline.inertia_kg_m2[0]
    assert len(structure.components) == len(baseline.components) + 1

    # A measured dry mass still wins over the derived shell.
    measured = with_shell.model_copy(update={"dry_mass_override_kg": 12.0})
    assert derive_dry_mass(measured) == pytest.approx(12.0)
    assert derive_rocket_structure(measured).dry_mass_kg == pytest.approx(
        baseline.dry_mass_kg + shell.mass_kg, rel=1e-12
    )
