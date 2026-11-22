"""Aerodynamic surfaces, recovery parachutes, rail buttons, and drag curves."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hefesto.domain._validators import (
    require_non_empty_text,
    require_relative_asset,
    require_xy_curve,
)


class NoseConeKind(StrEnum):
    """Nose cone profiles supported by RocketPy."""

    LV_HAACK = "lvhaack"
    CONICAL = "conical"
    OGIVE = "ogive"
    VON_KARMAN = "Von Karman"
    POWERSERIES = "powerseries"


class NoseConeSpec(BaseModel):
    """Aerodynamic nose cone configuration along nose_to_tail axis."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    length_m: float = Field(gt=0.0)
    kind: NoseConeKind = NoseConeKind.LV_HAACK
    position_m: float = Field(default=0.0, ge=0.0)
    bluffness: float = Field(default=0.0, ge=0.0, le=1.0)
    power: float | None = Field(default=None, gt=0.0)
    base_radius_m: float | None = Field(default=None, gt=0.0)
    name: str = "Nose Cone"

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_non_empty_text(value, "name")


class FinSetSpec(BaseModel):
    """Aerodynamic fin set geometry supporting free-form and trapezoidal RocketPy builders."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: str = "Fins"
    count: int = Field(ge=1)
    position_m: float = Field(ge=0.0)
    shape_points_m: tuple[tuple[float, float], ...] = Field(min_length=3)
    cant_angle_deg: float = Field(default=0.0, ge=-45.0, le=45.0)
    radius_m: float | None = Field(default=None, gt=0.0)
    root_chord_m: float | None = Field(default=None, gt=0.0)
    tip_chord_m: float | None = Field(default=None, ge=0.0)
    span_m: float | None = Field(default=None, gt=0.0)
    sweep_length_m: float | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_non_empty_text(value, "name")

    @field_validator("shape_points_m")
    @classmethod
    def _validate_shape_points(
        cls, points: tuple[tuple[float, float], ...]
    ) -> tuple[tuple[float, float], ...]:
        for idx, (x_m, y_m) in enumerate(points):
            if not (math.isfinite(x_m) and math.isfinite(y_m)):
                raise ValueError(f"Fin shape point [{idx}] must be finite: {(x_m, y_m)!r}")
        return points


class RailButtonsSpec(BaseModel):
    """Launch rail buttons placed along nose_to_tail axis."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    upper_button_position_m: float = Field(ge=0.0)
    lower_button_position_m: float = Field(ge=0.0)
    angular_position_deg: float = Field(default=45.0, ge=0.0, lt=360.0)
    radius_m: float | None = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def _validate_button_order(self) -> RailButtonsSpec:
        # In nose_to_tail coordinates, lower button sits closer to the tail (larger position).
        if self.upper_button_position_m >= self.lower_button_position_m:
            raise ValueError(
                f"upper_button_position_m ({self.upper_button_position_m}) must be less than "
                f"lower_button_position_m ({self.lower_button_position_m}) in nose_to_tail"
            )
        return self


class ParachuteSpec(BaseModel):
    """Recovery parachute parameters and deployment trigger."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: str
    cd_s_m2: float = Field(gt=0.0)
    trigger: Literal["apogee"] | float
    lag_s: float = Field(default=0.0, ge=0.0)
    radius_m: float = Field(default=1.5, gt=0.0)
    sampling_rate_hz: float = Field(default=100.0, gt=0.0)
    noise_std: tuple[float, float, float] = (0.0, 0.0, 0.0)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_non_empty_text(value, "name")

    @field_validator("trigger")
    @classmethod
    def _validate_trigger(cls, value: Literal["apogee"] | float) -> Literal["apogee"] | float:
        if isinstance(value, (int, float)) and value <= 0.0:
            raise ValueError(f"Numeric parachute altitude trigger must be > 0, got {value}")
        return value

    @field_validator("noise_std")
    @classmethod
    def _validate_noise_std(
        cls, value: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        if any(sigma < 0.0 for sigma in value):
            raise ValueError(f"noise_std values must be >= 0, got {value!r}")
        return value


class DragCurveSpec(BaseModel):
    """In-memory Mach vs drag coefficient (Cd) curve with optional relative source asset."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    points: tuple[tuple[float, float], ...]
    asset_name: str | None = None

    @field_validator("points")
    @classmethod
    def _validate_points(
        cls, value: tuple[tuple[float, float], ...]
    ) -> tuple[tuple[float, float], ...]:
        return require_xy_curve(
            value,
            x_name="mach",
            y_name="cd",
            min_points=2,
            min_x=0.0,
            min_y=0.0,
            strict_x=True,
        )

    @field_validator("asset_name")
    @classmethod
    def _validate_asset(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_relative_asset(value, "asset_name")


__all__ = [
    "DragCurveSpec",
    "FinSetSpec",
    "NoseConeKind",
    "NoseConeSpec",
    "ParachuteSpec",
    "RailButtonsSpec",
]
