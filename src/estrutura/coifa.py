# src/estrutura/coifa.py
"""Deriva massa, CG e inércia de uma `CoifaSpec` por integração numérica.

A coifa é tratada como uma casca fina (t << L) de espessura constante sobre
o perfil `r(x)` do formato escolhido (`x=0` no bico, `x=L` na base).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from src.especificacoes import CoifaSpec


def _perfil_conico(x: float, L: float, R: float) -> float:
    return R * x / L


def _perfil_lvhaack(x: float, L: float, R: float) -> float:
    """LV-Haack (von Kármán quando C=0)."""
    arg = max(-1.0, min(1.0, 1.0 - 2.0 * x / L))
    theta = math.acos(arg)
    val = theta - math.sin(2.0 * theta) / 2.0
    return R / math.sqrt(math.pi) * math.sqrt(max(0.0, val))


def _perfil_ogive(x: float, L: float, R: float) -> float:
    """Ogiva tangente: ρ = (R² + L²) / (2R)."""
    rho = (R**2 + L**2) / (2.0 * R)
    return math.sqrt(max(0.0, rho**2 - (L - x) ** 2)) + R - rho


_PERFIS = {
    "conical": _perfil_conico,
    "lvhaack": _perfil_lvhaack,
    "ogive": _perfil_ogive,
}


def perfil(x: float, kind: str, L: float, R: float) -> float:
    if kind not in _PERFIS:
        raise ValueError(f"kind inválido: {kind!r}. Use: {list(_PERFIS)}")
    return _PERFIS[kind](x, L, R)


def _derivada_perfil(x: float, kind: str, L: float, R: float, eps: float = 1e-7) -> float:
    x_lo = max(0.0, x - eps)
    x_hi = min(L, x + eps)
    return (perfil(x_hi, kind, L, R) - perfil(x_lo, kind, L, R)) / (x_hi - x_lo)


@dataclass(frozen=True)
class CoifaDerivada:
    nome: str
    massa: float              # kg — casca + massa_extra
    cg: float                 # m — posição axial em coords do foguete (x=0 no nariz)
    I_xx_local: float         # kg·m² — longitudinal (roll, eixo e_3)
    I_yy_local: float         # kg·m² — transversal pelo próprio CG


def calcular_coifa(spec: CoifaSpec, raio_base: float, n: int = 200) -> CoifaDerivada:
    """Integra massa e inércia da casca ao longo do perfil axial."""
    if raio_base <= 0:
        raise ValueError(f"calcular_coifa: raio_base deve ser > 0 (recebido: {raio_base})")

    L, R, t, rho = spec.length, raio_base, spec.thickness, spec.densidade
    dx = L / n

    fatias: list[tuple[float, float, float]] = []
    m_shell = 0.0
    momento = 0.0
    I_xx = 0.0

    for i in range(n):
        x = (i + 0.5) * dx
        r = perfil(x, spec.kind, L, R)
        dr = _derivada_perfil(x, spec.kind, L, R)
        ds = math.sqrt(1.0 + dr**2) * dx
        dm = 2.0 * math.pi * r * ds * t * rho
        fatias.append((x, r, dm))
        m_shell += dm
        momento += x * dm
        I_xx += r**2 * dm

    cg_shell = momento / m_shell if m_shell > 0 else 0.0
    m_extra = spec.massa_extra
    x_extra = spec.posicao_massa_extra if spec.posicao_massa_extra is not None else cg_shell

    m_total = m_shell + m_extra
    cg_total = (m_shell * cg_shell + m_extra * x_extra) / m_total if m_total > 0 else 0.0

    I_yy_local = sum(((x - cg_total) ** 2 + r**2 / 2.0) * dm for x, r, dm in fatias)
    if m_extra > 0:
        I_yy_local += m_extra * (x_extra - cg_total) ** 2

    return CoifaDerivada(
        nome=spec.nome,
        massa=m_total,
        cg=spec.position + cg_total,
        I_xx_local=I_xx,
        I_yy_local=I_yy_local,
    )
