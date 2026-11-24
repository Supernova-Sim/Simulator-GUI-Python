"""Motor safety limits, fail-closed checks, and non-blocking safety reports."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hefesto.domain._validators import require_non_empty_text


class SafetyCriterion(StrEnum):
    """The five non-blocking motor safety criteria."""

    CASE_SAFETY_FACTOR = "case_safety_factor"
    PEAK_CHAMBER_PRESSURE = "peak_chamber_pressure_pa"
    PEAK_KN = "peak_kn"
    PEAK_MASS_FLUX = "peak_mass_flux_kg_m2_s"
    PORT_TO_THROAT_RATIO = "port_to_throat_ratio"


class SafetyLimits(BaseModel):
    """Design thresholds for motor structural and internal ballistics checks."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    min_case_safety_factor: float = Field(default=2.0, gt=0.0)
    target_case_safety_factor: float = Field(default=3.0, gt=0.0)
    max_chamber_pressure_pa: float = Field(default=8_000_000.0, gt=0.0)
    max_kn: float = Field(default=250.0, gt=0.0)
    max_mass_flux_kg_m2_s: float = Field(default=1406.0, gt=0.0)
    min_port_to_throat_ratio: float = Field(default=2.0, gt=0.0)

    @model_validator(mode="after")
    def _validate_target_ge_min(self) -> SafetyLimits:
        if self.target_case_safety_factor < self.min_case_safety_factor:
            raise ValueError(
                f"target_case_safety_factor ({self.target_case_safety_factor}) must be >= "
                f"min_case_safety_factor ({self.min_case_safety_factor})"
            )
        return self


class SafetyCheck(BaseModel):
    """Single fail-closed evaluation against a SafetyCriterion threshold."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    criterion: SafetyCriterion
    name: str
    value: float | None = None
    min_limit: float | None = None
    max_limit: float | None = None
    unit: str = ""
    passed: bool
    detail: str = ""

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_non_empty_text(value, "name")

    @model_validator(mode="after")
    def _enforce_fail_closed(self) -> SafetyCheck:
        if self.value is None and self.passed:
            raise ValueError("SafetyCheck with value=None must be fail-closed (passed=False)")
        return self


class SafetyReport(BaseModel):
    """Aggregated non-blocking safety evaluation covering all 5 criteria."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    limits: SafetyLimits
    checks: tuple[SafetyCheck, ...] = Field(min_length=5, max_length=5)
    hoop_stress_pa: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _validate_all_five_criteria_present(self) -> SafetyReport:
        criteria = {check.criterion for check in self.checks}
        expected = set(SafetyCriterion)
        if criteria != expected:
            missing = sorted(c.value for c in expected - criteria)
            raise ValueError(f"SafetyReport must cover all 5 criteria; missing={missing}")
        return self

    @property
    def all_passed(self) -> bool:
        return all(check.passed for check in self.checks)


class FlightSafetyStatus(StrEnum):
    """Traffic-light evaluation status for a flight safety envelope check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


# Reference shear modulus G (Pa) for common amateur rocketry fin materials.
FIN_MATERIAL_SHEAR_MODULUS_PA: Final[dict[str, float]] = {
    "Fibra de Vidro G10": 4.1e9,
    "Fibra de Carbono": 5.0e9,
    "Alumínio 6061-T6": 26.0e9,
    "Compensado Aeronáutico": 0.6e9,
}


class FlightSafetyLimits(BaseModel):
    """Configurable engineering thresholds for the Flight Safety Envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    min_flutter_safety_factor_fail: float = Field(default=1.25, gt=0.0)
    min_flutter_safety_factor_warn: float = Field(default=1.50, gt=0.0)
    min_static_margin_fail_calibers: float = 1.0
    min_static_margin_warn_calibers: float = 1.5
    max_static_margin_warn_calibers: float = 3.5
    max_apogee_horizontal_speed_warn_ms: float = Field(default=25.0, gt=0.0)
    max_apogee_horizontal_speed_fail_ms: float = Field(default=40.0, gt=0.0)
    max_burnout_tilt_warn_deg: float = Field(default=25.0, gt=0.0)
    max_burnout_tilt_fail_deg: float = Field(default=40.0, gt=0.0)
    min_twr_fail: float = Field(default=4.0, gt=0.0)
    min_twr_warn: float = Field(default=5.0, gt=0.0)
    min_rail_exit_velocity_fail_ms: float = Field(default=15.0, gt=0.0)
    min_rail_exit_velocity_warn_ms: float = Field(default=20.0, gt=0.0)
    max_rail_aoa_pass_deg: float = Field(default=12.0, gt=0.0)
    max_rail_aoa_warn_deg: float = Field(default=20.0, gt=0.0)
    max_axial_accel_warn_g: float = Field(default=15.0, gt=0.0)
    max_axial_accel_fail_g: float = Field(default=25.0, gt=0.0)
    parachute_opening_factor_cx: float = Field(default=1.3, gt=0.0)
    max_parachute_shock_warn_g: float = Field(default=15.0, gt=0.0)
    max_parachute_shock_fail_g: float = Field(default=25.0, gt=0.0)
    max_parachute_deploy_speed_warn_ms: float = Field(default=35.0, gt=0.0)
    max_parachute_deploy_speed_fail_ms: float = Field(default=60.0, gt=0.0)
    max_impact_speed_pass_ms: float = Field(default=7.5, gt=0.0)
    max_impact_speed_warn_ms: float = Field(default=10.0, gt=0.0)


class FlightSafetyCheck(BaseModel):
    """Single flight safety envelope check with status, measured value, and guidance."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    key: str
    category: str
    name: str
    status: FlightSafetyStatus
    value: float | None = None
    unit: str = ""
    reference_limit: str = ""
    detail: str = ""
    recommendation: str = ""

    @field_validator("key", "category", "name")
    @classmethod
    def _validate_texts(cls, value: str) -> str:
        return require_non_empty_text(value, "flight safety check text")


class FlightSafetyReport(BaseModel):
    """Aggregated Flight Safety Envelope report for a 6-DOF simulation run."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    limits: FlightSafetyLimits
    checks: tuple[FlightSafetyCheck, ...]
    overall_status: FlightSafetyStatus
    fin_flutter_velocity_ms: float | None = None
    fin_flutter_safety_factor: float | None = None
    max_q_kpa: float | None = None
    twr: float | None = None
    rail_aoa_deg: float | None = None
    max_parachute_shock_n: float | None = None
    max_parachute_shock_g: float | None = None


__all__ = [
    "FIN_MATERIAL_SHEAR_MODULUS_PA",
    "FlightSafetyCheck",
    "FlightSafetyLimits",
    "FlightSafetyReport",
    "FlightSafetyStatus",
    "SafetyCheck",
    "SafetyCriterion",
    "SafetyLimits",
    "SafetyReport",
]
