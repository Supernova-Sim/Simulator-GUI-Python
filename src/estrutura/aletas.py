# src/estrutura/aletas.py
"""Deriva massa, CG e inércia de uma `AletaSpec` e converte para o formato RASAero II."""
from __future__ import annotations

from dataclasses import dataclass

from src.especificacoes import AletaSpec

IN_POR_M = 1.0 / 0.0254   # 39.3700787402


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


@dataclass(frozen=True)
class AletaRASAero:
    """Campos de aleta prontos para inserção no RASAero II GUI."""
    fin_count: int
    root_chord_in: float
    span_in: float
    tip_chord_in: float
    sweep_distance_in: float
    thickness_in: float
    airfoil_section: str = "Square"

    def imprimir(self) -> None:
        print(f"  Fin Count:               {self.fin_count}")
        print(f"  Root Chord (in):         {self.root_chord_in:.4f}")
        print(f"  Span (in):               {self.span_in:.4f}")
        print(f"  Tip Chord (in):          {self.tip_chord_in:.4f}")
        print(f"  Sweep Distance (in):     {self.sweep_distance_in:.4f}")
        print(f"  Fin Thickness (in):      {self.thickness_in:.4f}")
        print(f"  Airfoil Section:         {self.airfoil_section}")


def _poligono_propriedades(pts: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Área e centroide `(x_c, y_c)` de um polígono simples (fórmula de Shoelace)."""
    n = len(pts)
    soma_cruzada = soma_x = soma_y = 0.0

    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        soma_cruzada += cross
        soma_x += (x1 + x2) * cross
        soma_y += (y1 + y2) * cross

    area_signed = soma_cruzada / 2.0
    return abs(area_signed), soma_x / (6.0 * area_signed), soma_y / (6.0 * area_signed)


def calcular_aleta(spec: AletaSpec, r_rocket: float) -> AletaDerivada:
    """Deriva massa, CG e inércia a partir da geometria e material."""
    if r_rocket <= 0:
        raise ValueError(f"calcular_aleta: r_rocket deve ser > 0 (recebido: {r_rocket})")

    area, x_c, y_c = _poligono_propriedades(spec.shape_points)
    v_unit = area * spec.thickness
    m_unit = spec.densidade * v_unit
    m_total = spec.n * m_unit
    r_c = r_rocket + y_c

    return AletaDerivada(
        area_planform=area,
        volume_unitario=v_unit,
        massa_unitaria=m_unit,
        massa_total=m_total,
        x_cg_local=x_c,
        y_cg_local=y_c,
        X_cg_absoluto=spec.position + x_c,
        r_cg=r_c,
        I_xx=m_total * r_c**2,
        I_yy_local=m_total * r_c**2 / 2.0,
        r_rocket=r_rocket,
    )


def aleta_para_rasaero(
    spec: AletaSpec,
    *,
    span_modo: str = "le",   # "le", "media", "te"
) -> AletaRASAero:
    """Converte `AletaSpec` (SI) para formato RASAero (polegadas)."""
    spans = {
        "le": spec.span_le,
        "te": spec.span_te,
        "media": (spec.span_le + spec.span_te) / 2.0,
    }
    if span_modo not in spans:
        raise ValueError(f"span_modo inválido: {span_modo!r}. Use 'le', 'media' ou 'te'.")

    return AletaRASAero(
        fin_count=spec.n,
        root_chord_in=spec.root_chord * IN_POR_M,
        span_in=spans[span_modo] * IN_POR_M,
        tip_chord_in=spec.tip_chord * IN_POR_M,
        sweep_distance_in=spec.sweep_length * IN_POR_M,
        thickness_in=spec.thickness * IN_POR_M,
    )
