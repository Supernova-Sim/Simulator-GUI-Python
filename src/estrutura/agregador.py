# src/estrutura/agregador.py
"""Combina specs e derivados num `FogueteResolvido` (Modo Calculado).

Agrega massa seca, CG sem motor e momentos de inércia pelo Teorema de Steiner,
entregando a tupla de inércia na convenção exata do RocketPy:
`(I_11, I_22, I_33) = (I_transversal, I_transversal, I_longitudinal)`.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.especificacoes import AletaSpec, CoifaSpec, MassaPontualSpec, TuboSpec
from src.estrutura.aletas import AletaDerivada, calcular_aleta
from src.estrutura.coifa import CoifaDerivada, calcular_coifa
from src.estrutura.componentes import ComponenteDerivado, derivar_todos


@dataclass(frozen=True)
class FogueteResolvido:
    """Parâmetros estruturais resolvidos analiticamente (`modo='calculado'`)."""
    componentes: list[ComponenteDerivado]
    spec_aleta: AletaSpec
    aleta: AletaDerivada
    spec_coifa: CoifaSpec
    coifa: CoifaDerivada
    raio: float               # m — raio externo do corpo do foguete

    @property
    def massa_seca(self) -> float:
        return sum(c.massa for c in self.componentes) + self.coifa.massa + self.aleta.massa_total

    @property
    def cg_sem_motor(self) -> float:
        partes = (
            [(c.massa, c.posicao) for c in self.componentes]
            + [(self.coifa.massa, self.coifa.cg)]
            + [(self.aleta.massa_total, self.aleta.X_cg_absoluto)]
        )
        m_total = sum(m for m, _ in partes)
        return sum(m * x for m, x in partes) / m_total

    @property
    def inercia_longitudinal(self) -> float:
        """Momento de inércia axial / roll (eixo de simetria e_3 do RocketPy)."""
        return sum(c.I_xx_local for c in self.componentes) + self.coifa.I_xx_local + self.aleta.I_xx

    @property
    def inercia_transversal(self) -> float:
        """Momento de inércia transversal / pitch-yaw (eixos e_1 e e_2 do RocketPy)."""
        cg = self.cg_sem_motor
        i_comp = sum(c.I_yy_local + c.massa * (c.posicao - cg) ** 2 for c in self.componentes)
        i_coifa = self.coifa.I_yy_local + self.coifa.massa * (self.coifa.cg - cg) ** 2
        i_aleta = self.aleta.I_yy_local + self.aleta.massa_total * (self.aleta.X_cg_absoluto - cg) ** 2
        return i_comp + i_coifa + i_aleta

    @property
    def inercia_rocketpy(self) -> tuple[float, float, float]:
        """Convenção RocketPy: (I_11, I_22, I_33) = (transversal, transversal, longitudinal)."""
        i_t = self.inercia_transversal
        return (i_t, i_t, self.inercia_longitudinal)


def resolver(
    componentes: Sequence[TuboSpec | MassaPontualSpec],
    spec_aleta: AletaSpec,
    spec_coifa: CoifaSpec,
    raio: float,
) -> FogueteResolvido:
    """Combina componentes + coifa + aleta num `FogueteResolvido`."""
    return FogueteResolvido(
        componentes=derivar_todos(componentes),
        spec_aleta=spec_aleta,
        aleta=calcular_aleta(spec_aleta, r_rocket=raio),
        spec_coifa=spec_coifa,
        coifa=calcular_coifa(spec_coifa, raio_base=raio),
        raio=raio,
    )
