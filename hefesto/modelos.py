# hefesto/modelos.py
from dataclasses import dataclass
from rocketpy import Rocket, SolidMotor

from configs.foguete.geometria import (
    FOGUETE, ALETAS, COIFA, RAIL_BUTTONS,
    REEFED, UNREEFED, ALETAS_TRAPEZIO_EQUIV, MOTOR_POSITION,
)
from configs.componentes import COMPONENTES
from configs.especificacao import AletaSpec, COIFA_IREC, CoifaSpec
from configs.motor.spec import MotorSpec
from configs.motor.medusa import MOTOR_IREC
from hefesto.modelo import resolver
from hefesto.calculos.motor import MotorDerivado, derivar_motor


@dataclass
class FogueteMontado:
    rocket: Rocket
    motor: SolidMotor
    motor_derivado: MotorDerivado       # ← novo
    nosecone: object
    fins: object
    rail_buttons: object
    unreefed: object
    reefed: object


def _motor_kwargs(spec, d, thrust_source=None) -> dict:
    if thrust_source is not None:
        ts = thrust_source
    elif d.curva_empuxo is not None:
        ts = list(d.curva_empuxo)          # .ric via motorlib
    else:
        ts = spec.thrust_curve_path        # fallback .eng

    return {
        "thrust_source": ts,
        "dry_mass": d.dry_mass,
        "dry_inertia": d.dry_inertia,
        "center_of_dry_mass_position": d.case_length - d.cg_dry,
        "grain_number": len(spec.grains),
        "grain_outer_radius": spec.grains[0].outer_radius,
        "grain_initial_inner_radius": d.grain_inner_radius_effective,
        "grain_initial_height": spec.grains[0].length,
        "grain_separation": spec.grain_separation,
        "grain_density": spec.propellant_density,
        "grains_center_of_mass_position": d.case_length - d.cg_propellant,
        "nozzle_position": spec.nozzle_position,
        "nozzle_radius": spec.nozzle_exit_radius,
        "throat_radius": spec.throat_radius,
        # burn_time começando em 0 (RocketPy pré-pend (0,0) na integração)
        "burn_time": (0.0, d.burn_time[1]),
        "coordinate_system_orientation": "nozzle_to_combustion_chamber",
    }


def build_motor(
    fator_empuxo: float = 1.0,
) -> tuple[SolidMotor, MotorDerivado]:
    """Constrói o motor e devolve o derivado junto (para reuso)."""
    d = derivar_motor(MOTOR_IREC)
    kwargs = _motor_kwargs(MOTOR_IREC, d)

    if fator_empuxo != 1.0:
        base = SolidMotor(**kwargs)
        kwargs["thrust_source"] = base.thrust * fator_empuxo

    return SolidMotor(**kwargs), d


def build_rocket(
    *,
    tipo_aletas: str = "freeform",
    spec_aleta: AletaSpec | None = None,
    fator_empuxo: float = 1.0,
    fator_arrasto: float = 1.0,
) -> FogueteMontado:
    """Constrói o foguete.

    Se `spec_aleta` for passada, massa/CG/inércia são RECALCULADOS a partir
    dos COMPONENTES + COIFA_IREC + aleta. Caso contrário, usa FOGUETE hardcoded.
    """
    motor, motor_d = build_motor(fator_empuxo=fator_empuxo)
    resolvido = None

    if spec_aleta is not None:
        resolvido = resolver(
            componentes=COMPONENTES,
            spec_aleta=spec_aleta,
            spec_coifa=COIFA_IREC,
            raio=FOGUETE["radius"],
        )
        parametros_rocket = resolvido.dict_rocket(
            power_off_drag=FOGUETE["power_off_drag"],
            power_on_drag=FOGUETE["power_on_drag"],
        )
        nose_kwargs = resolvido.dict_coifa()
    else:
        parametros_rocket = dict(FOGUETE)
        nose_kwargs = dict(COIFA)

    rkt = Rocket(**parametros_rocket)

    if fator_arrasto != 1.0:
        rkt.power_off_drag = rkt.power_off_drag * fator_arrasto
        rkt.power_on_drag  = rkt.power_on_drag  * fator_arrasto

    nosecone = rkt.add_nose(**nose_kwargs)

    if spec_aleta is not None:
        fins = rkt.add_free_form_fins(
            n=spec_aleta.n,
            position=spec_aleta.position,
            shape_points=resolvido.shape_points(),
            cant_angle=spec_aleta.cant_angle,
        )
    elif tipo_aletas == "freeform":
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
        rocket=rkt, motor=motor, motor_derivado=motor_d,
        nosecone=nosecone, fins=fins, rail_buttons=rail_buttons,
        unreefed=unreefed, reefed=reefed,
    )