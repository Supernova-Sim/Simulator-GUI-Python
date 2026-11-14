# src/motor/derivador.py
"""Deriva propriedades completas do motor a partir de um `MotorSpec` (.ric > .eng).

Este é um módulo profundo:
  1. Se `spec.ric_path` está definido, delega ao `adaptador_openmotor.executar_ric`
     aplicando `spec.overrides` em memória uma única vez e extraindo geometria e
     balística consistentes.
  2. Se apenas `spec.thrust_curve_path` (.eng) está definido, integra a curva RASP
     e usa os grãos declarados em `spec.grains`.
  3. Calcula massa, CG, raio efetivo, inércia seca na convenção RocketPy e
     diagnósticos de segurança frente a `LimitesSeguranca`.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from src.especificacoes import LIMITES_PADRAO, GrainSpec, LimitesSeguranca, MotorSpec
from src.motor.adaptador_openmotor import executar_ric
from src.motor.seguranca import (
    DiagnosticoFS,
    check_kn,
    check_mass_flux,
    check_p0,
    fs_carcaca,
)


def _ler_eng(path: str | Path) -> tuple[list[float], list[float], dict[str, Any]]:
    """Lê um arquivo RASP `.eng` e devolve `(tempos, empuxos, header)`."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo .eng não encontrado: {path}")

    tempos: list[float] = []
    empuxos: list[float] = []
    header_line: str | None = None

    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            if header_line is None:
                header_line = line
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                tempos.append(float(parts[0]))
                empuxos.append(float(parts[1]))
            except ValueError:
                continue

    if header_line is None:
        raise ValueError(f"Arquivo .eng sem cabeçalho: {path}")
    if len(tempos) < 2:
        raise ValueError(f"Arquivo .eng sem pontos suficientes: {path}")

    hp = header_line.split()
    header = {
        "designation": hp[0] if len(hp) > 0 else "",
        "diameter_mm": float(hp[1]) if len(hp) > 1 else 0.0,
        "length_mm": float(hp[2]) if len(hp) > 2 else 0.0,
        "delay": hp[3] if len(hp) > 3 else "",
        "propellant_mass": float(hp[4]) if len(hp) > 4 else 0.0,
        "total_mass": float(hp[5]) if len(hp) > 5 else 0.0,
    }
    return tempos, empuxos, header


@dataclass(frozen=True)
class MotorDerivado:
    nome: str
    fonte: str                          # "ric" ou "eng"

    # ---------- Cinemática (de .ric ou .eng) ----------
    burn_time: tuple[float, float]
    total_impulse: float
    max_thrust: float
    eng_propellant_mass: float

    # ---------- Curva e Balística interna ----------
    curva_empuxo: tuple[tuple[float, float], ...] | None
    p0_pico: float | None
    kn_pico: float | None
    mass_flux_pico: float | None
    isp_entregue: float | None

    # ---------- Geometria efetiva resolvida ----------
    grains: tuple[GrainSpec, ...]
    propellant_density: float
    throat_radius: float
    nozzle_exit_radius: float

    # ---------- Propriedades derivadas dos grãos e carcaça ----------
    propellant_mass: float
    propellant_length: float
    stack_length: float
    cg_propellant: float
    grain_inner_radius_effective: float
    grain_outer_radius_effective: float
    grain_height_effective: float

    case_length: float
    case_outer_radius: float
    dry_mass: float
    cg_dry: float

    # Convenção RocketPy: (I_11, I_22, I_33) = (transversal, transversal, longitudinal)
    dry_inertia: tuple[float, float, float]
    mass_loaded: float
    diagnosticos: tuple[DiagnosticoFS, ...]

    @property
    def inercia_transversal(self) -> float:
        return self.dry_inertia[0]

    @property
    def inercia_longitudinal(self) -> float:
        return self.dry_inertia[2]

    def to_dict(self) -> dict[str, Any]:
        dados = dataclasses.asdict(self)
        dados.pop("curva_empuxo", None)
        dados["burn_time"] = list(self.burn_time)
        dados["dry_inertia"] = list(self.dry_inertia)
        return dados


