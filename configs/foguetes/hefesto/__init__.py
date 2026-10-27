# configs/foguetes/hefesto/__init__.py
"""Instância concreta: foguete Hefesto."""
from __future__ import annotations

from configs.foguetes.hefesto.aletas import ALETA_IREC, ALETAS_TRAPEZIO_EQUIV
from configs.foguetes.hefesto.coifa import COIFA_IREC
from configs.foguetes.hefesto.corpo import COMPONENTES
from configs.foguetes.hefesto.estocastico import (
    ALETAS_E,
    ALETAS_POS_E,
    COIFA_E,
    COIFA_POS_E,
    FOGUETE_E,
    LOWER_BUTTON_POSITION_E,
    MOTOR_E,
    MOTOR_POS_E,
    RAIL_BUTTONS_E,
    REEFED_E,
    UNREEFED_E,
)
from configs.foguetes.hefesto.geometria import (
    ALETAS,
    COIFA,
    FOGUETE,
    GEOMETRIA_MEDIDA_HEFESTO,
    MOTOR_POSITION,
    RAIL_BUTTONS,
)
from configs.foguetes.hefesto.motor import ENG_MEDUSA, MOTOR_IREC, RIC_MEDUSA
from configs.foguetes.hefesto.recuperacao import REEFED, UNREEFED
from configs.foguetes.hefesto.voo import IREC, IREC_E, IREC_ENSEMBLE_E
from configs.limites import LIMITES_IREC
from src.specs import FogueteSpec

HEFESTO = FogueteSpec(
    nome="Hefesto",
    raio=FOGUETE["radius"],
    motor=MOTOR_IREC,
    motor_position=MOTOR_POSITION,
    power_off_drag=FOGUETE["power_off_drag"],
    power_on_drag=FOGUETE["power_on_drag"],
    rail_buttons=RAIL_BUTTONS,
    reefed=REEFED,
    unreefed=UNREEFED,
    componentes=tuple(COMPONENTES),
    coifa=COIFA_IREC,
    aleta=ALETA_IREC,
    geometria_medida=GEOMETRIA_MEDIDA_HEFESTO,
    limites=LIMITES_IREC,
)

__all__ = [
    "ALETAS",
    "ALETAS_E",
    "ALETAS_POS_E",
    "ALETAS_TRAPEZIO_EQUIV",
    "ALETA_IREC",
    "COIFA",
    "COIFA_E",
    "COIFA_IREC",
    "COIFA_POS_E",
    "COMPONENTES",
    "ENG_MEDUSA",
    "FOGUETE",
    "FOGUETE_E",
    "GEOMETRIA_MEDIDA_HEFESTO",
    "HEFESTO",
    "IREC",
    "IREC_E",
    "IREC_ENSEMBLE_E",
    "LOWER_BUTTON_POSITION_E",
    "MOTOR_E",
    "MOTOR_IREC",
    "MOTOR_POSITION",
    "MOTOR_POS_E",
    "RAIL_BUTTONS",
    "RAIL_BUTTONS_E",
    "REEFED",
    "REEFED_E",
    "RIC_MEDUSA",
    "UNREEFED",
    "UNREEFED_E",
]
