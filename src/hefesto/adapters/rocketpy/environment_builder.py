"""RocketPy Environment builder: ERA5 NetCDF by default, optional ISA override."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Final

from rocketpy import Environment

from hefesto.domain import EnvironmentSpec, Era5DatasetKind, IsaAtmosphereSpec, NetCdfVariableMap

_ISA_LAPSE_RATE_K_PER_M: Final[float] = 0.0065
_ISA_TROPOPAUSE_M: Final[float] = 11_000.0
_ISA_MIN_TEMPERATURE_K: Final[float] = 150.0
_STANDARD_GRAVITY_M_S2: Final[float] = 9.80665
_SPECIFIC_GAS_CONSTANT_J_KG_K: Final[float] = 287.05
_ISA_PROFILE_POINTS: Final[int] = 241


def build_netcdf_dictionary(
    variable_map: NetCdfVariableMap,
    dataset_kind: Era5DatasetKind,
) -> dict[str, str | None]:
    """Translate NetCdfVariableMap into RocketPy's ERA5 variable dictionary."""
    mapping: dict[str, str | None] = {
        "time": variable_map.time,
        "latitude": variable_map.latitude,
        "longitude": variable_map.longitude,
        "level": variable_map.level,
        "temperature": variable_map.temperature,
        "surface_geopotential_height": variable_map.surface_geopotential_height,
        "geopotential_height": variable_map.geopotential_height,
        "geopotential": variable_map.geopotential,
        "u_wind": variable_map.u_wind,
        "v_wind": variable_map.v_wind,
    }
    if dataset_kind == Era5DatasetKind.ENDA:
        if not variable_map.ensemble_number or not variable_map.ensemble_number.strip():
            raise ValueError("variable_map.ensemble_number is required for ERA5 'enda' datasets")
        mapping["ensemble"] = variable_map.ensemble_number
    return mapping


def _resolve_nc_path(spec: EnvironmentSpec, atmosphere_path: Path | str | None) -> Path:
    if not spec.atmosphere_asset.lower().endswith(".nc"):
        raise ValueError(
            f"EnvironmentSpec.atmosphere_asset must reference a .nc file (no ISA fallback), "
            f"got {spec.atmosphere_asset!r}"
        )
    if atmosphere_path is None or (
        isinstance(atmosphere_path, str) and not atmosphere_path.strip()
    ):
        raise ValueError("atmosphere_path must be a non-empty .nc file path (no ISA fallback)")

    path = Path(atmosphere_path)
    if path.suffix.lower() != ".nc":
        raise ValueError(
            f"Only .nc NetCDF atmosphere files are supported (no ISA fallback), got {path!r}"
        )
    if not path.is_file():
        raise FileNotFoundError(f"NetCDF atmosphere file not found: {path}")
    return path


def build_isa_profiles(
    isa: IsaAtmosphereSpec,
    *,
    max_height_m: float,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Return (pressure, temperature) ISA profiles anchored at the configured elevation."""
    top_m = max(max_height_m, isa.elevation_m)
    tropopause_m = max(isa.elevation_m, _ISA_TROPOPAUSE_M)
    tropopause_temperature_k = max(
        isa.base_temperature_k - _ISA_LAPSE_RATE_K_PER_M * (_ISA_TROPOPAUSE_M - isa.elevation_m),
        _ISA_MIN_TEMPERATURE_K,
    )
    exponent = _STANDARD_GRAVITY_M_S2 / (
        _ISA_LAPSE_RATE_K_PER_M * _SPECIFIC_GAS_CONSTANT_J_KG_K
    )
    pressure: list[tuple[float, float]] = []
    temperature: list[tuple[float, float]] = []
    for index in range(_ISA_PROFILE_POINTS):
        height_m = top_m * index / (_ISA_PROFILE_POINTS - 1)
        if height_m <= tropopause_m:
            temp_k = max(
                isa.base_temperature_k
                - _ISA_LAPSE_RATE_K_PER_M * (height_m - isa.elevation_m),
                _ISA_MIN_TEMPERATURE_K,
            )
            pressure_pa = isa.base_pressure_pa * (temp_k / isa.base_temperature_k) ** exponent
        else:
            # Isothermal layer above the tropopause keeps the profile positive and monotonic.
            temp_k = tropopause_temperature_k
            pressure_pa = isa.base_pressure_pa * (
                tropopause_temperature_k / isa.base_temperature_k
            ) ** exponent * math.exp(
                -_STANDARD_GRAVITY_M_S2
                * (height_m - tropopause_m)
                / (_SPECIFIC_GAS_CONSTANT_J_KG_K * tropopause_temperature_k)
            )
        pressure.append((height_m, pressure_pa))
        temperature.append((height_m, temp_k))
    return pressure, temperature


def build_isa_wind(isa: IsaAtmosphereSpec) -> tuple[float, float]:
    """Convert (speed, azimuth blown towards) into RocketPy east/north wind components."""
    direction_rad = math.radians(isa.wind_direction_deg)
    return (
        isa.wind_speed_ms * math.sin(direction_rad),
        isa.wind_speed_ms * math.cos(direction_rad),
    )


def _build_isa_environment(spec: EnvironmentSpec, isa: IsaAtmosphereSpec) -> Environment:
    """Build a RocketPy Environment on a custom ISA profile (atmosphere_asset unused)."""
    env = Environment(
        date=spec.date_utc,
        latitude=spec.latitude_deg,
        longitude=spec.longitude_deg,
        elevation=isa.elevation_m,
        datum=spec.datum,
        timezone=spec.timezone,
        max_expected_height=spec.max_expected_height_m,
    )
    pressure, temperature = build_isa_profiles(isa, max_height_m=spec.max_expected_height_m)
    wind_u, wind_v = build_isa_wind(isa)
    env.set_atmospheric_model(
        type="custom_atmosphere",
        pressure=pressure,
        temperature=temperature,
        wind_u=[[0.0, wind_u]],
        wind_v=[[0.0, wind_v]],
    )
    return env


def build_environment(
    spec: EnvironmentSpec,
    atmosphere_path: Path | str | None = None,
    *,
    isa: IsaAtmosphereSpec | None = None,
) -> Environment:
    """Build a RocketPy Environment from an ERA5 .nc file, or from an optional ISA override."""
    if isa is not None:
        return _build_isa_environment(spec, isa)
    nc_path = _resolve_nc_path(spec, atmosphere_path)
    if spec.dataset_kind == Era5DatasetKind.OPER and spec.ensemble_member is not None:
        raise ValueError("ensemble_member must be None when dataset_kind is 'oper'")

    dictionary = build_netcdf_dictionary(spec.variable_map, spec.dataset_kind)
    env = Environment(
        date=spec.date_utc,
        latitude=spec.latitude_deg,
        longitude=spec.longitude_deg,
        elevation=spec.elevation_m,
        datum=spec.datum,
        timezone=spec.timezone,
        max_expected_height=spec.max_expected_height_m,
    )

    if spec.dataset_kind == Era5DatasetKind.OPER:
        env.set_atmospheric_model(type="Reanalysis", file=str(nc_path), dictionary=dictionary)
        return env

    env.set_atmospheric_model(type="Ensemble", file=str(nc_path), dictionary=dictionary)
    if spec.ensemble_member is not None:
        env.select_ensemble_member(spec.ensemble_member)
    return env


__all__ = [
    "build_environment",
    "build_isa_profiles",
    "build_isa_wind",
    "build_netcdf_dictionary",
]