def _resolver_fonte_e_geometria(spec: MotorSpec) -> dict[str, Any]:
    """Resolve balística e geometria efetiva (`.ric` > `.eng`)."""
    if spec.ric_path is not None:
        r = executar_ric(spec.ric_path, spec.overrides, nome=spec.nome)
        return {
            "fonte": "ric",
            "burn_time": r.burn_time,
            "total_impulse": r.impulso_total,
            "max_thrust": r.empuxo_max,
            "eng_propellant_mass": r.massa_propelente_inicial,
            "curva_empuxo": r.curva_empuxo,
            "p0_pico": r.p0_pico,
            "kn_pico": r.kn_pico,
            "mass_flux_pico": r.mass_flux_pico,
            "isp_entregue": r.isp_entregue,
            "grains": r.grains if not spec.grains or spec.overrides else spec.grains,
            "propellant_density": (
                r.propellant_density if spec.propellant_density is None or spec.overrides else spec.propellant_density
            ),
            "throat_radius": r.throat_radius if spec.throat_radius is None or spec.overrides else spec.throat_radius,
            "nozzle_exit_radius": (
                r.nozzle_exit_radius if spec.nozzle_exit_radius is None or spec.overrides else spec.nozzle_exit_radius
            ),
        }

    if spec.thrust_curve_path is not None:
        tempos, empuxos, header = _ler_eng(spec.thrust_curve_path)
        return {
            "fonte": "eng",
            "burn_time": (tempos[0], tempos[-1]),
            "total_impulse": float(np.trapezoid(empuxos, tempos)),
            "max_thrust": max(empuxos),
            "eng_propellant_mass": header["propellant_mass"],
            "curva_empuxo": tuple(zip(tempos, empuxos)),
            "p0_pico": None,
            "kn_pico": None,
            "mass_flux_pico": None,
            "isp_entregue": None,
            "grains": spec.grains,
            "propellant_density": float(spec.propellant_density),
            "throat_radius": float(spec.throat_radius),
            "nozzle_exit_radius": float(spec.nozzle_exit_radius),
        }

    raise ValueError(f"MotorSpec '{spec.nome}' precisa de 'ric_path' ou 'thrust_curve_path'.")


def _derivar_dos_graos(
    grains: tuple[GrainSpec, ...],
    propellant_density: float,
    grain_separation: float,
    margin_forward_side: float,
) -> tuple[float, float, float, float, float, float, float]:
    """Retorna `(massa_total, comp_prop, stack_len, cg_local, inner_eff, height_eff, outer_eff)`."""
    massa_total = momento = volume_total = comp_prop = 0.0
    x = margin_forward_side

    for i, g in enumerate(grains):
        v = math.pi * (g.outer_radius**2 - g.inner_radius**2) * g.length
        m = v * propellant_density
        massa_total += m
        momento += m * (x + g.length / 2.0)
        volume_total += v
        comp_prop += g.length
        x += g.length + (grain_separation if i < len(grains) - 1 else 0.0)

    stack_len = comp_prop + (len(grains) - 1) * grain_separation
    cg_local = momento / massa_total if massa_total > 0 else 0.0
    height_eff = comp_prop / len(grains)
    outer_eff = sum(g.outer_radius * g.length for g in grains) / comp_prop
    inner_eff = math.sqrt(max(0.0, outer_eff**2 - volume_total / (math.pi * comp_prop)))
    return massa_total, comp_prop, stack_len, cg_local, inner_eff, height_eff, outer_eff


