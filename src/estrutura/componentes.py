# src/estrutura/componentes.py
"""Deriva massa e inércia dos componentes estruturais a partir de suas Specs.

Cada `TuboSpec` ou `MassaPontualSpec` é traduzida num `ComponenteDerivado`
com massa, posição axial e inércias locais (longitudinal/roll e transversal).
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from src.especificacoes import MassaPontualSpec, TuboSpec


@dataclass(frozen=True)
class ComponenteDerivado:
    nome: str
    massa: float              # kg
    posicao: float            # m — CG axial (x=0 no nariz)
    I_xx_local: float         # kg·m² — longitudinal (roll, eixo e_3)
    I_yy_local: float         # kg·m² — transversal (pitch/yaw, pelo próprio CG)


def derivar_tubo(spec: TuboSpec) -> ComponenteDerivado:
    """Cilindro oco. Fórmulas padrão para casca cilíndrica."""
    r_e, r_i, L = spec.raio_externo, spec.raio_interno, spec.comprimento
    volume = math.pi * (r_e**2 - r_i**2) * L
    massa = volume * spec.densidade + spec.massa_extra
    return ComponenteDerivado(
        nome=spec.nome,
        massa=massa,
        posicao=spec.posicao,
        I_xx_local=0.5 * massa * (r_e**2 + r_i**2),
        I_yy_local=(massa / 12.0) * (3.0 * (r_e**2 + r_i**2) + L**2),
    )


def derivar_massa_pontual(spec: MassaPontualSpec) -> ComponenteDerivado:
    """Massa fixa com geometria cilíndrica equivalente para inércia local."""
    m, r, L = spec.massa, spec.raio_equivalente, spec.comprimento
    return ComponenteDerivado(
        nome=spec.nome,
        massa=m,
        posicao=spec.posicao,
        I_xx_local=0.5 * m * r**2,
        I_yy_local=(m / 12.0) * (3.0 * r**2 + L**2),
    )


def derivar(componente: TuboSpec | MassaPontualSpec) -> ComponenteDerivado:
    if isinstance(componente, TuboSpec):
        return derivar_tubo(componente)
    if isinstance(componente, MassaPontualSpec):
        return derivar_massa_pontual(componente)
    raise TypeError(f"Tipo de componente não suportado: {type(componente).__name__}")


def derivar_todos(
    componentes: Sequence[TuboSpec | MassaPontualSpec],
) -> list[ComponenteDerivado]:
    return [derivar(c) for c in componentes]
