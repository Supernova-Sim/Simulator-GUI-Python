#!/usr/bin/env python
"""Inspeção da configuração do foguete Hefesto.

Imprime de forma organizada: motor, estrutura, segurança, voo.

Uso pela CLI:
    python centralControle/inspecionar.py motor       # só o motor
    python centralControle/inspecionar.py estrutura   # corpo + coifa + aletas
    python centralControle/inspecionar.py seguranca   # FS e limites
    python centralControle/inspecionar.py voo         # parâmetros de voo
    python centralControle/inspecionar.py tudo        # tudo acima

Uso pela IDE (Python Console):
    from centralControle.inspecionar import inspecionar_motor
    inspecionar_motor()
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.calculos.motor import derivar_motor
from src.modelo import resolver


# ============================================================
#  Helpers de formatação
# ============================================================
LARGURA = 72


def _titulo(txt: str) -> None:
    print()
    print("═" * LARGURA)
    print(f"  {txt}")
    print("═" * LARGURA)


def _sub(txt: str) -> None:
    print()
    print(f"── {txt} ──")


def _linha(label: str, valor, unidade: str = "", largura: int = 30) -> None:
    if unidade:
        print(f"  {label:<{largura}} {valor} {unidade}")
    else:
        print(f"  {label:<{largura}} {valor}")


def _fmt(v, casas: int = 4, unidade: str = "") -> str:
    if v is None:
        return "(—)"
    s = f"{v:.{casas}f}"
    return f"{s} {unidade}" if unidade else s


def _barra() -> None:
    print()


# ============================================================
#  MOTOR
# ============================================================
def inspecionar_motor() -> None:
    """Spec do motor + derivado + balística interna."""
    from configs import MOTOR_IREC

    spec = MOTOR_IREC
    d = derivar_motor(spec)

    _titulo("MOTOR — SPEC (fonte)")
    _linha("nome", spec.nome)
    _linha("fonte", "ric" if spec.ric_path else "eng")
    _linha("ric_path", spec.ric_path or "—")
    _linha("thrust_curve", spec.thrust_curve_path or "—")

    _sub(f"Grãos ({len(spec.grains)})")
    for i, g in enumerate(spec.grains):
        print(f"  [{i}]  L={g.length:.4f} m   "
              f"r_o={g.outer_radius:.5f} m   "
              f"r_i={g.inner_radius:.5f} m")
    _linha("separação", _fmt(spec.grain_separation * 1000, 1, "mm"))
    _linha("ρ propelente", _fmt(spec.propellant_density, 1, "kg/m³"))

    _sub("Carcaça")
    _linha("raio interno", _fmt(spec.case_inner_radius * 1000, 3, "mm"))
    _linha("espessura parede", _fmt(spec.case_wall_thickness * 1000, 3, "mm"))
    _linha("ρ carcaça", _fmt(spec.case_density, 1, "kg/m³"))
    _linha("comprimento", _fmt(spec.case_length, 4, "m"))
    _linha("massa seca (medida)", _fmt(spec.dry_mass, 4, "kg"))

    _sub("Tubeira")
    _linha("posição", _fmt(spec.nozzle_position * 1000, 2, "mm"))
    _linha("r de saída", _fmt(spec.nozzle_exit_radius * 1000, 2, "mm"))
    _linha("r da garganta", _fmt(spec.throat_radius * 1000, 2, "mm"))

    # ---------------- DERIVADO ----------------
    _titulo("MOTOR — DERIVADO")

    _sub("Cinemática")
    _linha("burn_time", f"{d.burn_time[0]:.3f} → {d.burn_time[1]:.3f} s")
    _linha("impulso total", _fmt(d.total_impulse, 1, "N·s"))
    _linha("empuxo máximo", _fmt(d.max_thrust, 1, "N"))
    dur = d.burn_time[1] - d.burn_time[0]
    _linha("empuxo médio", _fmt(d.total_impulse / dur, 1, "N") if dur else "—")
    _linha("ISP entregue", _fmt(d.isp_entregue, 2, "s"))

    _sub("Geometria / Massas")
    _linha("massa propelente", _fmt(d.propellant_mass, 4, "kg"))
    _linha("comprimento propelente", _fmt(d.propellant_length, 4, "m"))
    _linha("stack length", _fmt(d.stack_length, 4, "m"))
    _linha("CG do propelente (local)", _fmt(d.cg_propellant, 4, "m"))
    _linha("r_i efetivo", _fmt(d.grain_inner_radius_effective * 1000, 3, "mm"))
    _linha("massa seca", _fmt(d.dry_mass, 4, "kg"))
    _linha("massa carregada", _fmt(d.mass_loaded, 4, "kg"))

    _sub("Inércia seca (aproximação cilíndrica)")
    _linha("I_11 (roll)",  _fmt(d.dry_inertia[0], 6, "kg·m²"))
    _linha("I_22 (pitch)", _fmt(d.dry_inertia[1], 6, "kg·m²"))
    _linha("I_33 (yaw)",   _fmt(d.dry_inertia[2], 6, "kg·m²"))

    if d.p0_pico is not None:
        _sub("Balística interna")
        _linha("P0 de pico", _fmt(d.p0_pico / 1e6, 3, "MPa"))
        _linha("Kn de pico", _fmt(d.kn_pico, 1))
        _linha("mass flux de pico", _fmt(d.mass_flux_pico, 3, "kg/(m²·s)"))


# ============================================================
#  ESTRUTURA (corpo + coifa + aletas)
# ============================================================
def inspecionar_estrutura() -> None:
    """Agregado do foguete + tabelas detalhadas."""
    from configs import (
        COMPONENTES, ALETA_IREC, COIFA_IREC, FOGUETE, MOTOR_POSITION,
    )

    r = resolver(
        componentes=COMPONENTES,
        spec_aleta=ALETA_IREC,
        spec_coifa=COIFA_IREC,
        raio=FOGUETE["radius"],
    )

    # ---- AGREGADO ----
    _titulo("ESTRUTURA — AGREGADO")
    _linha("raio externo", _fmt(r.raio * 1000, 1, "mm"))
    _linha("massa seca", _fmt(r.massa_seca, 4, "kg"))
    _linha("CG sem motor", _fmt(r.cg_sem_motor, 4, "m"))
    _linha("I_xx (roll)", _fmt(r.inercia_longitudinal, 6, "kg·m²"))
    _linha("I_yy (pitch)", _fmt(r.inercia_transversal, 6, "kg·m²"))

    # ---- COMPRIMENTOS ----
    comp_modulos = sum(c.comprimento for c in COMPONENTES
                       if c.nome.startswith("Módulo"))
    fim_corpo = COIFA_IREC.length + comp_modulos
    comp_total = max(fim_corpo, MOTOR_POSITION)

    _sub("Comprimentos")
    _linha("coifa", _fmt(COIFA_IREC.length, 4, "m"))
    _linha("corpo (4 módulos)", _fmt(comp_modulos, 4, "m"))
    _linha("fim do corpo", _fmt(fim_corpo, 4, "m"))
    _linha("posição do motor (tubeira)", _fmt(MOTOR_POSITION, 4, "m"))
    _linha("COMPRIMENTO TOTAL", _fmt(comp_total, 4, "m"))

    # ---- COMPONENTES ----
    _titulo("COMPONENTES (nariz → cauda)")
    print(f"  {'#':>2}  {'nome':<30} {'massa':>8} {'pos':>7} "
          f"{'L':>7} {'r_e':>7} {'r_i':>7}")
    print(f"  {'-'*2}  {'-'*30} {'-'*8} {'-'*7} "
          f"{'-'*7} {'-'*7} {'-'*7}")

    for i, (spec, deriv) in enumerate(zip(COMPONENTES, r.componentes)):
        if hasattr(spec, "raio_externo"):
            re = spec.raio_externo * 1000
            ri = spec.raio_interno * 1000
            L = spec.comprimento
            print(f"  {i:>2}  {spec.nome:<30} {deriv.massa:>8.4f} "
                  f"{spec.posicao:>7.4f} {L:>7.4f} {re:>7.1f} {ri:>7.1f}")
        else:
            print(f"  {i:>2}  {spec.nome:<30} {deriv.massa:>8.4f} "
                  f"{spec.posicao:>7.4f} {'—':>7} {'—':>7} {'—':>7}")

    # ---- ALETAS ----
    _titulo("ALETAS")
    _linha("quantidade", ALETA_IREC.n)
    _linha("root_chord", _fmt(ALETA_IREC.root_chord, 4, "m"))
    _linha("tip_chord", _fmt(ALETA_IREC.tip_chord, 4, "m"))
    _linha("span_le", _fmt(ALETA_IREC.span_le, 4, "m"))
    _linha("span_te", _fmt(ALETA_IREC.span_te, 4, "m"))
    _linha("sweep_length", _fmt(ALETA_IREC.sweep_length, 4, "m"))
    _linha("espessura", _fmt(ALETA_IREC.thickness, 4, "m"))
    _linha("posição", _fmt(ALETA_IREC.position, 4, "m"))
    _linha("cant_angle", _fmt(ALETA_IREC.cant_angle, 2, "°"))

    a = r.aleta
    _sub("Derivadas")
    _linha("área unitária", _fmt(a.area_planform, 6, "m²"))
    _linha("massa unitária", _fmt(a.massa_unitaria, 4, "kg"))
    _linha("massa total", _fmt(a.massa_total, 4, "kg"))
    _linha("CG axial", _fmt(a.X_cg_absoluto, 4, "m"))
    _linha("r_cg", _fmt(a.r_cg, 4, "m"))
    _linha("I_xx (todas)", _fmt(a.I_xx, 6, "kg·m²"))
    _linha("I_yy local", _fmt(a.I_yy_local, 6, "kg·m²"))

    # ---- COIFA ----
    _titulo("COIFA")
    cf = r.coifa
    _linha("kind", COIFA_IREC.kind)
    _linha("comprimento", _fmt(COIFA_IREC.length, 4, "m"))
    _linha("espessura", _fmt(COIFA_IREC.thickness * 1000, 3, "mm"))
    _linha("ρ casca", _fmt(COIFA_IREC.densidade, 1, "kg/m³"))
    _linha("massa_extra", _fmt(COIFA_IREC.massa_extra, 4, "kg"))

    _sub("Derivadas")
    _linha("massa total", _fmt(cf.massa, 4, "kg"))
    _linha("CG", _fmt(cf.cg, 4, "m"))
    _linha("I_xx local", _fmt(cf.I_xx_local, 6, "kg·m²"))
    _linha("I_yy local", _fmt(cf.I_yy_local, 6, "kg·m²"))


# ============================================================
#  SEGURANÇA
# ============================================================
def inspecionar_seguranca() -> None:
    """Diagnósticos de segurança do motor."""
    from configs import MOTOR_IREC

    d = derivar_motor(MOTOR_IREC)

    _titulo("DIAGNÓSTICOS DE SEGURANÇA")
    if not d.diagnosticos:
        print("  (sem diagnósticos — fonte é .eng)")
        return

    for diag in d.diagnosticos:
        print(diag.linha())

    ok = all(x.ok for x in d.diagnosticos)
    _barra()
    print(f"  RESULTADO: {'✓ Todos passaram' if ok else '✗ Há alertas'}")


# ============================================================
#  VOO
# ============================================================
def inspecionar_voo() -> None:
    """Parâmetros de voo e atmosfera."""
    from configs import IREC, IREC_E, IREC_ENSEMBLE_E
    from src.ambiente import build_irec

    _titulo("PARÂMETROS DE VOO")

    _sub("Nominal (IREC)")
    _linha("inclinação", _fmt(IREC["inclination"], 1, "°"))
    _linha("heading", _fmt(IREC["heading"], 1, "°"))
    _linha("rail_length", _fmt(IREC["rail_length"], 2, "m"))

    _sub("Estocástico (Monte Carlo)")
    _linha("rail_length σ", _fmt(IREC_E["rail_length"] * 1000, 1, "mm"))
    _linha("inclinação σ", _fmt(IREC_E["inclination"], 2, "°"))
    _linha("heading σ", _fmt(IREC_E["heading"], 2, "°"))
    _linha("elevation σ", _fmt(IREC_ENSEMBLE_E.get("elevation"), 2, "m"))

    env = build_irec()
    _sub("Atmosfera (Environment)")
    _linha("data", env.date)
    _linha("latitude", _fmt(env.latitude, 5, "°"))
    _linha("longitude", _fmt(env.longitude, 5, "°"))
    _linha("elevação", _fmt(env.elevation, 1, "m"))


# ============================================================
#  TUDO
# ============================================================
def inspecionar_tudo() -> None:
    """Chama todas as seções em ordem."""
    inspecionar_motor()
    inspecionar_estrutura()
    inspecionar_seguranca()
    inspecionar_voo()
    print()


# ============================================================
#  CLI
# ============================================================
FUNCOES = {
    "motor":     inspecionar_motor,
    "estrutura": inspecionar_estrutura,
    "seguranca": inspecionar_seguranca,
    "voo":       inspecionar_voo,
    "tudo":      inspecionar_tudo,
}


def main() -> None:
    p = argparse.ArgumentParser(
        description="Inspeciona a configuração do foguete Hefesto"
    )
    p.add_argument(
        "alvo",
        choices=list(FUNCOES.keys()),
        nargs="?",
        default="tudo",
        help="o que inspecionar (default: tudo)",
    )
    args = p.parse_args()
    FUNCOES[args.alvo]()


if __name__ == "__main__":
    inspecionar_estrutura()