"""Solid motor geometry, casing, grain, and thrust curve domain models."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hefesto.domain._validators import (
    require_axisymmetric_inertia,
    require_burn_time,
    require_non_empty_text,
    require_relative_asset,
    require_xy_curve,
)


class GeometryValidationError(Exception):
    """Blocking error raised when grain stack or motor geometry overflows physical bounds."""


class GrainInhibition(StrEnum):
    """Inhibited end faces of a BATES propellant grain."""

    NEITHER = "neither"
    TOP = "top"
    BOTTOM = "bottom"
    BOTH = "both"


class InterpolationMethod(StrEnum):
    """Thrust curve interpolation methods supported by RocketPy."""

    LINEAR = "linear"
    SPLINE = "spline"
    AKIMA = "akima"


class GrainSpec(BaseModel):
    """Single hollow cylindrical BATES propellant grain."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    length_m: float = Field(gt=0.0)
    outer_radius_m: float = Field(gt=0.0)
    inner_radius_m: float = Field(ge=0.0)
    inhibited_ends: GrainInhibition = GrainInhibition.NEITHER

    @field_validator("inhibited_ends", mode="before")
    @classmethod
    def _normalize_inhibited_ends(cls, value: GrainInhibition | str) -> GrainInhibition | str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @model_validator(mode="after")
    def _validate_inner_smaller_than_outer(self) -> GrainSpec:
        if self.inner_radius_m >= self.outer_radius_m:
            raise ValueError(
                f"inner_radius_m ({self.inner_radius_m}) must be strictly less than "
                f"outer_radius_m ({self.outer_radius_m})"
            )
        return self


class NozzleSpec(BaseModel):
    """Converging-diverging rocket motor nozzle geometry in SI and degrees."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    throat_radius_m: float = Field(gt=0.0)
    exit_radius_m: float = Field(gt=0.0)
    position_m: float = 0.0
    throat_length_m: float | None = Field(default=None, gt=0.0)
    converging_angle_deg: float | None = Field(default=None, gt=0.0, lt=90.0)
    diverging_angle_deg: float | None = Field(default=None, gt=0.0, lt=90.0)
    efficiency: float = Field(default=1.0, gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_exit_ge_throat(self) -> NozzleSpec:
        if self.exit_radius_m < self.throat_radius_m:
            raise ValueError(
                f"exit_radius_m ({self.exit_radius_m}) must be >= "
                f"throat_radius_m ({self.throat_radius_m})"
            )
        return self


class MotorCasingSpec(BaseModel):
    """Motor casing dimensions, structural yield limit, and dry mass/inertia properties."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    inner_radius_m: float = Field(gt=0.0)
    wall_thickness_m: float = Field(gt=0.0)
    length_m: float = Field(gt=0.0)
    internal_clearance_m: float = Field(default=0.0, ge=0.0)
    yield_strength_pa: float = Field(gt=0.0)
    dry_mass_kg: float = Field(gt=0.0)
    dry_inertia_kg_m2: tuple[float, float, float]
    center_of_dry_mass_m: float

    @field_validator("dry_inertia_kg_m2")
    @classmethod
    def _validate_inertia(
        cls, value: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        return require_axisymmetric_inertia(value, "dry_inertia_kg_m2")

    @model_validator(mode="after")
    def _validate_clearance(self) -> MotorCasingSpec:
        if self.internal_clearance_m >= self.length_m:
            raise ValueError(
                f"internal_clearance_m ({self.internal_clearance_m}) must be less than "
                f"length_m ({self.length_m})"
            )
        return self

    @property
    def outer_radius_m(self) -> float:
        return self.inner_radius_m + self.wall_thickness_m

    @property
    def available_grain_length_m(self) -> float:
        return self.length_m - self.internal_clearance_m


class MotorOverride(BaseModel):
    """Typed parameter override applied to a motor configuration path."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    path: str
    value: float | int | str

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return require_non_empty_text(value, "path")


class MotorSpec(BaseModel):
    """Complete in-memory solid motor specification (nozzle_to_combustion_chamber)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: str
    coordinate_system: Literal["nozzle_to_combustion_chamber"] = "nozzle_to_combustion_chamber"
    grains: tuple[GrainSpec, ...] = Field(min_length=1)
    grain_separation_m: float = Field(ge=0.0)
    grains_center_of_mass_m: float
    propellant_name: str = "KNSB"
    propellant_density_kg_m3: float = Field(gt=0.0)
    nozzle: NozzleSpec
    casing: MotorCasingSpec
    burn_time_s: tuple[float, float]
    thrust_curve: tuple[tuple[float, float], ...]
    interpolation_method: InterpolationMethod = InterpolationMethod.LINEAR
    motor_asset: str | None = None
    thrust_curve_asset: str | None = None

    @field_validator("name", "propellant_name")
    @classmethod
    def _validate_names(cls, value: str) -> str:
        return require_non_empty_text(value, "name")

    @field_validator("motor_asset", "thrust_curve_asset")
    @classmethod
    def _validate_assets(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_relative_asset(value, "motor asset")

    @field_validator("burn_time_s")
    @classmethod
    def _validate_burn_time(cls, value: tuple[float, float]) -> tuple[float, float]:
        return require_burn_time(value)

    @field_validator("thrust_curve")
    @classmethod
    def _validate_thrust_curve(
        cls, value: tuple[tuple[float, float], ...]
    ) -> tuple[tuple[float, float], ...]:
        return require_xy_curve(
            value,
            x_name="time_s",
            y_name="thrust_n",
            min_points=2,
            min_x=0.0,
            min_y=0.0,
            strict_x=True,
        )

    @property
    def grain_count(self) -> int:
        return len(self.grains)

    @property
    def grain_stack_length_m(self) -> float:
        # Grain stack length includes spacing gaps; physics checks this before RocketPy.
        total_grain_len = sum(grain.length_m for grain in self.grains)
        return total_grain_len + (len(self.grains) - 1) * self.grain_separation_m

    @property
    def max_grain_outer_radius_m(self) -> float:
        return max(grain.outer_radius_m for grain in self.grains)


__all__ = [
    "GeometryValidationError",
    "GrainInhibition",
    "GrainSpec",
    "InterpolationMethod",
    "MotorCasingSpec",
    "MotorOverride",
    "MotorSpec",
    "NozzleSpec",
]
