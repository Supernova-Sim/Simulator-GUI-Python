"""TDD tests for Hefesto pure solid motor preparation and casing mass/inertia scaling."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from hefesto.domain import (
    GeometryValidationError,
    GrainSpec,
    InterpolationMethod,
    MotorCasingSpec,
    MotorSpec,
    NozzleSpec,
)
from hefesto.physics.constants import ALUMINUM_DENSITY_KG_M3
from hefesto.physics.geometry import hollow_cylinder_volume_m3
from hefesto.physics.inertia import compute_motor_casing_dry_inertia_kg_m2
from hefesto.physics.propulsion import (
    PreparedSolidMotor,
    compute_casing_shell_mass_kg,
    prepare_solid_motor,
    recalculate_casing_dry_properties,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = REPO_ROOT / "tests" / "golden" / "hefesto_baseline.json"
MEDUSA_ENG_PATH = REPO_ROOT / "data" / "assets" / "motors" / "medusa_knsb_a.eng"


def _load_medusa_thrust_curve() -> tuple[tuple[float, float], ...]:
    lines = MEDUSA_ENG_PATH.read_text(encoding="utf-8").splitlines()[1:]
    points: list[tuple[float, float]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        t_str, f_str = stripped.split()[:2]
        points.append((float(t_str), float(f_str)))
    return tuple(points)


def _medusa_grains() -> tuple[GrainSpec, ...]:
    return (
        *(
            GrainSpec(
                length_m=0.16,
                outer_radius_m=0.049345,
                inner_radius_m=0.0195,
            )
            for _ in range(4)
        ),
        *(
            GrainSpec(
                length_m=0.16,
                outer_radius_m=0.049345,
                inner_radius_m=0.027,
            )
            for _ in range(2)
        ),
    )


def _medusa_casing(
    *,
    inner_radius_m: float = 0.05395,
    wall_thickness_m: float = 0.003175,
    length_m: float = 1.10,
    internal_clearance_m: float = 0.04,
    dry_mass_kg: float = 7.5,
    dry_inertia_kg_m2: tuple[float, float, float] = (
        0.7678260027343752,
        0.7678260027343752,
        0.023152005468749997,
    ),
    center_of_dry_mass_m: float = 0.55,
) -> MotorCasingSpec:
    return MotorCasingSpec(
        inner_radius_m=inner_radius_m,
        wall_thickness_m=wall_thickness_m,
        length_m=length_m,
        internal_clearance_m=internal_clearance_m,
        yield_strength_pa=145_000_000.0,
        dry_mass_kg=dry_mass_kg,
        dry_inertia_kg_m2=dry_inertia_kg_m2,
        center_of_dry_mass_m=center_of_dry_mass_m,
    )


def _medusa_motor(
    *,
    casing: MotorCasingSpec | None = None,
    grains: tuple[GrainSpec, ...] | None = None,
    grain_separation_m: float = 0.01,
    thrust_curve: tuple[tuple[float, float], ...] | None = None,
    interpolation_method: InterpolationMethod = InterpolationMethod.LINEAR,
) -> MotorSpec:
    return MotorSpec(
        name="Medusa KNSB A",
        grains=_medusa_grains() if grains is None else grains,
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
        casing=_medusa_casing() if casing is None else casing,
        burn_time_s=(0.0, 3.9),
        thrust_curve=(
            ((0.0, 0.0), (0.03, 3159.6675), (3.87, 1766.9398), (3.9, 0.0))
            if thrust_curve is None
            else thrust_curve
        ),
        interpolation_method=interpolation_method,
        motor_asset="medusa_knsb_a.ric",
        thrust_curve_asset="medusa_knsb_a.eng",
    )


def test_prepare_solid_motor_matches_golden_medusa_baseline() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    medusa_curve = _load_medusa_thrust_curve()
    motor_spec = _medusa_motor(thrust_curve=medusa_curve)

    prepared = prepare_solid_motor(motor_spec)
    assert isinstance(prepared, PreparedSolidMotor)
    assert prepared.delta_shell_mass_kg == 0.0
    assert isinstance(prepared.thrust_points, list)
    assert len(prepared.thrust_points) == len(medusa_curve)
    assert prepared.casing.dry_mass_kg == pytest.approx(
        golden["rocketpy_baseline_88deg"]["inputs"]["motor_dry_mass_kg"], rel=1e-12
    )
    assert prepared.casing.dry_inertia_kg_m2 == pytest.approx(
        tuple(golden["rocketpy_baseline_88deg"]["inputs"]["motor_dry_inertia_kg_m2"]),
        rel=1e-12,
    )
    assert prepared.casing.center_of_dry_mass_m == pytest.approx(
        golden["rocketpy_baseline_88deg"]["inputs"]["motor_center_of_dry_mass_m"], rel=1e-12
    )
    assert prepared.propellant_mass_kg == pytest.approx(
        golden["openmotor_baselines"]["medusa_knsb_a"]["propellant_mass_kg"], rel=1e-12
    )
    assert prepared.loaded_mass_kg == pytest.approx(
        prepared.casing.dry_mass_kg + prepared.propellant_mass_kg, rel=1e-12
    )
    assert prepared.total_impulse_ns == pytest.approx(
        golden["rocketpy_baseline_88deg"]["metrics"]["total_impulse_ns"], rel=1e-9
    )


def test_prepare_solid_motor_blocks_axial_and_radial_overflow() -> None:
    axial_overflow = _medusa_motor(
        casing=_medusa_casing(length_m=1.04, internal_clearance_m=0.04)
    )
    # 6 * 0.16 + 5 * 0.01 = 1.01 m > available 1.00 m
    with pytest.raises(GeometryValidationError, match="exceeds available casing"):
        prepare_solid_motor(axial_overflow)

    radial_overflow = _medusa_motor(
        grains=(
            *_medusa_grains()[:5],
            GrainSpec(length_m=0.16, outer_radius_m=0.055, inner_radius_m=0.027),
        )
    )
    with pytest.raises(GeometryValidationError, match="exceeds casing inner radius"):
        prepare_solid_motor(radial_overflow)


def test_recalculate_dry_mass_with_shell_delta_and_dry_inertia() -> None:
    base_casing = _medusa_casing()
    base_shell_mass = compute_casing_shell_mass_kg(
        base_casing.inner_radius_m,
        base_casing.wall_thickness_m,
        base_casing.length_m,
        ALUMINUM_DENSITY_KG_M3,
    )
    expected_base_vol = hollow_cylinder_volume_m3(
        base_casing.outer_radius_m,
        base_casing.inner_radius_m,
        base_casing.length_m,
    )
    assert base_shell_mass == pytest.approx(expected_base_vol * ALUMINUM_DENSITY_KG_M3)

    # Identical casing yields zero shell delta and bit-exact golden inertia.
    unchanged = recalculate_casing_dry_properties(base_casing, base_casing=base_casing)
    assert unchanged.dry_mass_kg == pytest.approx(7.5, rel=1e-12)
    assert unchanged.dry_inertia_kg_m2 == pytest.approx(base_casing.dry_inertia_kg_m2, rel=1e-12)

    # Thicker wall and longer casing: dry_mass = dry_mass_base + delta_m_shell, inertia updated.
    modified_casing = base_casing.model_copy(
        update={
            "wall_thickness_m": 0.005,
            "length_m": 1.20,
        }
    )
    updated = recalculate_casing_dry_properties(
        modified_casing,
        base_casing=base_casing,
        case_density_kg_m3=ALUMINUM_DENSITY_KG_M3,
    )

    new_r_i = 0.05395
    new_t = 0.005
    new_r_o = new_r_i + new_t
    new_len = 1.20
    new_shell_mass = math.pi * (new_r_o**2 - new_r_i**2) * new_len * ALUMINUM_DENSITY_KG_M3
    delta_m_shell = new_shell_mass - base_shell_mass
    expected_dry_mass = 7.5 + delta_m_shell
    expected_inertia = compute_motor_casing_dry_inertia_kg_m2(
        dry_mass_kg=expected_dry_mass,
        inner_radius_m=new_r_i,
        wall_thickness_m=new_t,
        length_m=new_len,
    )

    assert updated.dry_mass_kg == pytest.approx(expected_dry_mass, rel=1e-12)
    assert updated.center_of_dry_mass_m == pytest.approx(0.60, rel=1e-12)
    assert updated.dry_inertia_kg_m2 == pytest.approx(expected_inertia, rel=1e-12)

    # Passing base_casing to prepare_solid_motor propagates recalculated dry_mass & dry_inertia.
    modified_motor = _medusa_motor(casing=modified_casing)
    prepared = prepare_solid_motor(modified_motor, base_casing=base_casing)
    assert prepared.delta_shell_mass_kg == pytest.approx(delta_m_shell, rel=1e-12)
    assert prepared.casing.dry_mass_kg == pytest.approx(expected_dry_mass, rel=1e-12)
    assert prepared.casing.dry_inertia_kg_m2 == pytest.approx(expected_inertia, rel=1e-12)
    assert prepared.casing.center_of_dry_mass_m == pytest.approx(0.60, rel=1e-12)
    assert prepared.loaded_mass_kg == pytest.approx(
        expected_dry_mass + prepared.propellant_mass_kg, rel=1e-12
    )


def test_propulsion_edge_cases_and_invalid_inputs() -> None:
    # Without base_casing, recalculate_casing_dry_properties refreshes inertia from geometry.
    stale_inertia_casing = _medusa_casing(
        wall_thickness_m=0.004,
        dry_mass_kg=8.2,
        dry_inertia_kg_m2=(0.5, 0.5, 0.01),
    )
    refreshed = recalculate_casing_dry_properties(stale_inertia_casing)
    assert refreshed.dry_mass_kg == pytest.approx(8.2)
    assert refreshed.dry_inertia_kg_m2 == pytest.approx(
        compute_motor_casing_dry_inertia_kg_m2(8.2, 0.05395, 0.004, 1.10)
    )

    # Non-positive recalculated dry mass (extreme shell shrinkage) raises GeometryValidationError.
    heavy_base = _medusa_casing(
        inner_radius_m=0.08,
        wall_thickness_m=0.02,
        length_m=1.50,
        dry_mass_kg=1.0,
    )
    tiny_target = _medusa_casing(
        inner_radius_m=0.02,
        wall_thickness_m=0.001,
        length_m=0.20,
        dry_mass_kg=1.0,
        center_of_dry_mass_m=0.10,
    )
    with pytest.raises(GeometryValidationError, match="dry mass"):
        recalculate_casing_dry_properties(tiny_target, base_casing=heavy_base)

    # Non-positive or non-finite case density raises GeometryValidationError.
    with pytest.raises(GeometryValidationError, match="case_density_kg_m3"):
        compute_casing_shell_mass_kg(0.05, 0.003, 1.0, case_density_kg_m3=0.0)
    with pytest.raises(GeometryValidationError, match="case_density_kg_m3"):
        compute_casing_shell_mass_kg(0.05, 0.003, 1.0, case_density_kg_m3=float("nan"))

    # Thinner casing produces negative delta_m_shell (< dry_mass_base) at exact fit boundary.
    base_casing = _medusa_casing()
    thinner_exact = base_casing.model_copy(
        update={
            "wall_thickness_m": 0.002,
            "length_m": 1.05,
            "internal_clearance_m": 0.04,  # 1.05 - 0.04 == 1.01 m exact stack boundary
        }
    )
    thinner_motor = _medusa_motor(casing=thinner_exact)
    prepared_thin = prepare_solid_motor(thinner_motor, base_casing=base_casing)
    assert prepared_thin.delta_shell_mass_kg < 0.0
    assert prepared_thin.casing.dry_mass_kg == pytest.approx(
        base_casing.dry_mass_kg + prepared_thin.delta_shell_mass_kg
    )
    assert prepared_thin.casing.dry_mass_kg < base_casing.dry_mass_kg

    # Top-level hefesto.physics package re-exports propulsion and safety symbols without RocketPy.
    import hefesto.physics as physics_pkg

    for symbol in physics_pkg.__all__:
        assert hasattr(physics_pkg, symbol)
    assert not hasattr(physics_pkg, "build_solid_motor")
    assert physics_pkg.prepare_solid_motor is prepare_solid_motor
