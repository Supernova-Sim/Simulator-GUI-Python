# src/construtor_foguete.py
"""Monta o `SolidMotor` e o `Rocket` prontos para simulação no RocketPy.

Separa explicitamente os dois modos de representação estrutural do foguete:
  - `modo="calculado"`: massa, CG e inércia vêm de `resolver(componentes, aleta, coifa, raio)`.
  - `modo="medido"`: massa, CG e inércia vêm de `GeometriaMedidaSpec` (bancada/OpenRocket).

Não importa nada de `configs/`; todas as especificações chegam por argumento.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from rocketpy import Rocket, SolidMotor

from src.calculos.motor import MotorDerivado, derivar_motor
from src.calculos.seguranca import LIMITES_PADRAO
from src.agregador_estrutural import FogueteResolvido, resolver
from src.specs import (
    AletaSpec,
    CoifaSpec,
    FogueteSpec,
    LimitesSeguranca,
    MassaPontualSpec,
    MotorSpec,
    TuboSpec,
)

ModoFoguete = Literal["calculado", "medido"]


@dataclass
class FogueteMontado:
    rocket: Rocket
    motor: SolidMotor
    motor_derivado: MotorDerivado
    modo: ModoFoguete
    foguete_resolvido: FogueteResolvido | None
    nosecone: object
    fins: object
    rail_buttons: object
    unreefed: object
    reefed: object


def _motor_kwargs(spec: MotorSpec, d: MotorDerivado, thrust_source: Any = None) -> dict[str, Any]:
    """Traduz `MotorSpec` + `MotorDerivado` para os argumentos de `SolidMotor`.

    Usa sempre `d.grains`, `d.propellant_density`, `d.nozzle_exit_radius` e
    `d.throat_radius` do `MotorDerivado` para refletir eventuais `overrides`.
    """
    if thrust_source is not None:
        ts = thrust_source
    elif d.curva_empuxo is not None:
        ts = list(d.curva_empuxo)
    else:
        ts = str(spec.thrust_curve_path)

    return {
        "thrust_source": ts,
        "dry_mass": d.dry_mass,
        "dry_inertia": d.dry_inertia,
        "center_of_dry_mass_position": d.case_length - d.cg_dry,
        "grain_number": len(d.grains),
        "grain_outer_radius": d.grain_outer_radius_effective,
        "grain_initial_inner_radius": d.grain_inner_radius_effective,
        "grain_initial_height": d.grain_height_effective,
        "grain_separation": spec.grain_separation,
        "grain_density": d.propellant_density,
        "grains_center_of_mass_position": d.case_length - d.cg_propellant,
        "nozzle_position": spec.nozzle_position,
        "nozzle_radius": d.nozzle_exit_radius,
        "throat_radius": d.throat_radius,
        "burn_time": (0.0, d.burn_time[1]),
        "coordinate_system_orientation": "nozzle_to_combustion_chamber",
    }


def build_motor(
    motor_spec: MotorSpec,
    fator_empuxo: float = 1.0,
    *,
    limites: LimitesSeguranca = LIMITES_PADRAO,
) -> tuple[SolidMotor, MotorDerivado]:
    """Constrói o `SolidMotor` e o `MotorDerivado` a partir de um `MotorSpec`."""
    d = derivar_motor(motor_spec, limites=limites)
    kwargs = _motor_kwargs(motor_spec, d)

    if fator_empuxo != 1.0:
        base = SolidMotor(**kwargs)
        kwargs["thrust_source"] = base.thrust * fator_empuxo

    return SolidMotor(**kwargs), d


def build_rocket(
    foguete_spec: FogueteSpec,
    *,
    modo: ModoFoguete = "calculado",
    motor_spec: MotorSpec | None = None,
    componentes: Sequence[TuboSpec | MassaPontualSpec] | None = None,
    spec_coifa: CoifaSpec | None = None,
    spec_aleta: AletaSpec | None = None,
    tipo_aletas: str = "freeform",
    fator_empuxo: float = 1.0,
    fator_arrasto: float = 1.0,
) -> FogueteMontado:
    """Constrói o `FogueteMontado` no modo estrutural escolhido (`calculado` ou `medido`).

    Parameters
    ----------
    foguete_spec : FogueteSpec
        Especificação completa do foguete (ex.: `HEFESTO` de `configs`).
    modo : {"calculado", "medido"}
        - `"calculado"`: resolve massa, CG e inércia a partir de componentes, coifa e aletas.
        - `"medido"`: usa os valores medidos de bancada (`foguete_spec.geometria_medida`).
    motor_spec : MotorSpec | None
        Permite substituir o motor nominal (ex.: por uma variação) sem recriar `foguete_spec`.
    """
    if modo not in ("calculado", "medido"):
        raise ValueError(
            f"modo inválido: {modo!r}. Escolha explicitamente 'calculado' ou 'medido'."
        )

    motor_efetivo = motor_spec if motor_spec is not None else foguete_spec.motor
    motor, motor_d = build_motor(
        motor_spec=motor_efetivo,
        fator_empuxo=fator_empuxo,
        limites=foguete_spec.limites,
    )

    resolvido: FogueteResolvido | None = None

    if modo == "calculado":
        comp_eff = componentes if componentes is not None else foguete_spec.componentes
        coifa_eff = spec_coifa if spec_coifa is not None else foguete_spec.coifa
        aleta_eff = spec_aleta if spec_aleta is not None else foguete_spec.aleta

        if not comp_eff or coifa_eff is None or aleta_eff is None:
            raise ValueError(
                f"Foguete '{foguete_spec.nome}' não possui todos os insumos para "
                "modo='calculado' (componentes, coifa, aleta)."
            )

        resolvido = resolver(
            componentes=comp_eff,
            spec_aleta=aleta_eff,
            spec_coifa=coifa_eff,
            raio=foguete_spec.raio,
        )
        parametros_rocket = resolvido.dict_rocket(
            power_off_drag=str(foguete_spec.power_off_drag),
            power_on_drag=str(foguete_spec.power_on_drag),
        )
        nose_kwargs = resolvido.dict_coifa()
    else:
        geom = foguete_spec.geometria_medida
        if geom is None:
            raise ValueError(
                f"Foguete '{foguete_spec.nome}' não possui 'geometria_medida' configurada "
                "para modo='medido'."
            )
        parametros_rocket = geom.dict_rocket(
            power_off_drag=str(foguete_spec.power_off_drag),
            power_on_drag=str(foguete_spec.power_on_drag),
        )
        nose_kwargs = geom.dict_coifa()

    rkt = Rocket(**parametros_rocket)

    if fator_arrasto != 1.0:
        rkt.power_off_drag = rkt.power_off_drag * fator_arrasto
        rkt.power_on_drag = rkt.power_on_drag * fator_arrasto

    nosecone = rkt.add_nose(**nose_kwargs)

    if tipo_aletas == "freeform":
        if modo == "calculado" and resolvido is not None:
            aleta_eff = resolvido.spec_aleta
            fins = rkt.add_free_form_fins(
                n=aleta_eff.n,
                position=aleta_eff.position,
                shape_points=resolvido.shape_points(),
                cant_angle=aleta_eff.cant_angle,
            )
        else:
            geom = foguete_spec.geometria_medida
            assert geom is not None
            fins = rkt.add_free_form_fins(**geom.dict_aletas_freeform())
    elif tipo_aletas == "trapezio":
        if modo == "calculado" and foguete_spec.aleta is not None:
            a = foguete_spec.aleta
            fins = rkt.add_trapezoidal_fins(
                n=a.n,
                root_chord=a.root_chord,
                tip_chord=a.tip_chord,
                span=a.span_le,
                sweep_length=a.sweep_length,
                position=a.position,
                cant_angle=a.cant_angle,
            )
        else:
            geom = foguete_spec.geometria_medida
            if geom is not None and geom.aletas_trapezio_equiv is not None:
                fins = rkt.add_trapezoidal_fins(**geom.aletas_trapezio_equiv)
            elif foguete_spec.aleta is not None:
                a = foguete_spec.aleta
                fins = rkt.add_trapezoidal_fins(
                    n=a.n,
                    root_chord=a.root_chord,
                    tip_chord=a.tip_chord,
                    span=a.span_le,
                    sweep_length=a.sweep_length,
                    position=a.position,
                    cant_angle=a.cant_angle,
                )
            else:
                raise ValueError("Sem dados de aleta trapezoidal disponíveis.")
    else:
        raise ValueError(f"tipo_aletas inválido: {tipo_aletas!r}. Use 'freeform' ou 'trapezio'.")

    rail_buttons = rkt.set_rail_buttons(**foguete_spec.rail_buttons)
    unreefed = rkt.add_parachute(**foguete_spec.unreefed)
    reefed = rkt.add_parachute(**foguete_spec.reefed)
    rkt.add_motor(motor, position=foguete_spec.motor_position)

    return FogueteMontado(
        rocket=rkt,
        motor=motor,
        motor_derivado=motor_d,
        modo=modo,
        foguete_resolvido=resolvido,
        nosecone=nosecone,
        fins=fins,
        rail_buttons=rail_buttons,
        unreefed=unreefed,
        reefed=reefed,
    )
