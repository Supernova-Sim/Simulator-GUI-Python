"""Typed OpenRocket (.ork) import intermediate and summary domain models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hefesto.domain._validators import (
    require_axisymmetric_inertia,
    require_non_empty_text,
)
from hefesto.domain.aerodynamics import (
    FinSetSpec,
    NoseConeSpec,
    ParachuteSpec,
    RailButtonsSpec,
)
from hefesto.domain.components import RocketComponent
from hefesto.domain.rocket import RocketSpec


class OrkImportWarning(BaseModel):
    """Structured diagnostic message emitted during OpenRocket XML parsing or import."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    severity: Literal["info", "warning"]
    component_name: str
    message: str

    @field_validator("component_name", "message")
    @classmethod
    def _validate_texts(cls, value: str) -> str:
        return require_non_empty_text(value, "warning text")


class OrkParsedDesign(BaseModel):
    """Typed intermediate representation extracted from an OpenRocket (.ork) XML document."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    rocket_name: str
    source_sha256: str
    radius_m: float = Field(gt=0.0)
    nose_cone: NoseConeSpec
    nose_cone_wall_thickness_m: float | None = Field(default=None, ge=0.0)
    nose_cone_density_kg_m3: float | None = Field(default=None, gt=0.0)
    nose_cone_override_mass_kg: float | None = Field(default=None, gt=0.0)
    nose_cone_override_cg_m: float | None = Field(default=None, ge=0.0)
    components: tuple[RocketComponent, ...] = Field(min_length=1)
    fins: FinSetSpec
    rail_buttons: RailButtonsSpec
    parachutes: tuple[ParachuteSpec, ...] = ()
    detected_motor_mount_position_m: float | None = Field(default=None, gt=0.0)
    embedded_rse_names: tuple[str, ...] = ()
    stored_datapoint_count: int = Field(default=0, ge=0)
    has_mass_or_cg_overrides: bool = False
    warnings: tuple[OrkImportWarning, ...] = ()

    @field_validator("rocket_name", "source_sha256")
    @classmethod
    def _validate_texts(cls, value: str) -> str:
        return require_non_empty_text(value, "openrocket design metadata")


class OrkImportSummary(BaseModel):
    """UI-ready summary of a previewed or persisted OpenRocket import."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    rocket_id: str | None = None
    rocket_spec: RocketSpec
    calculated_dry_mass_kg: float = Field(gt=0.0)
    center_of_mass_without_motor_m: float = Field(gt=0.0)
    inertia_kg_m2: tuple[float, float, float]
    from_cache: bool = False
    source_sha256: str
    embedded_rse_names: tuple[str, ...] = ()
    stored_datapoint_count: int = Field(default=0, ge=0)
    has_mass_or_cg_overrides: bool = False
    warnings: tuple[OrkImportWarning, ...] = ()

    @field_validator("source_sha256")
    @classmethod
    def _validate_sha(cls, value: str) -> str:
        return require_non_empty_text(value, "source_sha256")

    @field_validator("inertia_kg_m2")
    @classmethod
    def _validate_inertia(
        cls, value: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        return require_axisymmetric_inertia(value, "inertia_kg_m2")


__all__ = [
    "OrkImportSummary",
    "OrkImportWarning",
    "OrkParsedDesign",
]
