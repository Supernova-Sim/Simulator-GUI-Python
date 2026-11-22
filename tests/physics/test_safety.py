"""TDD tests for Hefesto fail-closed non-blocking motor safety evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto.domain import (
    BallisticsResult,
    GrainSpec,
    MotorCasingSpec,
    MotorSpec,
    NozzleSpec,
    SafetyCheck,
    SafetyCriterion,
    SafetyLimits,
    SafetyReport,
)
from hefesto.physics.safety import (
    check_case_safety_factor,
    check_peak_chamber_pressure,
    check_peak_kn,
    check_peak_mass_flux,
    check_port_to_throat_ratio,
    compute_aft_port_to_throat_ratio,
    compute_case_hoop_stress_pa,
    evaluate_motor_safety,
    evaluate_safety_metrics,
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


def _medusa_casing() -> MotorCasingSpec:
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


def _medusa_ballistics() -> BallisticsResult:
    return BallisticsResult(
        motor_name="Medusa KNSB A",
        grains=_medusa_grains(),
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
    )


def test_evaluate_motor_safety_matches_golden_medusa_baseline() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    safety_gold = golden["safety_baseline_medusa_knsb_a"]

    report = evaluate_motor_safety(_medusa_ballistics(), _medusa_casing())
    assert isinstance(report, SafetyReport)
    assert report.all_passed is True
    assert len(report.checks) == 5
    assert report.hoop_stress_pa == pytest.approx(safety_gold["hoop_stress_pa"], rel=1e-12)

    by_criterion = {check.criterion: check for check in report.checks}

    fs_check = by_criterion[SafetyCriterion.CASE_SAFETY_FACTOR]
    assert fs_check.passed is True
    assert fs_check.value == pytest.approx(
        safety_gold["checks"]["case_safety_factor"]["value"], rel=1e-12
    )
    assert fs_check.min_limit == pytest.approx(2.0)

    p0_check = by_criterion[SafetyCriterion.PEAK_CHAMBER_PRESSURE]
    assert p0_check.passed is True
    assert p0_check.unit == "Pa"
    assert p0_check.value == pytest.approx(
        safety_gold["checks"]["peak_chamber_pressure_mpa"]["value"] * 1e6, rel=1e-12
    )
    assert p0_check.max_limit == pytest.approx(8_000_000.0)

    kn_check = by_criterion[SafetyCriterion.PEAK_KN]
    assert kn_check.passed is True
    assert kn_check.value == pytest.approx(safety_gold["checks"]["peak_kn"]["value"], rel=1e-12)
    assert kn_check.max_limit == pytest.approx(250.0)

    mf_check = by_criterion[SafetyCriterion.PEAK_MASS_FLUX]
    assert mf_check.passed is True
    assert mf_check.value == pytest.approx(
        safety_gold["checks"]["peak_mass_flux_kg_m2_s"]["value"], rel=1e-12
    )
    assert mf_check.max_limit == pytest.approx(1406.0)

    pt_check = by_criterion[SafetyCriterion.PORT_TO_THROAT_RATIO]
    assert pt_check.passed is True
    assert pt_check.value == pytest.approx(
        safety_gold["checks"]["aft_port_to_throat_ratio"]["value"], rel=1e-12
    )
    assert pt_check.min_limit == pytest.approx(2.0)


def test_port_to_throat_uses_aft_grain_grains_minus_one() -> None:
    # Forward grains (0..3) have port/throat = (0.0195/0.017)^2 = 1.3157 < 2.0,
    # while aft grain grains[-1] has port/throat = (0.027/0.017)^2 = 2.5225 >= 2.0.
    grains = _medusa_grains()
    ratio = compute_aft_port_to_throat_ratio(grains, throat_radius_m=0.017)
    assert ratio == pytest.approx((0.027 / 0.017) ** 2, rel=1e-12)

    check = check_port_to_throat_ratio(grains, throat_radius_m=0.017)
    assert check.passed is True
    assert check.value == pytest.approx(2.5224913494809686, rel=1e-12)

    # Reversing order puts smaller bore at grains[-1] -> must evaluate grains[-1] and fail (< 2.0).
    reversed_grains = tuple(reversed(grains))
    failing_check = check_port_to_throat_ratio(reversed_grains, throat_radius_m=0.017)
    assert failing_check.passed is False
    assert failing_check.value == pytest.approx((0.0195 / 0.017) ** 2, rel=1e-12)


@pytest.mark.parametrize(
    "bad_value",
    [None, float("nan"), float("inf"), float("-inf"), 0.0, -10.0, True, False],
)
def test_all_five_checks_are_fail_closed_and_non_blocking(bad_value: float | bool | None) -> None:
    limits = SafetyLimits()

    # Pydantic SafetyCheck forbids NaN/inf, so invalid inputs must map to value=None, passed=False.
    fs_check = check_case_safety_factor(
        bad_value,  # type: ignore[arg-type]
        0.05395,
        0.003175,
        145_000_000.0,
        limits=limits,
    )
    assert isinstance(fs_check, SafetyCheck)
    assert fs_check.value is None
    assert fs_check.passed is False

    p0_check = check_peak_chamber_pressure(bad_value, limits=limits)  # type: ignore[arg-type]
    assert p0_check.value is None
    assert p0_check.passed is False

    kn_check = check_peak_kn(bad_value, limits=limits)  # type: ignore[arg-type]
    assert kn_check.value is None
    assert kn_check.passed is False

    mf_check = check_peak_mass_flux(bad_value, limits=limits)  # type: ignore[arg-type]
    assert mf_check.value is None
    assert mf_check.passed is False

    pt_check = check_port_to_throat_ratio(
        _medusa_grains(),
        bad_value,  # type: ignore[arg-type]
        limits=limits,
    )
    assert pt_check.value is None
    assert pt_check.passed is False

    # Also test invalid hoop stress inputs directly and zero-port solid grain.
    assert compute_case_hoop_stress_pa(3e6, bad_value, 0.003) is None  # type: ignore[arg-type]
    assert compute_case_hoop_stress_pa(3e6, 0.05, bad_value) is None  # type: ignore[arg-type]
    solid_aft = (GrainSpec(length_m=0.16, outer_radius_m=0.05, inner_radius_m=0.0),)
    solid_pt = check_port_to_throat_ratio(solid_aft, throat_radius_m=0.017, limits=limits)
    assert solid_pt.value is None
    assert solid_pt.passed is False


def test_non_blocking_limit_failures_and_partial_telemetry_reports() -> None:
    limits = SafetyLimits(
        min_case_safety_factor=3.0,
        target_case_safety_factor=3.5,
        max_chamber_pressure_pa=3_000_000.0,
        max_kn=240.0,
        max_mass_flux_kg_m2_s=1300.0,
        min_port_to_throat_ratio=2.6,
    )

    # All 5 criteria fail against tightened limits, yet SafetyReport returns without raising.
    report = evaluate_motor_safety(_medusa_ballistics(), _medusa_casing(), limits=limits)
    assert report.all_passed is False
    assert all(not check.passed for check in report.checks)
    assert all(check.value is not None for check in report.checks)

    # Exact boundary equality passes for both floor (>=) and ceiling (<=).
    boundary = evaluate_safety_metrics(
        peak_chamber_pressure_pa=limits.max_chamber_pressure_pa,
        peak_kn=limits.max_kn,
        peak_mass_flux_kg_m2_s=limits.max_mass_flux_kg_m2_s,
        grains=(GrainSpec(length_m=0.16, outer_radius_m=0.05, inner_radius_m=0.03),),
        throat_radius_m=0.03 / (limits.min_port_to_throat_ratio**0.5),
        casing=MotorCasingSpec(
            inner_radius_m=0.05,
            wall_thickness_m=0.005,
            length_m=1.0,
            yield_strength_pa=90_000_000.0,
            dry_mass_kg=5.0,
            dry_inertia_kg_m2=(0.4, 0.4, 0.01),
            center_of_dry_mass_m=0.5,
        ),
        limits=limits,
    )
    by_crit = {c.criterion: c for c in boundary.checks}
    assert by_crit[SafetyCriterion.PEAK_CHAMBER_PRESSURE].passed is True
    assert by_crit[SafetyCriterion.PEAK_KN].passed is True
    assert by_crit[SafetyCriterion.PEAK_MASS_FLUX].passed is True
    assert by_crit[SafetyCriterion.PORT_TO_THROAT_RATIO].passed is True
    assert by_crit[SafetyCriterion.CASE_SAFETY_FACTOR].passed is True

    # Missing ballistics (e.g. .eng-only run) still evaluates port/throat when MotorSpec is given.
    eng_only_motor = MotorSpec(
        name="Medusa ENG Only",
        grains=_medusa_grains(),
        grain_separation_m=0.01,
        grains_center_of_mass_m=0.54,
        propellant_density_kg_m3=1841.0,
        nozzle=NozzleSpec(throat_radius_m=0.017, exit_radius_m=0.039),
        casing=_medusa_casing(),
        burn_time_s=(0.0, 3.9),
        thrust_curve=((0.0, 0.0), (1.0, 3000.0), (3.9, 0.0)),
    )
    partial_report = evaluate_motor_safety(None, motor=eng_only_motor)
    assert partial_report.all_passed is False
    assert partial_report.hoop_stress_pa is None
    partial_by_crit = {c.criterion: c for c in partial_report.checks}
    assert partial_by_crit[SafetyCriterion.PORT_TO_THROAT_RATIO].passed is True
    assert partial_by_crit[SafetyCriterion.CASE_SAFETY_FACTOR].passed is False
    assert partial_by_crit[SafetyCriterion.PEAK_CHAMBER_PRESSURE].passed is False
    assert partial_by_crit[SafetyCriterion.PEAK_KN].passed is False
    assert partial_by_crit[SafetyCriterion.PEAK_MASS_FLUX].passed is False

    # Missing both ballistics and casing returns all 5 checks fail-closed with hoop_stress_pa=None.
    empty_report = evaluate_motor_safety(None, None)
    assert empty_report.all_passed is False
    assert empty_report.hoop_stress_pa is None
    assert all(c.value is None and not c.passed for c in empty_report.checks)
    assert SafetyReport.model_validate_json(empty_report.model_dump_json()) == empty_report

    # Empty or None grains and extreme underflow pressure remain non-blocking and fail-closed.
    assert check_port_to_throat_ratio((), 0.017).passed is False
    assert check_port_to_throat_ratio(None, 0.017).passed is False
    underflow = evaluate_safety_metrics(
        peak_chamber_pressure_pa=1e-320,
        peak_kn=100.0,
        peak_mass_flux_kg_m2_s=500.0,
        grains=_medusa_grains(),
        throat_radius_m=0.017,
        casing=_medusa_casing(),
    )
    underflow_fs = next(
        c for c in underflow.checks if c.criterion == SafetyCriterion.CASE_SAFETY_FACTOR
    )
    assert underflow_fs.value is None
    assert underflow_fs.passed is False
    assert underflow.hoop_stress_pa is None
