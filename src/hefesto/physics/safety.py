"""Fail-closed, non-blocking evaluation of the five motor safety criteria."""

from __future__ import annotations

import math
from collections.abc import Sequence

from hefesto.domain import (
    BallisticsResult,
    GrainSpec,
    MotorCasingSpec,
    MotorSpec,
    SafetyCheck,
    SafetyCriterion,
    SafetyLimits,
    SafetyReport,
)
from hefesto.physics.constants import PA_PER_MPA

DEFAULT_SAFETY_LIMITS = SafetyLimits()


def _valid_positive_finite(value: float | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0.0:
        return None
    return numeric


def _build_safety_check(
    *,
    criterion: SafetyCriterion,
    name: str,
    value: float | None,
    unit: str,
    min_limit: float | None = None,
    max_limit: float | None = None,
    detail: str = "",
    invalid_detail: str = "invalid or missing telemetry (fail-closed)",
) -> SafetyCheck:
    if value is None or not math.isfinite(value):
        return SafetyCheck(
            criterion=criterion,
            name=name,
            value=None,
            min_limit=min_limit,
            max_limit=max_limit,
            unit=unit,
            passed=False,
            detail=invalid_detail,
        )

    if min_limit is not None:
        passed = value >= min_limit
    elif max_limit is not None:
        passed = value <= max_limit
    else:
        passed = False

    return SafetyCheck(
        criterion=criterion,
        name=name,
        value=value,
        min_limit=min_limit,
        max_limit=max_limit,
        unit=unit,
        passed=passed,
        detail=detail,
    )


def compute_case_hoop_stress_pa(
    peak_chamber_pressure_pa: float | None,
    case_inner_radius_m: float | None,
    case_wall_thickness_m: float | None,
) -> float | None:
    """Compute thin-walled cylindrical hoop stress sigma = P0 * r_i / t (fail-closed)."""
    pressure = _valid_positive_finite(peak_chamber_pressure_pa)
    inner_radius = _valid_positive_finite(case_inner_radius_m)
    wall_thickness = _valid_positive_finite(case_wall_thickness_m)
    if pressure is None or inner_radius is None or wall_thickness is None:
        return None
    hoop_stress = pressure * inner_radius / wall_thickness
    if not math.isfinite(hoop_stress) or hoop_stress <= 0.0:
        return None
    return hoop_stress


def compute_aft_port_to_throat_ratio(
    grains: Sequence[GrainSpec] | None,
    throat_radius_m: float | None,
) -> float | None:
    """Compute nozzle-end (aft) grain port-to-throat area ratio on grains[-1]."""
    if not grains:
        return None
    throat = _valid_positive_finite(throat_radius_m)
    aft_port = _valid_positive_finite(grains[-1].inner_radius_m)
    if throat is None or aft_port is None:
        return None
    ratio = (aft_port / throat) ** 2
    if not math.isfinite(ratio) or ratio <= 0.0:
        return None
    return ratio


def check_case_safety_factor(
    peak_chamber_pressure_pa: float | None,
    case_inner_radius_m: float | None,
    case_wall_thickness_m: float | None,
    yield_strength_pa: float | None,
    *,
    limits: SafetyLimits = DEFAULT_SAFETY_LIMITS,
) -> SafetyCheck:
    """Evaluate thin-wall casing yield safety factor against min_case_safety_factor."""
    hoop_stress = compute_case_hoop_stress_pa(
        peak_chamber_pressure_pa,
        case_inner_radius_m,
        case_wall_thickness_m,
    )
    yield_strength = _valid_positive_finite(yield_strength_pa)

    safety_factor: float | None = None
    detail = ""
    if hoop_stress is not None and yield_strength is not None:
        candidate = yield_strength / hoop_stress
        if math.isfinite(candidate) and candidate > 0.0:
            safety_factor = candidate
            detail = (
                f"hoop_stress={hoop_stress / PA_PER_MPA:.2f} MPa, "
                f"yield={yield_strength / PA_PER_MPA:.0f} MPa, "
                f"target>={limits.target_case_safety_factor:.2f}"
            )

    return _build_safety_check(
        criterion=SafetyCriterion.CASE_SAFETY_FACTOR,
        name="Case safety factor",
        value=safety_factor,
        unit="",
        min_limit=limits.min_case_safety_factor,
        detail=detail,
        invalid_detail="invalid or non-positive casing/pressure input (fail-closed)",
    )


def check_peak_chamber_pressure(
    peak_chamber_pressure_pa: float | None,
    *,
    limits: SafetyLimits = DEFAULT_SAFETY_LIMITS,
) -> SafetyCheck:
    """Evaluate peak chamber pressure in Pa against max_chamber_pressure_pa."""
    pressure = _valid_positive_finite(peak_chamber_pressure_pa)
    detail = (
        f"p0_peak={pressure / PA_PER_MPA:.3f} MPa "
        f"(limit={limits.max_chamber_pressure_pa / PA_PER_MPA:.2f} MPa)"
        if pressure is not None
        else ""
    )
    return _build_safety_check(
        criterion=SafetyCriterion.PEAK_CHAMBER_PRESSURE,
        name="Peak chamber pressure",
        value=pressure,
        unit="Pa",
        max_limit=limits.max_chamber_pressure_pa,
        detail=detail,
    )


def check_peak_kn(
    peak_kn: float | None,
    *,
    limits: SafetyLimits = DEFAULT_SAFETY_LIMITS,
) -> SafetyCheck:
    """Evaluate peak burn-area-to-throat ratio Kn against max_kn."""
    kn = _valid_positive_finite(peak_kn)
    return _build_safety_check(
        criterion=SafetyCriterion.PEAK_KN,
        name="Peak Kn",
        value=kn,
        unit="",
        max_limit=limits.max_kn,
        detail="burn-to-throat area ratio" if kn is not None else "",
    )


def check_peak_mass_flux(
    peak_mass_flux_kg_m2_s: float | None,
    *,
    limits: SafetyLimits = DEFAULT_SAFETY_LIMITS,
) -> SafetyCheck:
    """Evaluate peak propellant mass flux in kg/(m^2*s) against max_mass_flux_kg_m2_s."""
    mass_flux = _valid_positive_finite(peak_mass_flux_kg_m2_s)
    return _build_safety_check(
        criterion=SafetyCriterion.PEAK_MASS_FLUX,
        name="Peak mass flux",
        value=mass_flux,
        unit="kg/(m^2*s)",
        max_limit=limits.max_mass_flux_kg_m2_s,
        detail="aft port mass flux ceiling" if mass_flux is not None else "",
    )


def check_port_to_throat_ratio(
    grains: Sequence[GrainSpec] | None,
    throat_radius_m: float | None,
    *,
    limits: SafetyLimits = DEFAULT_SAFETY_LIMITS,
) -> SafetyCheck:
    """Evaluate aft grain (grains[-1]) port-to-throat ratio against min_port_to_throat_ratio."""
    ratio = compute_aft_port_to_throat_ratio(grains, throat_radius_m)
    return _build_safety_check(
        criterion=SafetyCriterion.PORT_TO_THROAT_RATIO,
        name="Aft port-to-throat ratio",
        value=ratio,
        unit="",
        min_limit=limits.min_port_to_throat_ratio,
        detail="aft grain grains[-1] port area / throat area" if ratio is not None else "",
        invalid_detail="invalid or non-positive aft port / throat geometry (fail-closed)",
    )


def evaluate_safety_metrics(
    *,
    peak_chamber_pressure_pa: float | None,
    peak_kn: float | None,
    peak_mass_flux_kg_m2_s: float | None,
    grains: Sequence[GrainSpec] | None,
    throat_radius_m: float | None,
    casing: MotorCasingSpec | None,
    limits: SafetyLimits | None = None,
) -> SafetyReport:
    """Run all five fail-closed non-blocking checks and return a complete SafetyReport."""
    resolved_limits = DEFAULT_SAFETY_LIMITS if limits is None else limits

    if casing is not None:
        hoop_stress_pa = compute_case_hoop_stress_pa(
            peak_chamber_pressure_pa,
            casing.inner_radius_m,
            casing.wall_thickness_m,
        )
        fs_check = check_case_safety_factor(
            peak_chamber_pressure_pa,
            casing.inner_radius_m,
            casing.wall_thickness_m,
            casing.yield_strength_pa,
            limits=resolved_limits,
        )
    else:
        hoop_stress_pa = None
        fs_check = check_case_safety_factor(
            peak_chamber_pressure_pa,
            None,
            None,
            None,
            limits=resolved_limits,
        )

    if fs_check.value is None:
        hoop_stress_pa = None

    checks = (
        fs_check,
        check_peak_chamber_pressure(peak_chamber_pressure_pa, limits=resolved_limits),
        check_peak_kn(peak_kn, limits=resolved_limits),
        check_peak_mass_flux(peak_mass_flux_kg_m2_s, limits=resolved_limits),
        check_port_to_throat_ratio(grains, throat_radius_m, limits=resolved_limits),
    )
    return SafetyReport(
        limits=resolved_limits,
        checks=checks,
        hoop_stress_pa=hoop_stress_pa,
    )


def evaluate_motor_safety(
    ballistics: BallisticsResult | None,
    casing: MotorCasingSpec | None = None,
    limits: SafetyLimits | None = None,
    *,
    motor: MotorSpec | None = None,
) -> SafetyReport:
    """Evaluate all five safety criteria from BallisticsResult and MotorCasingSpec/MotorSpec."""
    resolved_casing = (
        casing if casing is not None else (motor.casing if motor is not None else None)
    )
    if ballistics is not None:
        grains: Sequence[GrainSpec] | None = ballistics.grains
        throat_radius_m: float | None = ballistics.throat_radius_m
        peak_pressure_pa: float | None = ballistics.peak_chamber_pressure_pa
        peak_kn: float | None = ballistics.peak_kn
        peak_mass_flux: float | None = ballistics.peak_mass_flux_kg_m2_s
    else:
        grains = motor.grains if motor is not None else None
        throat_radius_m = motor.nozzle.throat_radius_m if motor is not None else None
        peak_pressure_pa = None
        peak_kn = None
        peak_mass_flux = None

    return evaluate_safety_metrics(
        peak_chamber_pressure_pa=peak_pressure_pa,
        peak_kn=peak_kn,
        peak_mass_flux_kg_m2_s=peak_mass_flux,
        grains=grains,
        throat_radius_m=throat_radius_m,
        casing=resolved_casing,
        limits=limits,
    )


__all__ = [
    "DEFAULT_SAFETY_LIMITS",
    "check_case_safety_factor",
    "check_peak_chamber_pressure",
    "check_peak_kn",
    "check_peak_mass_flux",
    "check_port_to_throat_ratio",
    "compute_aft_port_to_throat_ratio",
    "compute_case_hoop_stress_pa",
    "evaluate_motor_safety",
    "evaluate_safety_metrics",
]