def _derivar_carcaca(spec: MotorSpec, stack_length: float) -> tuple[float, float, float]:
    """Retorna `(case_length, case_outer_radius, dry_mass)`."""
    case_length = (
        spec.case_length
        if spec.case_length is not None
        else spec.margin_forward_side + stack_length + spec.margin_nozzle_side
    )
    r_o = spec.case_inner_radius + spec.case_wall_thickness
    if spec.dry_mass is not None:
        dry_mass = spec.dry_mass
    else:
        v_casca = math.pi * (r_o**2 - spec.case_inner_radius**2) * case_length
        dry_mass = v_casca * spec.case_density + spec.nozzle_mass + spec.dry_mass_extra
    return case_length, r_o, dry_mass


def _derivar_inercia_seca(dry_mass: float, r_o: float, r_i: float, length: float) -> tuple[float, float]:
    """Retorna `(I_longitudinal, I_transversal)` para casca cilíndrica oca."""
    return (
        0.5 * dry_mass * (r_o**2 + r_i**2),
        (dry_mass / 12.0) * (3.0 * (r_o**2 + r_i**2) + length**2),
    )


def _diagnosticar(info: dict[str, Any], spec: MotorSpec, limites: LimitesSeguranca) -> tuple[DiagnosticoFS, ...]:
    if info["p0_pico"] is None:
        return ()
    return (
        fs_carcaca(
            p0_pico=info["p0_pico"],
            case_inner_radius=spec.case_inner_radius,
            case_wall_thickness=spec.case_wall_thickness,
            limites=limites,
        ),
        check_p0(info["p0_pico"], limites=limites),
        check_kn(info["kn_pico"], limites=limites),
        check_mass_flux(info["mass_flux_pico"], limites=limites),
    )


def derivar_motor(spec: MotorSpec, *, limites: LimitesSeguranca = LIMITES_PADRAO) -> MotorDerivado:
    """Deriva cinemática, balística interna, massas, inércias e diagnósticos do motor."""
    info = _resolver_fonte_e_geometria(spec)
    grains_eff: tuple[GrainSpec, ...] = info["grains"]
    rho_eff: float = info["propellant_density"]

    prop_mass, prop_len, stack_len, cg_prop, inner_eff, grain_h_eff, outer_eff = _derivar_dos_graos(
        grains=grains_eff,
        propellant_density=rho_eff,
        grain_separation=spec.grain_separation,
        margin_forward_side=spec.margin_forward_side,
    )
    case_len, case_r_o, dry_mass = _derivar_carcaca(spec, stack_len)

    if spec.dry_inertia_override is not None:
        dry_inertia = spec.dry_inertia_override
    else:
        i_long, i_transv = _derivar_inercia_seca(dry_mass, case_r_o, spec.case_inner_radius, case_len)
        dry_inertia = (i_transv, i_transv, i_long)

    return MotorDerivado(
        nome=spec.nome,
        fonte=info["fonte"],
        burn_time=info["burn_time"],
        total_impulse=info["total_impulse"],
        max_thrust=info["max_thrust"],
        eng_propellant_mass=info["eng_propellant_mass"],
        curva_empuxo=info["curva_empuxo"],
        p0_pico=info["p0_pico"],
        kn_pico=info["kn_pico"],
        mass_flux_pico=info["mass_flux_pico"],
        isp_entregue=info["isp_entregue"],
        grains=grains_eff,
        propellant_density=rho_eff,
        throat_radius=info["throat_radius"],
        nozzle_exit_radius=info["nozzle_exit_radius"],
        propellant_mass=prop_mass,
        propellant_length=prop_len,
        stack_length=stack_len,
        cg_propellant=cg_prop,
        grain_inner_radius_effective=inner_eff,
        grain_outer_radius_effective=outer_eff,
        grain_height_effective=grain_h_eff,
        case_length=case_len,
        case_outer_radius=case_r_o,
        dry_mass=dry_mass,
        cg_dry=case_len / 2.0,
        dry_inertia=dry_inertia,
        mass_loaded=dry_mass + prop_mass,
        diagnosticos=_diagnosticar(info, spec, limites),
    )
