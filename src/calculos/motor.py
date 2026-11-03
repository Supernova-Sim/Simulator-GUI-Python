# src/calculos/motor.py
"""Deriva propriedades completas do motor a partir de um `MotorSpec` (.ric > .eng).

🧩 Arquitetura C4 (Nível 3): docs/arquitetura/c3-subsistema-motor.md
⚡ Arquitetura C4 (Nível 4): clique no botão de Grafo no topo direito ao lado de 'More Actions'

Este é um módulo profundo:
  1. Se `spec.ric_path` está definido, carrega o `.ric`, aplica `spec.overrides`
     em memória UMA única vez e extrai do mesmo dicionário `props` tanto a
     geometria real dos grãos/tubeira/propelente quanto a simulação balística
     interna do OpenMotor.
  2. Se apenas `spec.thrust_curve_path` (.eng) está definido, integra a curva
     RASP e usa os grãos declarados em `spec.grains`.
  3. Calcula massa, CG, raio interno efetivo e inércia seca na convenção do
     RocketPy: `(I_11, I_22, I_33) = (I_transversal, I_transversal, I_longitudinal)`.
  4. Avalia todos os diagnósticos de segurança frente a `LimitesSeguranca`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.calculos.motorlib_variacoes import aplicar_overrides
from src.calculos.motorlib_wrapper import (
    carregar_props,
    extrair_geometria_props,
    simular_props,
)
from src.calculos.seguranca import (
    LIMITES_PADRAO,
    DiagnosticoFS,
    check_kn,
    check_mass_flux,
    check_p0,
    fs_carcaca,
)
from src.specs import GrainSpec, LimitesSeguranca, MotorSpec


# ============================================================
#  Parser do arquivo .eng (formato RASP)
# ============================================================
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
                t = float(parts[0])
                ft = float(parts[1])
            except ValueError:
                continue
            tempos.append(t)
            empuxos.append(ft)

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


def _integrar_trapezio(tempos: list[float], empuxos: list[float]) -> float:
    total = 0.0
    for i in range(1, len(tempos)):
        dt = tempos[i] - tempos[i - 1]
        total += 0.5 * (empuxos[i] + empuxos[i - 1]) * dt
    return total


# ============================================================
#  Saída resolvida do motor
# ============================================================
@dataclass(frozen=True)
class MotorDerivado:
    nome: str
    fonte: str                          # "ric" ou "eng"

    # ---------- Cinemática (de .ric ou .eng) ----------
    burn_time: tuple[float, float]
    total_impulse: float
    max_thrust: float
    eng_propellant_mass: float          # massa declarada pela fonte (cross-check)

    # ---------- Curva (só se fonte=ric) ----------
    curva_empuxo: tuple[tuple[float, float], ...] | None

    # ---------- Balística interna (só se fonte=ric) ----------
    p0_pico: float | None
    kn_pico: float | None
    mass_flux_pico: float | None
    isp_entregue: float | None

    # ---------- Geometria efetiva resolvida (já pós-overrides) ----------
    grains: tuple[GrainSpec, ...]
    propellant_density: float
    throat_radius: float
    nozzle_exit_radius: float

    # ---------- Propriedades derivadas dos grãos ----------
    propellant_mass: float
    propellant_length: float
    stack_length: float
    cg_propellant: float
    grain_inner_radius_effective: float
    grain_outer_radius_effective: float
    grain_height_effective: float

    # ---------- Carcaça ----------
    case_length: float
    case_outer_radius: float
    dry_mass: float
    cg_dry: float

    # ---------- Inércia seca ----------
    # Convenção RocketPy: (I_11, I_22, I_33) = (transversal, transversal, longitudinal)
    dry_inertia: tuple[float, float, float]

    # ---------- Agregados ----------
    mass_loaded: float                  # kg — dry_mass + propellant_mass

    # ---------- Fatores de segurança ----------
    diagnosticos: tuple[DiagnosticoFS, ...]

    @property
    def inercia_transversal(self) -> float:
        return self.dry_inertia[0]

    @property
    def inercia_longitudinal(self) -> float:
        return self.dry_inertia[2]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nome": self.nome,
            "fonte": self.fonte,
            "burn_time": list(self.burn_time),
            "total_impulse": self.total_impulse,
            "max_thrust": self.max_thrust,
            "eng_propellant_mass": self.eng_propellant_mass,
            "p0_pico": self.p0_pico,
            "kn_pico": self.kn_pico,
            "mass_flux_pico": self.mass_flux_pico,
            "isp_entregue": self.isp_entregue,
            "grains": [g.to_dict() for g in self.grains],
            "propellant_density": self.propellant_density,
            "throat_radius": self.throat_radius,
            "nozzle_exit_radius": self.nozzle_exit_radius,
            "propellant_mass": self.propellant_mass,
            "propellant_length": self.propellant_length,
            "stack_length": self.stack_length,
            "cg_propellant": self.cg_propellant,
            "grain_inner_radius_effective": self.grain_inner_radius_effective,
            "grain_outer_radius_effective": self.grain_outer_radius_effective,
            "grain_height_effective": self.grain_height_effective,
            "case_length": self.case_length,
            "case_outer_radius": self.case_outer_radius,
            "dry_mass": self.dry_mass,
            "cg_dry": self.cg_dry,
            "dry_inertia": list(self.dry_inertia),
            "mass_loaded": self.mass_loaded,
            "diagnosticos": [
                {
                    "nome": x.nome,
                    "valor": x.valor,
                    "limite_min": x.limite_min,
                    "limite_max": x.limite_max,
                    "unidade": x.unidade,
                    "ok": x.ok,
                    "detalhe": x.detalhe,
                }
                for x in self.diagnosticos
            ],
        }


# ============================================================
#  Cálculos internos
# ============================================================
def _resolver_fonte_e_geometria(spec: MotorSpec) -> dict[str, Any]:
    """Resolve tanto a balística quanto a geometria efetiva (.ric > .eng)."""
    if spec.ric_path is not None:
        props = carregar_props(spec.ric_path)
        if spec.overrides:
            props = aplicar_overrides(props, spec.overrides)

        grains_ric, rho_ric, throat_r_ric, exit_r_ric = extrair_geometria_props(props)
        r = simular_props(props, nome=spec.nome)

        # Se o usuário não sobrescreveu explicitamente no MotorSpec (ou se veio do .ric),
        # usamos os valores extraídos do `props` já com overrides aplicados.
        grains_eff = grains_ric if not spec.grains or spec.overrides else spec.grains
        rho_eff = rho_ric if spec.propellant_density is None or spec.overrides else spec.propellant_density
        throat_eff = throat_r_ric if spec.throat_radius is None or spec.overrides else spec.throat_radius
        exit_eff = exit_r_ric if spec.nozzle_exit_radius is None or spec.overrides else spec.nozzle_exit_radius

        return {
            "fonte": "ric",
            "burn_time": (r.tempo[0], r.tempo[-1]),
            "total_impulse": r.impulso_total,
            "max_thrust": r.empuxo_max,
            "eng_propellant_mass": r.massa_propelente_inicial,
            "curva_empuxo": tuple(r.curva_empuxo),
            "p0_pico": r.p0_pico,
            "kn_pico": r.kn_pico,
            "mass_flux_pico": r.mass_flux_pico,
            "isp_entregue": r.isp_entregue,
            "grains": grains_eff,
            "propellant_density": rho_eff,
            "throat_radius": throat_eff,
            "nozzle_exit_radius": exit_eff,
        }

    if spec.thrust_curve_path is not None:
        tempos, empuxos, header = _ler_eng(spec.thrust_curve_path)
        burn_time = (tempos[0], tempos[-1])
        total_impulse = _integrar_trapezio(tempos, empuxos)
        max_thrust = max(empuxos)
        return {
            "fonte": "eng",
            "burn_time": burn_time,
            "total_impulse": total_impulse,
            "max_thrust": max_thrust,
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

    raise ValueError(
        f"MotorSpec '{spec.nome}' precisa de 'ric_path' ou 'thrust_curve_path'."
    )


def _derivar_dos_graos(
    grains: tuple[GrainSpec, ...],
    propellant_density: float,
    grain_separation: float,
    margin_forward_side: float,
) -> tuple[float, float, float, float, float, float, float]:
    """Retorna `(massa_total, comprimento_prop, stack_length, cg_local, inner_eff,
    grain_height_eff, outer_eff)`."""
    massa_total = 0.0
    momento = 0.0
    volume_total = 0.0
    x = margin_forward_side
    comprimento_prop = 0.0

    for i, g in enumerate(grains):
        v = math.pi * (g.outer_radius**2 - g.inner_radius**2) * g.length
        m = v * propellant_density

        x_centro = x + g.length / 2.0
        massa_total += m
        momento += m * x_centro
        volume_total += v
        comprimento_prop += g.length

        x += g.length
        if i < len(grains) - 1:
            x += grain_separation

    stack_length = comprimento_prop + (len(grains) - 1) * grain_separation
    cg_local = momento / massa_total if massa_total > 0 else 0.0

    grain_height_eff = comprimento_prop / len(grains)
    outer_eff = sum(g.outer_radius * g.length for g in grains) / comprimento_prop
    r_i_eff_sq = outer_eff**2 - volume_total / (math.pi * comprimento_prop)
    inner_eff = math.sqrt(max(0.0, r_i_eff_sq))

    return (
        massa_total,
        comprimento_prop,
        stack_length,
        cg_local,
        inner_eff,
        grain_height_eff,
        outer_eff,
    )


def _derivar_carcaca(spec: MotorSpec, stack_length: float) -> tuple[float, float, float]:
    """Retorna `(case_length, case_outer_radius, dry_mass)`."""
    if spec.case_length is not None:
        case_length = spec.case_length
    else:
        case_length = (
            spec.margin_forward_side + stack_length + spec.margin_nozzle_side
        )

    r_o = spec.case_inner_radius + spec.case_wall_thickness

    if spec.dry_mass is not None:
        dry_mass = spec.dry_mass
    else:
        v_casca = math.pi * (r_o**2 - spec.case_inner_radius**2) * case_length
        massa_casca = v_casca * spec.case_density
        dry_mass = massa_casca + spec.nozzle_mass + spec.dry_mass_extra

    return case_length, r_o, dry_mass


def _derivar_inercia_seca(
    dry_mass: float, r_o: float, r_i: float, L: float,
) -> tuple[float, float]:
    """Inércia de casca cilíndrica oca.

    Returns
    -------
    (I_xx_longitudinal, I_yy_transversal)
        I_xx_longitudinal = roll (em torno do eixo axial e_3)
        I_yy_transversal  = pitch/yaw (em torno dos eixos transversais e_1, e_2)
    """
    I_xx_longitudinal = 0.5 * dry_mass * (r_o**2 + r_i**2)
    I_yy_transversal = (dry_mass / 12.0) * (3.0 * (r_o**2 + r_i**2) + L**2)
    return I_xx_longitudinal, I_yy_transversal


def _diagnosticar(
    info: dict[str, Any],
    spec: MotorSpec,
    limites: LimitesSeguranca,
) -> tuple[DiagnosticoFS, ...]:
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


# ============================================================
#  Ponto de Entrada Principal
# ============================================================
def derivar_motor(
    spec: MotorSpec,
    *,
    limites: LimitesSeguranca = LIMITES_PADRAO,
) -> MotorDerivado:
    """Deriva cinemática, balística interna, massas, inércias e diagnósticos do motor."""
    info = _resolver_fonte_e_geometria(spec)

    grains_eff: tuple[GrainSpec, ...] = info["grains"]
    rho_eff: float = info["propellant_density"]

    (
        prop_mass,
        prop_len,
        stack_len,
        cg_prop,
        inner_eff,
        grain_height_eff,
        outer_eff,
    ) = _derivar_dos_graos(
        grains=grains_eff,
        propellant_density=rho_eff,
        grain_separation=spec.grain_separation,
        margin_forward_side=spec.margin_forward_side,
    )

    case_len, case_r_o, dry_mass = _derivar_carcaca(spec, stack_len)
    cg_dry = case_len / 2.0

    # Convenção RocketPy: (I_11, I_22, I_33) = (transversal, transversal, longitudinal)
    if spec.dry_inertia_override is not None:
        dry_inertia = spec.dry_inertia_override
    else:
        I_long, I_transv = _derivar_inercia_seca(
            dry_mass, case_r_o, spec.case_inner_radius, case_len,
        )
        dry_inertia = (I_transv, I_transv, I_long)

    diagnosticos = _diagnosticar(info, spec, limites)

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
        grain_height_effective=grain_height_eff,
        case_length=case_len,
        case_outer_radius=case_r_o,
        dry_mass=dry_mass,
        cg_dry=cg_dry,
        dry_inertia=dry_inertia,
        mass_loaded=dry_mass + prop_mass,
        diagnosticos=diagnosticos,
    )
