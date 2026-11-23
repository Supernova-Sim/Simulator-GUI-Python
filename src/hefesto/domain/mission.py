"""Mission presets, resolved mission specs, and catalog overview DTOs."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hefesto.domain._validators import (
    require_axisymmetric_inertia,
    require_burn_time,
    require_non_empty_text,
    require_relative_asset,
)
from hefesto.domain.aerodynamics import (
    DragCurveTable,
    DragSource,
    FinSetSpec,
    NoseConeSpec,
    ParachuteSpec,
    RailButtonsSpec,
    SurfaceFinish,
)
from hefesto.domain.components import RocketComponent
from hefesto.domain.environment import EnvironmentSpec
from hefesto.domain.motor import (
    GrainSpec,
    MotorCasingSpec,
    MotorOverride,
    NozzleSpec,
)
from hefesto.domain.rocket import FinGeometryMode, MassMode, RocketSpec
from hefesto.domain.safety import SafetyLimits


class AssetCategory(StrEnum):
    """Supported raw asset directories under data/assets/."""

    MOTORS = "motors"
    DRAG = "drag"
    ATMOSPHERE = "atmosphere"


class AssetEntry(BaseModel):
    """Catalog metadata for a single relative asset file."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    category: AssetCategory
    relative_path: str
    name: str
    file_format: str

    @field_validator("relative_path")
    @classmethod
    def _validate_relative_path(cls, value: str) -> str:
        return require_relative_asset(value, "relative_path")

    @field_validator("name", "file_format")
    @classmethod
    def _validate_texts(cls, value: str) -> str:
        return require_non_empty_text(value, "asset metadata")


class MotorPreset(BaseModel):
    """Catalog motor preset referencing relative motor/thrust assets."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: str
    motor_asset: str | None = None
    thrust_curve_asset: str | None = None
    casing: MotorCasingSpec
    grain_separation_m: float = Field(ge=0.0)
    grains_center_of_mass_m: float
    nozzle_position_m: float = 0.0
    propellant_name: str = "KNSB"
    overrides: tuple[MotorOverride, ...] = ()
    fallback_grains: tuple[GrainSpec, ...] = ()
    propellant_density_kg_m3: float | None = Field(default=None, gt=0.0)
    nozzle: NozzleSpec | None = None
    burn_time_s: tuple[float, float] | None = None

    @field_validator("name", "propellant_name")
    @classmethod
    def _validate_names(cls, value: str) -> str:
        return require_non_empty_text(value, "motor preset name")

    @field_validator("motor_asset", "thrust_curve_asset")
    @classmethod
    def _validate_assets(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_relative_asset(value, "motor preset asset")

    @field_validator("burn_time_s")
    @classmethod
    def _validate_burn_time(
        cls, value: tuple[float, float] | None
    ) -> tuple[float, float] | None:
        if value is None:
            return None
        return require_burn_time(value)

    @model_validator(mode="after")
    def _require_at_least_one_source(self) -> MotorPreset:
        if self.motor_asset is None and self.thrust_curve_asset is None:
            raise ValueError("MotorPreset requires motor_asset and/or thrust_curve_asset")
        return self


class RicMotorAsset(BaseModel):
    """Auto-discovered OpenMotor .ric motor without an equivalent catalog preset."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    preset_id: str
    name: str
    motor_asset: str
    warnings: tuple[str, ...] = ()

    @field_validator("preset_id", "name")
    @classmethod
    def _validate_texts(cls, value: str) -> str:
        return require_non_empty_text(value, "ric motor metadata")

    @field_validator("motor_asset")
    @classmethod
    def _validate_asset(cls, value: str) -> str:
        return require_relative_asset(value, "ric motor asset")


class RicMotorCacheEntry(BaseModel):
    """Cached .ric -> MotorPreset conversion keyed by path plus mtime/size/sha256."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    relative_path: str
    mtime_ns: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    sha256: str
    preset: MotorPreset | None = None
    warnings: tuple[str, ...] = ()


class RicMotorCache(BaseModel):
    """Persistent index written to data/cache/motors/discovery.json."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    version: int = Field(default=1, ge=1)
    entries: tuple[RicMotorCacheEntry, ...] = ()


