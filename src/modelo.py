# src/modelo.py — bloco de imports no topo (linhas 1-9)
"""Combina specs e derivados num 'foguete resolvido' pronto para o RocketPy."""
from dataclasses import dataclass

from configs import AletaSpec, CoifaSpec, TuboSpec, MassaPontualSpec
from src.calculos.aletas import AletaDerivada, calcular_aleta
from src.calculos.componentes import ComponenteDerivado, derivar_todos
from src.calculos.coifa import CoifaDerivada, calcular_coifa


@dataclass(frozen=True)
class FogueteResolvido:
    """Todos os parâmetros do foguete — definidos + calculados.

    `componentes` contém o corpo (tudo que não é coifa nem aleta).
    Coifa e aletas vêm separadas por terem geometria própria.
    """
    componentes: list[ComponenteDerivado]
    spec_aleta: AletaSpec
    aleta: AletaDerivada
    spec_coifa: CoifaSpec
    coifa: CoifaDerivada
    raio: float               # m — raio externo do corpo do foguete

    # ---------- Agregados ----------

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
        # Roll: sem Steiner (todos os componentes são centrados no eixo).
        I_comp = sum(c.I_xx_local for c in self.componentes)
        return I_comp + self.coifa.I_xx_local + self.aleta.I_xx

    @property
    def inercia_transversal(self) -> float:
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

    # ---------- Saídas para o RocketPy ----------

    def dict_rocket(self, power_off_drag: str, power_on_drag: str) -> dict:
        I_t = self.inercia_transversal
        I_l = self.inercia_longitudinal
        return {
            "radius": self.raio,
            "mass": self.massa_seca,
            "inertia": (I_l, I_t, I_t),
            "center_of_mass_without_motor": self.cg_sem_motor,
            "coordinate_system_orientation": "nose_to_tail",
            "power_off_drag": power_off_drag,
            "power_on_drag": power_on_drag,
        }

    def dict_coifa(self) -> dict:
        return {
            "length": self.spec_coifa.length,
            "kind":   self.spec_coifa.kind,
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
    componentes: list[TuboSpec | MassaPontualSpec],
    spec_aleta: AletaSpec,
    spec_coifa: CoifaSpec,
    raio: float,
) -> FogueteResolvido:
    """Combina componentes + coifa + aleta num foguete resolvido."""
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

def main() -> None:
    """Smoke test: resolve o foguete Hefesto."""
    from configs import COMPONENTES, ALETA_IREC, COIFA_IREC, FOGUETE

    r = resolver(
        componentes=COMPONENTES,
        spec_aleta=ALETA_IREC,
        spec_coifa=COIFA_IREC,
        raio=FOGUETE["radius"],
    )

    print(f"massa seca:  {r.massa_seca:.4f} kg")
    print(f"CG:          {r.cg_sem_motor:.4f} m")
    print(f"I_xx:        {r.inercia_longitudinal:.4f} kg·m²")
    print(f"I_yy:        {r.inercia_transversal:.4f} kg·m²")

    # Sanidade — faixas calibradas contra o Hefesto real
    assert 22.0 < r.massa_seca < 27.0, f"massa suspeita: {r.massa_seca}"
    assert 1.0 < r.cg_sem_motor < 2.0, f"CG suspeito: {r.cg_sem_motor}"
    assert 0.10 < r.inercia_longitudinal < 0.25, f"I_xx suspeito: {r.inercia_longitudinal}"
    assert 12.0 < r.inercia_transversal < 15.0, f"I_yy suspeito: {r.inercia_transversal}"
    print("\n✓ modelo OK")


if __name__ == "__main__":
    main()