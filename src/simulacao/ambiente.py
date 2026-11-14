# src/simulacao/ambiente.py
"""Fábricas de `Environment` do RocketPy para simulações determinísticas e ensemble."""
from __future__ import annotations

from rocketpy import Environment

from src.caminhos import ATMOSFERA

_DIC_NC = {
    "time": "valid_time",
    "latitude": "latitude",
    "longitude": "longitude",
    "level": "pressure_level",
    "temperature": "t",
    "surface_geopotential_height": None,
    "geopotential_height": None,
    "geopotential": "z",
    "u_wind": "u",
    "v_wind": "v",
}


def _criar_ambiente_base() -> Environment:
    return Environment(
        date=(2026, 6, 15, 12),
        latitude=32.94019,
        longitude=-106.92056,
        elevation=1401,
    )


def build_irec() -> Environment:
    """Constrói o ambiente atmosférico nominal de Spaceport America (ERA5 Reanalysis)."""
    env = _criar_ambiente_base()
    env.set_atmospheric_model(
        type="Reanalysis",
        file=str(ATMOSFERA / "irec" / "data_stream-oper_stepType-instant.nc"),
        dictionary=_DIC_NC,
    )
    return env


def build_irec_ensemble() -> Environment:
    """Constrói o ambiente atmosférico Ensemble de Spaceport America (Monte Carlo)."""
    env = _criar_ambiente_base()
    env.set_atmospheric_model(
        type="Ensemble",
        file=str(ATMOSFERA / "irec" / "data_stream-enda_stepType-instantCerto.nc"),
        dictionary={"ensemble": "number", **_DIC_NC},
    )
    return env
