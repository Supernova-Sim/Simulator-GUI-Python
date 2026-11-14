# src/simulacao/construtor_foguete.py
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

from src.especificacoes import (
    LIMITES_PADRAO,
    AletaSpec,
    CoifaSpec,
    FogueteSpec,
    LimitesSeguranca,
    MassaPontualSpec,
    MotorSpec,
    TuboSpec,
)
from src.estrutura.agregador import FogueteResolvido, resolver
from src.motor.derivador import MotorDerivado, derivar_motor

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


def _kwargs_rocket(foguete_spec: FogueteSpec, fonte: Any) -> dict[str, Any]:
    """Constrói os argumentos comuns de `Rocket(...)` a partir de um resolvido ou medido."""
    return {
        "radius": fonte.raio,
        "mass": fonte.massa_seca,
        "inertia": fonte.inercia_rocketpy,
        "center_of_mass_without_motor": fonte.cg_sem_motor,
        "coordinate_system_orientation": "nose_to_tail",
        "power_off_drag": str(foguete_spec.power_off_drag),
        "power_on_drag": str(foguete_spec.power_on_drag),
    }


def _adicionar_aletas(
    rkt: Rocket,
    foguete_spec: FogueteSpec,
    modo: ModoFoguete,
    resolvido: FogueteResolvido | None,
    spec_aleta: AletaSpec | None,
    tipo_aletas: str,
) -> object:
    """Anexa o conjunto de aletas (`freeform` ou `trapezio`) no `Rocket`."""
    aleta_eff = (
        resolvido.spec_aleta
        if resolvido is not None
        else (spec_aleta if spec_aleta is not None else foguete_spec.aleta)
    )
    geom = foguete_spec.geometria_medida

    if tipo_aletas == "freeform":
        if modo == "calculado":
            assert aleta_eff is not None
            return rkt.add_free_form_fins(
                n=aleta_eff.n,
                position=aleta_eff.position,
                shape_points=aleta_eff.shape_points,
                cant_angle=aleta_eff.cant_angle,
            )
        assert geom is not None
        return rkt.add_free_form_fins(
            n=geom.aletas_n,
            position=geom.aletas_position,
            shape_points=list(geom.aletas_shape_points),
            cant_angle=geom.aletas_cant_angle,
        )

    if tipo_aletas == "trapezio":
        if modo == "medido" and geom is not None and geom.aletas_trapezio_equiv is not None:
            return rkt.add_trapezoidal_fins(**geom.aletas_trapezio_equiv)
        if aleta_eff is None:
            raise ValueError("Sem dados de aleta trapezoidal disponíveis.")
        return rkt.add_trapezoidal_fins(
            n=aleta_eff.n,
            root_chord=aleta_eff.root_chord,
            tip_chord=aleta_eff.tip_chord,
            span=aleta_eff.span_le,
            sweep_length=aleta_eff.sweep_length,
            position=aleta_eff.position,
            cant_angle=aleta_eff.cant_angle,
        )

    raise ValueError(f"tipo_aletas inválido: {tipo_aletas!r}. Use 'freeform' ou 'trapezio'.")


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
    """Constrói o `FogueteMontado` no modo estrutural escolhido (`calculado` ou `medido`)."""
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
        parametros_rocket = _kwargs_rocket(foguete_spec, resolvido)
        nose_kwargs = {
            "length": coifa_eff.length,
            "kind": coifa_eff.kind,
            "position": coifa_eff.position,
        }
    else:
        geom = foguete_spec.geometria_medida
        if geom is None:
            raise ValueError(
                f"Foguete '{foguete_spec.nome}' não possui 'geometria_medida' configurada "
                "para modo='medido'."
            )
        parametros_rocket = _kwargs_rocket(foguete_spec, geom)
        nose_kwargs = {
            "length": geom.coifa_length,
            "kind": geom.coifa_kind,
            "position": geom.coifa_position,
        }

    rkt = Rocket(**parametros_rocket)
    if fator_arrasto != 1.0:
        rkt.power_off_drag = rkt.power_off_drag * fator_arrasto
        rkt.power_on_drag = rkt.power_on_drag * fator_arrasto

    nosecone = rkt.add_nose(**nose_kwargs)
    fins = _adicionar_aletas(rkt, foguete_spec, modo, resolvido, spec_aleta, tipo_aletas)
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
