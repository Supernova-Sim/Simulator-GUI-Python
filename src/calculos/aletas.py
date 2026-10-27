# src/calculos/aletas.py
"""Deriva massa, CG e inércia de uma `AletaSpec`."""
from __future__ import annotations

from dataclasses import dataclass

from src.specs import AletaSpec


@dataclass(frozen=True)
class AletaDerivada:
    area_planform: float       # m² por aleta
    volume_unitario: float     # m³
    massa_unitaria: float      # kg
    massa_total: float         # kg (todas as aletas)

    x_cg_local: float          # m — do bordo de ataque da raiz
    y_cg_local: float          # m — da raiz (radial)
    X_cg_absoluto: float       # m — posição axial do CG da aleta no foguete
    r_cg: float                # m — distância radial do CG ao eixo longitudinal

    I_xx: float                # kg·m² — longitudinal (roll, eixo e_3)
    I_yy_local: float          # kg·m² — transversal (pitch/yaw, pelo próprio CG)
    r_rocket: float            # m — raio do foguete na região das aletas


def _poligono_propriedades(pts: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Área e centroide `(x_c, y_c)` de um polígono simples (fórmula de Shoelace)."""
    n = len(pts)
    soma_cruzada = 0.0
    soma_x = 0.0
    soma_y = 0.0

    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        soma_cruzada += cross
        soma_x += (x1 + x2) * cross
        soma_y += (y1 + y2) * cross

    area_signed = soma_cruzada / 2.0
    x_c = soma_x / (6.0 * area_signed)
    y_c = soma_y / (6.0 * area_signed)
    return abs(area_signed), x_c, y_c


def calcular_aleta(spec: AletaSpec, r_rocket: float) -> AletaDerivada:
    """Deriva massa, CG e inércia a partir da geometria e material."""
    if r_rocket <= 0:
        raise ValueError(f"calcular_aleta: r_rocket deve ser > 0 (recebido: {r_rocket})")

    Cr, Ct, XR, S_le, S_te, t = (
        spec.root_chord,
        spec.tip_chord,
        spec.sweep_length,
        spec.span_le,
        spec.span_te,
        spec.thickness,
    )

    pts = [
        (0.0, 0.0),
        (XR, S_le),
        (XR + Ct, S_te),
        (Cr, 0.0),
    ]
    A, x_c, y_c = _poligono_propriedades(pts)
    V_unit = A * t

    m_unit = spec.densidade * V_unit
    m_total = spec.n * m_unit

    X_abs = spec.position + x_c
    r_c = r_rocket + y_c

    I_xx = m_total * r_c**2
    I_yy_local = m_total * r_c**2 / 2.0

    return AletaDerivada(
        area_planform=A,
        volume_unitario=V_unit,
        massa_unitaria=m_unit,
        massa_total=m_total,
        x_cg_local=x_c,
        y_cg_local=y_c,
        X_cg_absoluto=X_abs,
        r_cg=r_c,
        I_xx=I_xx,
        I_yy_local=I_yy_local,
        r_rocket=r_rocket,
    )
