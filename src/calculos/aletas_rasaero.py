# src/calculos/aletas_rasaero.py
"""Converte `AletaSpec` (SI) para o formato do RASAero II (polegadas)."""
from __future__ import annotations

from dataclasses import dataclass

from src.specs import AletaSpec

IN_POR_M = 1.0 / 0.0254   # 39.3700787402


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


def aleta_para_rasaero(
    spec: AletaSpec,
    *,
    span_modo: str = "le",   # "le", "media", "te"
) -> AletaRASAero:
    """Converte `AletaSpec` (SI) para formato RASAero (polegadas)."""
    if span_modo == "le":
        span = spec.span_le
    elif span_modo == "te":
        span = spec.span_te
    elif span_modo == "media":
        span = (spec.span_le + spec.span_te) / 2.0
    else:
        raise ValueError(f"span_modo inválido: {span_modo!r}. Use 'le', 'media' ou 'te'.")

    return AletaRASAero(
        fin_count=spec.n,
        root_chord_in=spec.root_chord * IN_POR_M,
        span_in=span * IN_POR_M,
        tip_chord_in=spec.tip_chord * IN_POR_M,
        sweep_distance_in=spec.sweep_length * IN_POR_M,
        thickness_in=spec.thickness * IN_POR_M,
    )
