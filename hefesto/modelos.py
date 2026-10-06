# hefesto/modelos.py
from dataclasses import dataclass
from rocketpy import Rocket, SolidMotor

from configs.foguete import (
    FOGUETE, ALETAS, COIFA, RAIL_BUTTONS,
    REEFED, UNREEFED, ALETAS_TRAPEZIO_EQUIV, MOTOR_POSITION,
)
from configs.motor import MOTOR


@dataclass
class FogueteMontado:
    rocket: Rocket
    motor: SolidMotor
    nosecone: object
    fins: object
    rail_buttons: object
    unreefed: object
    reefed: object


def build_motor(fator_empuxo: float = 1.0) -> SolidMotor:
    """Constrói o motor. Se fator_empuxo != 1.0, escala a curva de empuxo."""
    motor = SolidMotor(**MOTOR)
    if fator_empuxo != 1.0:
        motor = SolidMotor(
            **{**MOTOR, "thrust_source": motor.thrust * fator_empuxo}
        )
    return motor


def build_rocket(
    *,
    tipo_aletas: str = "freeform",
    fator_empuxo: float = 1.0,
    fator_arrasto: float = 1.0,
) -> FogueteMontado:
    """Constrói o foguete.

    Parameters
    ----------
    tipo_aletas : str
        "freeform" ou "trapezio".
    fator_empuxo : float
        Multiplica a curva de empuxo do motor (1.0 = nominal).
    fator_arrasto : float
        Multiplica as curvas power_off_drag e power_on_drag
        (1.0 = nominal).
    """
    motor = build_motor(fator_empuxo=fator_empuxo)

    rkt = Rocket(**FOGUETE)

    # Ajusta arrasto se solicitado. RocketPy carrega os CSVs em __init__,
    # então neste ponto rkt.power_off_drag e power_on_drag já são Functions.
    if fator_arrasto != 1.0:
        rkt.power_off_drag = rkt.power_off_drag * fator_arrasto
        rkt.power_on_drag  = rkt.power_on_drag  * fator_arrasto

    nosecone = rkt.add_nose(**COIFA)

    if tipo_aletas == "freeform":
        fins = rkt.add_free_form_fins(**ALETAS)
    elif tipo_aletas == "trapezio":
        fins = rkt.add_trapezoidal_fins(**ALETAS_TRAPEZIO_EQUIV)
    else:
        raise ValueError(f"tipo_aletas inválido: {tipo_aletas!r}")

    rail_buttons = rkt.set_rail_buttons(**RAIL_BUTTONS)

    unreefed = rkt.add_parachute(**UNREEFED)
    reefed   = rkt.add_parachute(**REEFED)

    rkt.add_motor(motor, position=MOTOR_POSITION)

    return FogueteMontado(
        rocket=rkt, motor=motor,
        nosecone=nosecone, fins=fins, rail_buttons=rail_buttons,
        unreefed=unreefed, reefed=reefed,
    )