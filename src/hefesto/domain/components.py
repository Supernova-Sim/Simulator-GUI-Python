"""Structural rocket component models (tubes, bulkheads, point masses, fin plates)."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hefesto.domain._validators import require_non_empty_text


class TubeComponent(BaseModel):
    """Hollow cylindrical shell or solid bulkhead when wall_thickness_m == outer_radius_m."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["tube"] = "tube"
    name: str
    outer_radius_m: float = Field(gt=0.0)
    wall_thickness_m: float = Field(gt=0.0)
    length_m: float = Field(gt=0.0)
    density_kg_m3: float = Field(gt=0.0)
    position_m: float = Field(ge=0.0)
    # OpenRocket <overridemass>/<overridecg>: absolute axial CG when provided.
    mass_override_kg: float | None = Field(default=None, gt=0.0)
    cg_override_m: float | None = Field(default=None, ge=0.0)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_non_empty_text(value, "name")

    @model_validator(mode="after")
    def _validate_wall_within_radius(self) -> TubeComponent:
        if self.wall_thickness_m > self.outer_radius_m:
            raise ValueError(
                f"wall_thickness_m ({self.wall_thickness_m}) cannot exceed "
                f"outer_radius_m ({self.outer_radius_m})"
            )
        return self

    @property
    def inner_radius_m(self) -> float:
        return self.outer_radius_m - self.wall_thickness_m


class PointMassComponent(BaseModel):
    """Lumped mass placed along the rocket nose_to_tail axis."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["point_mass"] = "point_mass"
    name: str
    mass_kg: float = Field(gt=0.0)
    position_m: float = Field(ge=0.0)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_non_empty_text(value, "name")


class FinComponent(BaseModel):
    """Structural fin plate mass definition described by an extruded polygon."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["fins"] = "fins"
    name: str
    count: int = Field(ge=1)
    shape_points_m: tuple[tuple[float, float], ...] = Field(min_length=3)
    thickness_m: float = Field(gt=0.0)
    density_kg_m3: float = Field(gt=0.0)
    position_m: float = Field(default=0.0, ge=0.0)

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
                raise ValueError(f"Fin polygon point [{idx}] must be finite: {(x_m, y_m)!r}")
        return points


RocketComponent = Annotated[
    TubeComponent | PointMassComponent | FinComponent,
    Field(discriminator="kind"),
]

__all__ = [
    "FinComponent",
    "PointMassComponent",
    "RocketComponent",
    "TubeComponent",
]
