"""Aerodynamic surfaces, recovery parachutes, rail buttons, and drag curves."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hefesto.domain._validators import (
    require_non_empty_text,
    require_relative_asset,
    require_xy_curve,
)
from hefesto.domain.components import PointMassComponent

# Where a rocket's power_off/power_on Cd(Mach) pair comes from.
DragSource = Literal["analytical", "ork_sim", "rasaero_csv", "legacy_csv"]


class SurfaceFinish(StrEnum):
    """Manufacturing surface finish used to bound the turbulent skin-friction coefficient."""

    SMOOTH = "smooth"
    REGULAR = "regular"
    ROUGH = "rough"
    UNFINISHED = "unfinished"


# Equivalent sand-grain roughness per finish (metres).
SURFACE_ROUGHNESS_M: Final[dict[SurfaceFinish, float]] = {
    SurfaceFinish.SMOOTH: 20e-6,
    SurfaceFinish.REGULAR: 60e-6,
    SurfaceFinish.ROUGH: 150e-6,
    SurfaceFinish.UNFINISHED: 250e-6,
}


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
    # Haack series C: None keeps the profile default (0 for Von Karman, 1/3 for LV-Haack).
    haack_parameter: float | None = Field(default=None, ge=0.0, le=1.0)
    base_radius_m: float | None = Field(default=None, gt=0.0)
    name: str = "Nose Cone"
    # Imported nose shell as a lumped mass; presets carrying it in `components` leave it None.
    shell: PointMassComponent | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_non_empty_text(value, "name")


def validate_nose_cone_shell_thickness(wall_thickness_m: float, base_radius_m: float) -> None:
    """Reject a nose shell whose wall leaves no hollow cavity (same guard as a tube)."""
    if not (math.isfinite(wall_thickness_m) and math.isfinite(base_radius_m)):
        raise ValueError(
            f"nose shell thickness/base radius must be finite, got "
            f"{wall_thickness_m!r}/{base_radius_m!r}"
        )
    if wall_thickness_m < 0.0:
        raise ValueError(f"wall_thickness_m must be >= 0, got {wall_thickness_m!r}")
    if base_radius_m <= 0.0:
        raise ValueError(f"base_radius_m must be > 0, got {base_radius_m!r}")
    if wall_thickness_m >= base_radius_m:
        raise ValueError(
            f"nose shell thickness_m ({wall_thickness_m}) must be less than "
            f"base_radius_m ({base_radius_m})"
        )


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


def _require_strictly_increasing(values: list[float], name: str, *, minimum: float) -> None:
    previous: float | None = None
    for idx, value in enumerate(values):
        if not math.isfinite(value) or value < minimum:
            raise ValueError(f"{name}[{idx}] must be finite and >= {minimum}, got {value!r}")
        if previous is not None and value <= previous:
            raise ValueError(f"{name} must strictly increase at [{idx}]: {previous} -> {value}")
        previous = value


def _require_non_negative(values: list[float], name: str) -> None:
    for idx, value in enumerate(values):
        if not math.isfinite(value) or value < 0.0:
            raise ValueError(f"{name}[{idx}] must be finite and >= 0, got {value!r}")


class DragCurveTable(BaseModel):
    """Mach-indexed axial Cd table with an optional RASAero II angle-of-attack grid."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    mach: list[float] = Field(min_length=2)
    cd_power_off: list[float] = Field(min_length=2)
    cd_power_on: list[float] = Field(min_length=2)
    source: str
    alpha_deg: list[float] = Field(default_factory=list)
    cd_alpha_power_off: list[list[float]] = Field(default_factory=list)
    cd_alpha_power_on: list[list[float]] = Field(default_factory=list)

    @field_validator("source")
    @classmethod
    def _validate_source(cls, value: str) -> str:
        return require_non_empty_text(value, "source")

    @model_validator(mode="after")
    def _validate_curves(self) -> DragCurveTable:
        _require_strictly_increasing(self.mach, "mach", minimum=0.0)
        for name, values in (
            ("cd_power_off", self.cd_power_off),
            ("cd_power_on", self.cd_power_on),
        ):
            if len(values) != len(self.mach):
                raise ValueError(
                    f"{name} has {len(values)} values but mach has {len(self.mach)}"
                )
            _require_non_negative(values, name)

        rows_by_name = (
            ("cd_alpha_power_off", self.cd_alpha_power_off),
            ("cd_alpha_power_on", self.cd_alpha_power_on),
        )
        if not self.alpha_deg:
            if any(rows for _, rows in rows_by_name):
                raise ValueError("angle-of-attack Cd rows require an alpha_deg grid")
            return self

        _require_strictly_increasing(self.alpha_deg, "alpha_deg", minimum=-180.0)
        for name, rows in rows_by_name:
            if len(rows) != len(self.alpha_deg):
                raise ValueError(
                    f"{name} has {len(rows)} rows but alpha_deg has {len(self.alpha_deg)}"
                )
            for alpha, row in zip(self.alpha_deg, rows, strict=True):
                if len(row) != len(self.mach):
                    raise ValueError(
                        f"{name} row alpha={alpha} has {len(row)} values but mach has "
                        f"{len(self.mach)}"
                    )
                _require_non_negative(row, f"{name}[alpha={alpha}]")
        return self

    def to_specs(self) -> tuple[DragCurveSpec, DragCurveSpec]:
        """Return the axial (power_off, power_on) DragCurveSpec pair for RocketPy assembly."""
        return (
            DragCurveSpec(points=tuple(zip(self.mach, self.cd_power_off, strict=True))),
            DragCurveSpec(points=tuple(zip(self.mach, self.cd_power_on, strict=True))),
        )


__all__ = [
    "SURFACE_ROUGHNESS_M",
    "DragCurveSpec",
    "DragCurveTable",
    "DragSource",
    "FinSetSpec",
    "NoseConeKind",
    "NoseConeSpec",
    "ParachuteSpec",
    "RailButtonsSpec",
    "SurfaceFinish",
    "validate_nose_cone_shell_thickness",
]
