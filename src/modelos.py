# src/modelos.py
"""Monta o foguete pronto para o RocketPy.

Padrão de injeção: todos os parâmetros concretos (motor, componentes,
aleta, coifa) chegam por argumento. Os defaults apontam para o Hefesto,
mas qualquer um pode ser sobrescrito.
"""
from dataclasses import dataclass
from rocketpy import Rocket, SolidMotor

from configs import (
    # defaults do Hefesto
    MOTOR_IREC, COMPONENTES, COIFA_IREC,
    FOGUETE, ALETAS, COIFA, RAIL_BUTTONS,
    REEFED, UNREEFED, ALETAS_TRAPEZIO_EQUIV, MOTOR_POSITION,
    # tipos
    AletaSpec, CoifaSpec, MotorSpec,
    TuboSpec, MassaPontualSpec,
)
from src.modelo import resolver
from src.calculos.motor import MotorDerivado, derivar_motor


@dataclass
class FogueteMontado:
    rocket: Rocket
    motor: SolidMotor
    motor_derivado: MotorDerivado
    nosecone: object
    fins: object
    rail_buttons: object
    unreefed: object
    reefed: object


def _motor_kwargs(spec: MotorSpec, d: MotorDerivado, thrust_source=None) -> dict:
    """Traduz MotorSpec + MotorDerivado para kwargs do SolidMotor."""
    if thrust_source is not None:
        ts = thrust_source
    elif d.curva_empuxo is not None:
        ts = list(d.curva_empuxo)
    else:
        ts = spec.thrust_curve_path

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
        "burn_time": (0.0, d.burn_time[1]),
        "coordinate_system_orientation": "nozzle_to_combustion_chamber",
    }


def build_motor(
    motor_spec: MotorSpec | None = None,
    fator_empuxo: float = 1.0,
) -> tuple[SolidMotor, MotorDerivado]:
    """Constrói o SolidMotor a partir de um MotorSpec.

    Parameters
    ----------
    motor_spec : MotorSpec | None
        Default = MOTOR_IREC (Hefesto).
    """
    spec = motor_spec if motor_spec is not None else MOTOR_IREC
    d = derivar_motor(spec)
    kwargs = _motor_kwargs(spec, d)

    if fator_empuxo != 1.0:
        base = SolidMotor(**kwargs)
        kwargs["thrust_source"] = base.thrust * fator_empuxo

    return SolidMotor(**kwargs), d


def build_rocket(
    *,
    # --- Identidade do foguete ---
    motor_spec: MotorSpec | None = None,
    componentes: list[TuboSpec | MassaPontualSpec] | None = None,
    spec_coifa: CoifaSpec | None = None,
    spec_aleta: AletaSpec | None = None,

    # --- Aletas (quando spec_aleta é None) ---
    tipo_aletas: str = "freeform",

    # --- Fatores de varredura ---
    fator_empuxo: float = 1.0,
    fator_arrasto: float = 1.0,
) -> FogueteMontado:
    """Constrói o foguete injetando as dependências.

    Defaults = Hefesto (IREC 2026). Para outro foguete, passe todos.
    """
    # --- Defaults do Hefesto ---
    motor_spec = motor_spec if motor_spec is not None else MOTOR_IREC
    componentes = componentes if componentes is not None else COMPONENTES
    spec_coifa = spec_coifa if spec_coifa is not None else COIFA_IREC

    motor, motor_d = build_motor(motor_spec=motor_spec, fator_empuxo=fator_empuxo)
    resolvido = None

    if spec_aleta is not None:
        resolvido = resolver(
            componentes=componentes,
            spec_aleta=spec_aleta,
            spec_coifa=spec_coifa,
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

def main() -> None:
    """Smoke test: monta o foguete e roda um voo curto."""
    from configs import IREC, ALETA_IREC
    from src.ambiente import build_irec
    from rocketpy import Flight

    # Configuração oficial do Hefesto (spec_aleta resolvida)
    foguete = build_rocket(spec_aleta=ALETA_IREC, tipo_aletas="freeform")
    voo = Flight(rocket=foguete.rocket, environment=build_irec(), **IREC)
    apogee_agl = voo.apogee - 1401

    print(f"apogee AGL:    {apogee_agl:.1f} m")
    print(f"min stability: {voo.min_stability_margin:.3f} cal")

    assert 2300 < apogee_agl < 2500, f"apogee fora da faixa: {apogee_agl}"
    assert voo.min_stability_margin > 1.0, "margem < 1 cal"
    print("\n✓ modelos OK")


if __name__ == "__main__":
    main()