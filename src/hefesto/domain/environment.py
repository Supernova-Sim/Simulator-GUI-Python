"""Atmospheric and launch site specification (.nc-only ERA5 without ISA fallback)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hefesto.domain._validators import require_non_empty_text, require_relative_asset


class Era5DatasetKind(StrEnum):
    """Supported ERA5 NetCDF dataset variants."""

    OPER = "oper"
    ENDA = "enda"


class NetCdfVariableMap(BaseModel):
    """Typed mapping of ERA5 NetCDF variable names expected by RocketPy."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    time: str = "valid_time"
    latitude: str = "latitude"
    longitude: str = "longitude"
    level: str = "pressure_level"
    temperature: str = "t"
    surface_geopotential_height: str | None = None
    geopotential_height: str | None = None
    geopotential: str | None = "z"
    u_wind: str = "u"
    v_wind: str = "v"
    ensemble_number: str | None = "number"


class EnvironmentSpec(BaseModel):
    """Launch site and NetCDF-only atmospheric reanalysis specification."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: str = "Spaceport America (IREC)"
    atmosphere_asset: str
    dataset_kind: Era5DatasetKind = Era5DatasetKind.OPER
    ensemble_member: int | None = Field(default=None, ge=0)
    date_utc: tuple[int, int, int, int]
    latitude_deg: float = Field(ge=-90.0, le=90.0)
    longitude_deg: float = Field(ge=-180.0, le=180.0)
    elevation_m: float = Field(ge=-500.0, le=9000.0)
    datum: str = "SIRGAS2000"
    timezone: str = "UTC"
    max_expected_height_m: float = Field(default=80000.0, gt=0.0)
    variable_map: NetCdfVariableMap = Field(default_factory=NetCdfVariableMap)

    @field_validator("name", "datum", "timezone")
    @classmethod
    def _validate_texts(cls, value: str) -> str:
        return require_non_empty_text(value, "text")

    @field_validator("atmosphere_asset")
    @classmethod
    def _validate_nc_asset(cls, value: str) -> str:
        cleaned = require_relative_asset(value, "atmosphere_asset")
        if not cleaned.lower().endswith(".nc"):
            raise ValueError(
                f"atmosphere_asset must reference a .nc NetCDF file (no ISA fallback), "
                f"got {value!r}"
            )
        return cleaned

    @field_validator("date_utc")
    @classmethod
    def _validate_date_utc(cls, value: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        year, month, day, hour = value
        datetime(year, month, day, hour)
        return value

    @model_validator(mode="after")
    def _validate_ensemble_for_kind(self) -> EnvironmentSpec:
        if self.dataset_kind == Era5DatasetKind.OPER and self.ensemble_member is not None:
            raise ValueError("ensemble_member must be None when dataset_kind is 'oper'")
        return self


__all__ = [
    "EnvironmentSpec",
    "Era5DatasetKind",
    "NetCdfVariableMap",
]
