"""Rocket vehicle assembly specification in nose_to_tail coordinates."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hefesto.domain._validators import (
    require_axisymmetric_inertia,
    require_non_empty_text,
)
from hefesto.domain.aerodynamics import (
    DragCurveSpec,
    FinSetSpec,
    NoseConeSpec,
    ParachuteSpec,
    RailButtonsSpec,
)
from hefesto.domain.components import RocketComponent
from hefesto.domain.motor import MotorSpec

MassMode = Literal["calculated", "measured"]
FinGeometryMode = Literal["freeform", "trapezoidal"]


class RocketSpec(BaseModel):
    """Complete in-memory 6-DOF vehicle specification (nose_to_tail, SI units)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: str
    coordinate_system: Literal["nose_to_tail"] = "nose_to_tail"
    radius_m: float = Field(gt=0.0)
    center_of_mass_without_motor_m: float = Field(gt=0.0)
    inertia_kg_m2: tuple[float, float, float]
    motor_position_m: float = Field(gt=0.0)
    components: tuple[RocketComponent, ...] = Field(min_length=1)
    dry_mass_override_kg: float | None = Field(default=None, gt=0.0)
    nose_cone: NoseConeSpec
    fins: FinSetSpec
    rail_buttons: RailButtonsSpec
    parachutes: tuple[ParachuteSpec, ...] = ()
    power_off_drag: DragCurveSpec
    power_on_drag: DragCurveSpec
    motor: MotorSpec

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_non_empty_text(value, "name")

    @field_validator("inertia_kg_m2")
    @classmethod
    def _validate_inertia(
        cls, value: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        return require_axisymmetric_inertia(value, "inertia_kg_m2")


__all__ = ["FinGeometryMode", "MassMode", "RocketSpec"]
