"""Internal ballistics, 6-DOF flight results, simulation results, and RunSummary DTO."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from hefesto.domain._validators import (
    require_burn_time,
    require_non_empty_text,
    require_relative_asset,
    require_xy_curve,
)
from hefesto.domain.environment import EnvironmentSpec
from hefesto.domain.mission import AssetEntry, SimulationConfig
from hefesto.domain.motor import GrainSpec, MotorCasingSpec, MotorOverride, NozzleSpec
from hefesto.domain.rocket import FinGeometryMode, MassMode
from hefesto.domain.safety import SafetyLimits, SafetyReport


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
    rocket_draw_png_b64: str | None = None

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
    executed_config: SimulationConfig | None = None

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


class MotorPhysicalSummary(BaseModel):
    """Combined physical casing, nozzle, and internal ballistics summary for display."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    motor_name: str
    dry_mass_kg: float = Field(gt=0.0)
    propellant_mass_kg: float = Field(gt=0.0)
    total_loaded_mass_kg: float = Field(gt=0.0)
    propellant_mass_fraction: float = Field(gt=0.0, lt=1.0)
    casing_length_m: float = Field(gt=0.0)
    outer_diameter_m: float = Field(gt=0.0)
    throat_diameter_mm: float = Field(gt=0.0)
    exit_diameter_mm: float = Field(gt=0.0)
    expansion_ratio: float = Field(gt=0.0)
    burn_time_s: tuple[float, float]
    burn_duration_s: float = Field(gt=0.0)
    total_impulse_ns: float = Field(ge=0.0)
    average_thrust_n: float = Field(ge=0.0)
    max_thrust_n: float = Field(ge=0.0)
    peak_chamber_pressure_pa: float | None = Field(default=None, ge=0.0)
    peak_kn: float | None = Field(default=None, ge=0.0)
    peak_mass_flux_kg_m2_s: float | None = Field(default=None, ge=0.0)
    delivered_isp_s: float | None = Field(default=None, ge=0.0)
    aft_port_to_throat_ratio: float | None = Field(default=None, ge=0.0)
    min_port_to_throat_ratio: float | None = Field(default=None, ge=0.0)
    grain_count: int = Field(ge=1)
    propellant_density_kg_m3: float = Field(gt=0.0)

    @field_validator("motor_name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_non_empty_text(value, "motor_name")

    @field_validator("burn_time_s")
    @classmethod
    def _validate_burn_time(cls, value: tuple[float, float]) -> tuple[float, float]:
        return require_burn_time(value)


class SavedMotorInspection(BaseModel):
    """Typed inspection summary of a saved catalog MotorPreset and its .ric/.eng source."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    preset_id: str
    name: str
    source_kind: Literal["ric_and_eng", "ric_only", "eng_only"]
    motor_asset: str | None = None
    thrust_curve_asset: str | None = None
    casing: MotorCasingSpec
    casing_outer_diameter_m: float = Field(gt=0.0)
    propellant_name: str
    propellant_density_kg_m3: float = Field(gt=0.0)
    nozzle: NozzleSpec
    grains: tuple[GrainSpec, ...] = Field(min_length=1)
    grain_separation_m: float = Field(ge=0.0)
    grains_center_of_mass_m: float
    preset_overrides: tuple[MotorOverride, ...] = ()

    @field_validator("preset_id", "name", "propellant_name")
    @classmethod
    def _validate_texts(cls, value: str) -> str:
        return require_non_empty_text(value, "saved motor inspection text")


class SavedRocketInspection(BaseModel):
    """Typed structural inspection summary of a saved catalog RocketPreset."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    preset_id: str
    name: str
    motor_preset_name: str
    radius_m: float = Field(gt=0.0)
    calculated_dry_mass_kg: float = Field(gt=0.0)
    dry_mass_override_kg: float | None = Field(default=None, gt=0.0)
    center_of_mass_without_motor_m: float = Field(gt=0.0)
    inertia_kg_m2: tuple[float, float, float]
    motor_position_m: float = Field(gt=0.0)
    tube_count: int = Field(ge=0)
    point_mass_count: int = Field(ge=0)
    fin_count: int = Field(ge=1)
    fin_position_m: float
    nose_cone_kind: str
    nose_cone_length_m: float = Field(gt=0.0)
    parachute_names: tuple[str, ...] = ()
    power_off_drag_asset: str
    power_on_drag_asset: str
    components_summary: tuple[str, ...] = ()

    @field_validator("preset_id", "name", "motor_preset_name", "nose_cone_kind")
    @classmethod
    def _validate_texts(cls, value: str) -> str:
        return require_non_empty_text(value, "saved rocket inspection text")


class NamedSitePreset(BaseModel):
    """Catalog EnvironmentSpec paired with its preset identifier."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    preset_id: str
    spec: EnvironmentSpec

    @field_validator("preset_id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return require_non_empty_text(value, "preset_id")


class NamedSafetyLimitsPreset(BaseModel):
    """Catalog SafetyLimits paired with its preset identifier."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    preset_id: str
    limits: SafetyLimits

    @field_validator("preset_id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return require_non_empty_text(value, "preset_id")


class CatalogDatabaseInspection(BaseModel):
    """Complete typed snapshot of catalog presets, raw assets, and saved runs."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    motors: tuple[SavedMotorInspection, ...] = ()
    rockets: tuple[SavedRocketInspection, ...] = ()
    sites: tuple[NamedSitePreset, ...] = ()
    limits: tuple[NamedSafetyLimitsPreset, ...] = ()
    assets: tuple[AssetEntry, ...] = ()
    runs: tuple[RunSummary, ...] = ()
    invalid_run_snapshots: tuple[str, ...] = ()


class AppliedOverrideAudit(BaseModel):
    """Audit entry comparing base .ric parameter value against applied MotorOverride."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    path: str
    label: str
    unit: str
    source: Literal["preset", "runtime"] = "runtime"
    base_value: float | int | str | None = None
    applied_value: float | int | str
    changed: bool = True

    @field_validator("path", "label", "unit")
    @classmethod
    def _validate_texts(cls, value: str) -> str:
        return require_non_empty_text(value, "applied override audit text")


class ExecutionAuditReport(BaseModel):
    """Detailed 'Saved Preset vs. Executed Snapshot' audit report for a simulation run."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    run_id: str
    mission_name: str
    motor_preset_id: str
    motor_source_kind: Literal["ric_and_eng", "ric_only", "eng_only"]
    motor_asset: str | None = None
    thrust_curve_asset: str | None = None
    applied_overrides: tuple[AppliedOverrideAudit, ...] = ()
    effective_grains: tuple[GrainSpec, ...] = ()
    motor_summary: MotorPhysicalSummary | None = None
    rocket_name: str
    rocket_preset_id: str | None = None
    rocket_modified_in_session: bool = False
    rocket_modification_notes: tuple[str, ...] = ()
    mass_mode: MassMode = "calculated"
    effective_dry_mass_kg: float = Field(gt=0.0)
    dry_mass_override_kg: float | None = None
    fin_geometry_mode: FinGeometryMode = "freeform"
    drag_factor: float = Field(default=1.0, gt=0.0)
    thrust_factor: float = Field(default=1.0, gt=0.0)
    environment_name: str = ""
    atmosphere_asset: str = ""
    components_summary: tuple[str, ...] = ()
    fins_summary: str = ""

    @field_validator("run_id", "mission_name", "motor_preset_id", "rocket_name")
    @classmethod
    def _validate_texts(cls, value: str) -> str:
        return require_non_empty_text(value, "execution audit text")

    @field_validator("rocket_preset_id")
    @classmethod
    def _validate_optional_rocket_preset_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_non_empty_text(value, "rocket_preset_id")


__all__ = [
    "AppliedOverrideAudit",
    "BallisticsResult",
    "CatalogDatabaseInspection",
    "ExecutionAuditReport",
    "FlightResult",
    "MotorPhysicalSummary",
    "NamedSafetyLimitsPreset",
    "NamedSitePreset",
    "RunSummary",
    "SavedMotorInspection",
    "SavedRocketInspection",
    "SimulationResult",
]
