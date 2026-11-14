# configs/foguetes/hefesto/motor.py
"""Configuração declarativa e variações exploratórias do motor Medusa (IREC).

Zero I/O no import: o arquivo `.ric` e a curva `.eng` são apenas referenciados
aqui e lidos sob demanda dentro de `derivar_motor()`.
"""
from __future__ import annotations

import dataclasses
from typing import Any

from src.caminhos import MOTORES, OPENMOTOR
from src.especificacoes import MotorSpec, validar_overrides

RIC_MEDUSA = OPENMOTOR / "MotorNovo2.ric"
ENG_MEDUSA = MOTORES / "jul2semMedidas.eng"

_CARCACA_MEDUSA = {
    "case_inner_radius": 0.05395,
    "case_wall_thickness": 0.003175,
    "case_density": 2700.0,         # alumínio 6063-T5
    "grain_separation": 0.010,
    "nozzle_position": 0.016,
    "case_length": 1.100,
    "dry_mass": 7.5,
    "margin_nozzle_side": 0.075,
    "margin_forward_side": 0.075,
}

MOTOR_IREC = MotorSpec(
    nome="Medusa KNSB a",
    ric_path=RIC_MEDUSA,
    thrust_curve_path=ENG_MEDUSA,
    **_CARCACA_MEDUSA,
)

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
