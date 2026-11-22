"""Internal ballistics, 6-DOF flight results, simulation results, and RunSummary DTO."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from hefesto.domain._validators import (
    require_burn_time,
    require_non_empty_text,
    require_relative_asset,
    require_xy_curve,
)
from hefesto.domain.motor import GrainSpec
from hefesto.domain.safety import SafetyReport


def _validate_optional_series(
    points: tuple[tuple[float, float], ...],
    y_name: str,
) -> tuple[tuple[float, float], ...]:
    if not points:
        return ()
    return require_xy_curve(
        points,
        x_name="time_s",
        y_name=y_name,
        min_points=1,
        min_x=0.0,
        min_y=None,
        strict_x=False,
    )


class BallisticsResult(BaseModel):
    """Internal ballistics outputs produced by the OpenMotor adapter."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    motor_name: str
    grains: tuple[GrainSpec, ...] = Field(min_length=1)
    propellant_density_kg_m3: float = Field(gt=0.0)
    throat_radius_m: float = Field(gt=0.0)
    nozzle_exit_radius_m: float = Field(gt=0.0)
    burn_time_s: tuple[float, float]
    total_impulse_ns: float = Field(ge=0.0)
    max_thrust_n: float = Field(ge=0.0)
    propellant_mass_kg: float = Field(gt=0.0)
    peak_chamber_pressure_pa: float = Field(ge=0.0)
    peak_kn: float = Field(ge=0.0)
    peak_mass_flux_kg_m2_s: float = Field(ge=0.0)
    delivered_isp_s: float | None = Field(default=None, ge=0.0)
    aft_port_to_throat_ratio: float | None = Field(default=None, ge=0.0)
    min_port_to_throat_ratio: float | None = Field(default=None, ge=0.0)
    thrust_curve: tuple[tuple[float, float], ...]
    pressure_curve: tuple[tuple[float, float], ...] = ()
    kn_curve: tuple[tuple[float, float], ...] = ()

    @field_validator("motor_name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_non_empty_text(value, "motor_name")

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

    @field_validator("pressure_curve")
    @classmethod
    def _validate_pressure_curve(
        cls, value: tuple[tuple[float, float], ...]
    ) -> tuple[tuple[float, float], ...]:
        return _validate_optional_series(value, "pressure_pa")

    @field_validator("kn_curve")
    @classmethod
    def _validate_kn_curve(
        cls, value: tuple[tuple[float, float], ...]
    ) -> tuple[tuple[float, float], ...]:
        return _validate_optional_series(value, "kn")


class FlightResult(BaseModel):
    """6-DOF RocketPy trajectory summary metrics and optional time-series curves."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    apogee_agl_m: float
    apogee_msl_m: float
    apogee_time_s: float = Field(ge=0.0)
    flight_time_s: float = Field(ge=0.0)
    max_speed_ms: float = Field(ge=0.0)
    max_mach: float = Field(ge=0.0)
    rail_exit_velocity_ms: float = Field(ge=0.0)
    min_static_margin_calibers: float
    max_static_margin_calibers: float | None = None
    total_impulse_ns: float = Field(ge=0.0)
    dry_mass_kg: float = Field(gt=0.0)
    landing_velocity_ms: float | None = Field(default=None, ge=0.0)
    impact_distance_m: float | None = Field(default=None, ge=0.0)
    x_series: tuple[tuple[float, float], ...] = ()
    y_series: tuple[tuple[float, float], ...] = ()
    altitude_agl_series: tuple[tuple[float, float], ...] = ()
    speed_series: tuple[tuple[float, float], ...] = ()
    vertical_velocity_series: tuple[tuple[float, float], ...] = ()
    acceleration_series: tuple[tuple[float, float], ...] = ()
    mach_series: tuple[tuple[float, float], ...] = ()
    cg_series: tuple[tuple[float, float], ...] = ()
    cp_series: tuple[tuple[float, float], ...] = ()
    static_margin_series: tuple[tuple[float, float], ...] = ()
    drag_series: tuple[tuple[float, float], ...] = ()
    power_off_drag_curve: tuple[tuple[float, float], ...] = ()
    power_on_drag_curve: tuple[tuple[float, float], ...] = ()
    thrust_series: tuple[tuple[float, float], ...] = ()

    @field_validator(
        "x_series",
        "y_series",
        "altitude_agl_series",
        "speed_series",
        "vertical_velocity_series",
        "acceleration_series",
        "mach_series",
        "cg_series",
        "cp_series",
        "static_margin_series",
        "drag_series",
        "thrust_series",
    )
    @classmethod
    def _validate_time_series_fields(
        cls,
        value: tuple[tuple[float, float], ...],
        info: ValidationInfo,
    ) -> tuple[tuple[float, float], ...]:
        return _validate_optional_series(value, info.field_name or "series")

    @field_validator("power_off_drag_curve", "power_on_drag_curve")
    @classmethod
    def _validate_drag_curves(
        cls, value: tuple[tuple[float, float], ...]
    ) -> tuple[tuple[float, float], ...]:
        if not value:
            return ()
        return require_xy_curve(
            value,
            x_name="mach",
            y_name="cd",
            min_points=2,
            min_x=0.0,
            min_y=0.0,
            strict_x=True,
        )


class RunSummary(BaseModel):
    """Compact summary DTO for run history listings without full trajectory curves."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    run_id: str
    created_at_utc: datetime
    mission_name: str
    motor_name: str
    apogee_agl_m: float
    max_mach: float = Field(ge=0.0)
    min_static_margin_calibers: float
    safety_passed: bool | None = None
    snapshot_asset: str | None = None

    @field_validator("run_id", "mission_name", "motor_name")
    @classmethod
    def _validate_texts(cls, value: str) -> str:
        return require_non_empty_text(value, "run summary text")

    @field_validator("snapshot_asset")
    @classmethod
    def _validate_snapshot_asset(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_relative_asset(value, "snapshot_asset")


class SimulationResult(BaseModel):
    """Full simulation run bundle combining flight, ballistics, and safety reports."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    run_id: str
    created_at_utc: datetime
    mission_name: str
    motor_name: str
    flight: FlightResult
    ballistics: BallisticsResult | None = None
    safety: SafetyReport | None = None

    @field_validator("run_id", "mission_name", "motor_name")
    @classmethod
    def _validate_texts(cls, value: str) -> str:
        return require_non_empty_text(value, "simulation result text")

    def to_summary(self, snapshot_asset: str | None = None) -> RunSummary:
        return RunSummary(
            run_id=self.run_id,
            created_at_utc=self.created_at_utc,
            mission_name=self.mission_name,
            motor_name=self.motor_name,
            apogee_agl_m=self.flight.apogee_agl_m,
            max_mach=self.flight.max_mach,
            min_static_margin_calibers=self.flight.min_static_margin_calibers,
            safety_passed=self.safety.all_passed if self.safety is not None else None,
            snapshot_asset=snapshot_asset,
        )


__all__ = [
    "BallisticsResult",
    "FlightResult",
    "RunSummary",
    "SimulationResult",
]