class RocketPreset(BaseModel):
    """Catalog rocket preset referencing relative drag CSVs and motor preset name."""

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
    power_off_drag_asset: str
    power_on_drag_asset: str
    motor_preset_name: str
    drag_source: DragSource = "legacy_csv"
    surface_finish: SurfaceFinish = SurfaceFinish.REGULAR
    drag_table: DragCurveTable | None = None

    @field_validator("name", "motor_preset_name")
    @classmethod
    def _validate_names(cls, value: str) -> str:
        return require_non_empty_text(value, "rocket preset name")

    @field_validator("power_off_drag_asset", "power_on_drag_asset")
    @classmethod
    def _validate_drag_assets(cls, value: str) -> str:
        return require_relative_asset(value, "drag asset")

    @field_validator("inertia_kg_m2")
    @classmethod
    def _validate_inertia(
        cls, value: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        return require_axisymmetric_inertia(value, "inertia_kg_m2")

    @model_validator(mode="after")
    def _validate_drag_source(self) -> RocketPreset:
        if self.drag_source == "ork_sim" and self.drag_table is None:
            raise ValueError(
                "drag_source='ork_sim' requires drag_table extracted from the .ork flight data"
            )
        if self.drag_source != "ork_sim" and self.drag_table is not None:
            raise ValueError(
                f"drag_table is only valid for drag_source='ork_sim', got {self.drag_source!r}"
            )
        return self


class LaunchConfig(BaseModel):
    """Launch rail orientation and 6-DOF numerical solver parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    inclination_deg: float = Field(default=88.0, gt=0.0, le=90.0)
    heading_deg: float = Field(default=90.0, ge=0.0, lt=360.0)
    rail_length_m: float = Field(default=6.0, gt=0.0)
    max_time_s: float = Field(default=600.0, gt=0.0)
    terminate_on_apogee: bool = False
    rtol: float = Field(default=1e-6, gt=0.0)
    ode_solver: Literal["LSODA", "RK45", "DOP853"] = "LSODA"


class IsaAtmosphereSpec(BaseModel):
    """Optional ISA atmosphere override used instead of the site's ERA5 NetCDF file."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    type: Literal["isa"] = "isa"
    elevation_m: float = Field(ge=-500.0, le=9000.0)
    base_temperature_k: float = Field(gt=0.0, le=1000.0)
    base_pressure_pa: float = Field(gt=0.0, le=200_000.0)
    wind_speed_ms: float = Field(default=0.0, ge=0.0, le=200.0)
    # Azimuth the wind blows towards (OpenRocket .ork convention), degrees from North.
    wind_direction_deg: float = Field(default=0.0, ge=0.0, lt=360.0)


class MissionPreset(BaseModel):
    """Catalog mission preset linking rocket and environment presets."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: str
    rocket_preset_name: str
    environment_preset_name: str
    launch: LaunchConfig = Field(default_factory=LaunchConfig)
    safety_limits: SafetyLimits = Field(default_factory=SafetyLimits)
    atmosphere: IsaAtmosphereSpec | None = None

    @field_validator("name", "rocket_preset_name", "environment_preset_name")
    @classmethod
    def _validate_names(cls, value: str) -> str:
        return require_non_empty_text(value, "mission preset name")


class MissionSpec(BaseModel):
    """Resolved in-memory mission ready for physics execution."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: str
    rocket: RocketSpec
    environment: EnvironmentSpec
    launch: LaunchConfig = Field(default_factory=LaunchConfig)
    safety_limits: SafetyLimits = Field(default_factory=SafetyLimits)
    atmosphere: IsaAtmosphereSpec | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_non_empty_text(value, "name")


class OutputSelection(BaseModel):
    """Boolean selector controlling which trajectory curves are extracted into FlightResult."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    x: bool = False
    y: bool = False
    altitude_agl: bool = False
    speed: bool = False
    vertical_velocity: bool = False
    acceleration: bool = False
    mach: bool = False
    cg: bool = False
    cp: bool = False
    static_margin: bool = False
    drag: bool = False
    thrust: bool = False

    @classmethod
    def all(cls) -> OutputSelection:
        """Enable extraction of all trajectory and aerodynamic curves."""
        return cls(
            x=True,
            y=True,
            altitude_agl=True,
            speed=True,
            vertical_velocity=True,
            acceleration=True,
            mach=True,
            cg=True,
            cp=True,
            static_margin=True,
            drag=True,
            thrust=True,
        )

    @classmethod
    def none(cls) -> OutputSelection:
        """Disable all optional trajectory curves (scalar metrics only)."""
        return cls()


class SimulationConfig(BaseModel):
    """Picklable end-to-end simulation configuration consumed by services and UI."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    mission: MissionSpec
    mass_mode: MassMode = "calculated"
    fin_geometry_mode: FinGeometryMode = "freeform"
    drag_factor: float = Field(default=1.0, gt=0.0)
    thrust_factor: float = Field(default=1.0, gt=0.0)
    motor_overrides: tuple[MotorOverride, ...] = ()
    output_selection: OutputSelection = Field(default_factory=OutputSelection.all)

    @model_validator(mode="after")
    def _validate_measured_mass_mode(self) -> SimulationConfig:
        if self.mass_mode == "measured" and self.mission.rocket.dry_mass_override_kg is None:
            raise ValueError(
                "SimulationConfig with mass_mode='measured' requires "
                "mission.rocket.dry_mass_override_kg to be set"
            )
        return self


class CatalogOverview(BaseModel):
    """Summary DTO of available assets and presets returned by storage/services."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: int = Field(default=1, ge=1)
    assets: tuple[AssetEntry, ...] = ()
    motor_presets: tuple[str, ...] = ()
    discovered_ric_motors: tuple[RicMotorAsset, ...] = ()
    rocket_presets: tuple[str, ...] = ()
    environment_presets: tuple[str, ...] = ()
    mission_presets: tuple[str, ...] = ()

    @field_validator(
        "motor_presets", "rocket_presets", "environment_presets", "mission_presets"
    )
    @classmethod
    def _validate_preset_names(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(require_non_empty_text(item, "preset name") for item in values)

    def assets_for(self, category: AssetCategory) -> tuple[AssetEntry, ...]:
        return tuple(entry for entry in self.assets if entry.category == category)


__all__ = [
    "AssetCategory",
    "AssetEntry",
    "CatalogOverview",
    "IsaAtmosphereSpec",
    "LaunchConfig",
    "MissionPreset",
    "MissionSpec",
    "MotorPreset",
    "OutputSelection",
    "RicMotorAsset",
    "RicMotorCache",
    "RicMotorCacheEntry",
    "RocketPreset",
    "SimulationConfig",
]
