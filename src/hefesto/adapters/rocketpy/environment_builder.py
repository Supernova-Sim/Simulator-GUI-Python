"""NetCDF-only RocketPy Environment builder without ISA fallback."""

from __future__ import annotations

from pathlib import Path

from rocketpy import Environment

from hefesto.domain import EnvironmentSpec, Era5DatasetKind, NetCdfVariableMap


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


def _resolve_nc_path(spec: EnvironmentSpec, atmosphere_path: Path | str) -> Path:
    if not spec.atmosphere_asset.lower().endswith(".nc"):
        raise ValueError(
            f"EnvironmentSpec.atmosphere_asset must reference a .nc file (no ISA fallback), "
            f"got {spec.atmosphere_asset!r}"
        )
    if isinstance(atmosphere_path, str) and not atmosphere_path.strip():
        raise ValueError("atmosphere_path must be a non-empty .nc file path (no ISA fallback)")

    path = Path(atmosphere_path)
    if path.suffix.lower() != ".nc":
        raise ValueError(
            f"Only .nc NetCDF atmosphere files are supported (no ISA fallback), got {path!r}"
        )
    if not path.is_file():
        raise FileNotFoundError(f"NetCDF atmosphere file not found: {path}")
    return path


def build_environment(
    spec: EnvironmentSpec,
    atmosphere_path: Path | str,
) -> Environment:
    """Build a RocketPy Environment backed strictly by an ERA5 .nc file (no ISA fallback)."""
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
    "build_netcdf_dictionary",
]
