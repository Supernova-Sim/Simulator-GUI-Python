# configs/foguetes/hefesto/motor_variacoes.py
"""Variações exploratórias do motor Medusa do Hefesto.

Separação:
  - `configs/foguetes/hefesto/motor.py` → motor OFICIAL (`MOTOR_IREC`)
  - este arquivo                        → presets e fábrica de variações (`VARIACOES`)
"""
from __future__ import annotations

import dataclasses
from typing import Any

from configs.foguetes.hefesto.motor import MOTOR_IREC
from src.calculos.motorlib_variacoes import validar_overrides
from src.specs import MotorSpec

PARAMS_LIVRES: set[str] = {
    # Geometria dos grãos
    "grains.*.properties.coreDiameter",
    "grains.*.properties.length",
    "grains.*.properties.inhibitedEnds",
    # Tubeira
    "nozzle.throat",
    "nozzle.exit",
    "nozzle.divAngle",
    "nozzle.convAngle",
    "nozzle.throatLength",
    "nozzle.efficiency",
    # Simulação
    "config.timestep",
    "config.ambPressure",
}


def criar_variacao(
    overrides: dict[str, Any],
    *,
    nome: str | None = None,
) -> MotorSpec:
    """Cria um `MotorSpec` do Hefesto com `overrides` validados contra `PARAMS_LIVRES`."""
    validar_overrides(overrides, PARAMS_LIVRES)
    nome_final = nome or f"{MOTOR_IREC.nome} (var {len(overrides)}p)"
    return dataclasses.replace(
        MOTOR_IREC,
        overrides=dict(overrides),
        nome=nome_final,
    )


# 1. Garganta estreitada (−6%) — aumenta P0 e Kn
MOTOR_THROAT_ESTREITO = criar_variacao(
    {"nozzle.throat": 0.034 * 0.94},
    nome="Medusa (throat −6%)",
)

# 2. Garganta alargada (+6%) — reduz P0, aumenta margem de FS
MOTOR_THROAT_LARGO = criar_variacao(
    {"nozzle.throat": 0.034 * 1.06},
    nome="Medusa (throat +6%)",
)

# 3. Todos os grãos com core uniforme de 45mm
MOTOR_CORE_UNIFORME = criar_variacao(
    {"grains.*.properties.coreDiameter": 0.045},
    nome="Medusa (core 45mm unif.)",
)

# 4. Só os 4 primeiros grãos com core menor (grãos traseiros ficam 54mm)
MOTOR_CORE_FWD_MENOR = criar_variacao(
    {
        "grains.0.properties.coreDiameter": 0.038,
        "grains.1.properties.coreDiameter": 0.038,
        "grains.2.properties.coreDiameter": 0.038,
        "grains.3.properties.coreDiameter": 0.038,
    },
    nome="Medusa (core fwd 38mm)",
)

VARIACOES: dict[str, MotorSpec] = {
    "oficial": MOTOR_IREC,
    "throat_estreito": MOTOR_THROAT_ESTREITO,
    "throat_largo": MOTOR_THROAT_LARGO,
    "core_uniforme": MOTOR_CORE_UNIFORME,
    "core_fwd_menor": MOTOR_CORE_FWD_MENOR,
}
