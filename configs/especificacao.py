# configs/especificacao.py
"""Abstrações geométricas — o que é definido, não o que se calcula.

As instâncias concretas de cada foguete ficam em
`configs/foguetes/<nome>/{aletas,coifa}.py`.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AletaSpec:
    """Aleta trapezoidal. Todas as unidades em SI."""
    nome: str
    n: int
    root_chord: float
    tip_chord: float
    span_le: float
    span_te: float
    sweep_length: float
    thickness: float
    position: float
    densidade: float
    cant_angle: float = 0.0


@dataclass(frozen=True)
class CoifaSpec:
    """Coifa modelada como casca fina sobre o perfil `kind`."""
    nome: str
    length: float
    kind: str
    position: float
    thickness: float
    densidade: float
    massa_extra: float = 0.0
    posicao_massa_extra: float | None = None