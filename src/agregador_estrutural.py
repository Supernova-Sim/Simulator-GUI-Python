# src/agregador_estrutural.py
"""Combina specs e derivados num `FogueteResolvido` (Modo Calculado).

Agrega massa seca, CG sem motor e momentos de inércia pelo Teorema de Steiner,
entregando a tupla de inércia na convenção exata do RocketPy:
`(I_11, I_22, I_33) = (I_transversal, I_transversal, I_longitudinal)`.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from src.calculos.aletas import AletaDerivada, calcular_aleta
from src.calculos.coifa import CoifaDerivada, calcular_coifa
from src.calculos.componentes import ComponenteDerivado, derivar_todos
from src.specs import AletaSpec, CoifaSpec, MassaPontualSpec, TuboSpec


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
        m_comp = sum(c.massa for c in self.componentes)
        return m_comp + self.coifa.massa + self.aleta.massa_total

    @property
    def cg_sem_motor(self) -> float:
        partes = (
            [(c.massa, c.posicao) for c in self.componentes]
            + [(self.coifa.massa, self.coifa.cg)]
            + [(self.aleta.massa_total, self.aleta.X_cg_absoluto)]
        )
        m_total = sum(m for m, _ in partes)
        momento = sum(m * x for m, x in partes)
        return momento / m_total

    @property
    def inercia_longitudinal(self) -> float:
        """Momento de inércia axial / roll (eixo de simetria e_3 do RocketPy)."""
        I_comp = sum(c.I_xx_local for c in self.componentes)
        return I_comp + self.coifa.I_xx_local + self.aleta.I_xx

    @property
    def inercia_transversal(self) -> float:
        """Momento de inércia transversal / pitch-yaw (eixos e_1 e e_2 do RocketPy)."""
        cg = self.cg_sem_motor

        I_comp = sum(
            c.I_yy_local + c.massa * (c.posicao - cg) ** 2
            for c in self.componentes
        )

        dx_coifa = self.coifa.cg - cg
        I_coifa = self.coifa.I_yy_local + self.coifa.massa * dx_coifa**2

        dx_aleta = self.aleta.X_cg_absoluto - cg
        I_aleta = self.aleta.I_yy_local + self.aleta.massa_total * dx_aleta**2

        return I_comp + I_coifa + I_aleta

    @property
    def inercia_rocketpy(self) -> tuple[float, float, float]:
        """Convenção RocketPy: (I_11, I_22, I_33) = (transversal, transversal, longitudinal)."""
        I_t = self.inercia_transversal
        I_l = self.inercia_longitudinal
        return (I_t, I_t, I_l)

    def dict_rocket(self, power_off_drag: str, power_on_drag: str) -> dict[str, Any]:
        return {
            "radius": self.raio,
            "mass": self.massa_seca,
            "inertia": self.inercia_rocketpy,
            "center_of_mass_without_motor": self.cg_sem_motor,
            "coordinate_system_orientation": "nose_to_tail",
            "power_off_drag": str(power_off_drag),
            "power_on_drag": str(power_on_drag),
        }

    def dict_coifa(self) -> dict[str, Any]:
        return {
            "length": self.spec_coifa.length,
            "kind": self.spec_coifa.kind,
            "position": self.spec_coifa.position,
        }

    def shape_points(self) -> list[tuple[float, float]]:
        s = self.spec_aleta
        return [
            (0.0, 0.0),
            (s.sweep_length, s.span_le),
            (s.sweep_length + s.tip_chord, s.span_te),
            (s.root_chord, 0.0),
        ]


def resolver(
    componentes: Sequence[TuboSpec | MassaPontualSpec],
    spec_aleta: AletaSpec,
    spec_coifa: CoifaSpec,
    raio: float,
) -> FogueteResolvido:
    """Combina componentes + coifa + aleta num `FogueteResolvido`."""
    derivados = derivar_todos(componentes)
    aleta = calcular_aleta(spec_aleta, r_rocket=raio)
    coifa = calcular_coifa(spec_coifa, raio_base=raio)
    return FogueteResolvido(
        componentes=derivados,
        spec_aleta=spec_aleta,
        aleta=aleta,
        spec_coifa=spec_coifa,
        coifa=coifa,
        raio=raio,
    )
