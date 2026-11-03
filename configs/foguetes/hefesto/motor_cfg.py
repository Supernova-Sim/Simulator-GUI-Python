# configs/foguetes/hefesto/motor.py
"""Configuração declarativa do motor Medusa (IREC).

Zero I/O no import: o arquivo `.ric` e a curva `.eng` são apenas referenciados
aqui e lidos sob demanda dentro de `derivar_motor()`.
"""
from __future__ import annotations

from src.paths import MOTORES, OPENMOTOR
from src.specs import MotorSpec

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
