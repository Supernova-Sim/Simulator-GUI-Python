"""Motor safety limits, fail-closed checks, and non-blocking safety reports."""

from __future__ import annotations

from enum import StrEnum

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


__all__ = [
    "SafetyCheck",
    "SafetyCriterion",
    "SafetyLimits",
    "SafetyReport",
]
