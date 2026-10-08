"""Deriva massa e inércia dos componentes a partir de specs.

Cada spec de `configs/componentes.py` é traduzida num `ComponenteDerivado`
com massa, posição axial e inércias locais (roll + transversal).
"""
import math
from dataclasses import dataclass

from configs import TuboSpec, MassaPontualSpec, COMPONENTES


# ============================================================
#  Saída
# ============================================================

@dataclass(frozen=True)
class ComponenteDerivado:
    nome: str
    massa: float              # kg
    posicao: float            # m — CG axial (x=0 no nariz)
    I_xx_local: float         # kg·m² — em torno do eixo longitudinal
    I_yy_local: float         # kg·m² — transversal, passando pelo próprio CG


# ============================================================
#  Derivações por tipo
# ============================================================

def derivar_tubo(spec: TuboSpec) -> ComponenteDerivado:
    """Cilindro oco. Fórmulas padrão para casca cilíndrica.

    A massa_extra (parafusos, cola, flanges) é somada à massa estrutural
    e tratada como se estivesse distribuída na mesma casca — aproximação
    razoável quando não se sabe a posição exata dessa massa extra.
    """
    r_e, r_i, L = spec.raio_externo, spec.raio_interno, spec.comprimento

    volume = math.pi * (r_e**2 - r_i**2) * L
    massa = volume * spec.densidade + spec.massa_extra

    # Roll: eixo longitudinal passando pelo CG do cilindro
    I_xx = 0.5 * massa * (r_e**2 + r_i**2)

    # Transversal: eixo perpendicular ao longitudinal, pelo CG
    I_yy = (massa / 12.0) * (3.0 * (r_e**2 + r_i**2) + L**2)

    return ComponenteDerivado(
        nome=spec.nome,
        massa=massa,
        posicao=spec.posicao,
        I_xx_local=I_xx,
        I_yy_local=I_yy,
    )


def derivar_massa_pontual(spec: MassaPontualSpec) -> ComponenteDerivado:
    """Massa fixa com geometria equivalente aproximada.

    `raio_equivalente` e `comprimento` não afetam a massa — só a inércia.
    """
    m = spec.massa
    r = spec.raio_equivalente
    L = spec.comprimento

    # Aproximação como disco sólido de raio r
    I_xx = 0.5 * m * r**2

    # Aproximação como cilindro sólido
    I_yy = (m / 12.0) * (3.0 * r**2 + L**2)

    return ComponenteDerivado(
        nome=spec.nome,
        massa=m,
        posicao=spec.posicao,
        I_xx_local=I_xx,
        I_yy_local=I_yy,
    )


# ============================================================
#  Dispatch e agregação
# ============================================================

def derivar(componente: TuboSpec | MassaPontualSpec) -> ComponenteDerivado:
    if isinstance(componente, TuboSpec):
        return derivar_tubo(componente)
    if isinstance(componente, MassaPontualSpec):
        return derivar_massa_pontual(componente)
    raise TypeError(f"Tipo de componente não suportado: {type(componente).__name__}")


def derivar_todos(
    componentes: list[TuboSpec | MassaPontualSpec],
) -> list[ComponenteDerivado]:
    return [derivar(c) for c in componentes]


# ============================================================
#  Inspeção rápida
# ============================================================

def main() -> None:
    derivados = derivar_todos(COMPONENTES)

    massa_total = sum(d.massa for d in derivados)
    momento = sum(d.massa * d.posicao for d in derivados)
    cg = momento / massa_total

    I_xx = sum(d.I_xx_local for d in derivados)
    I_yy = sum(
        d.I_yy_local + d.massa * (d.posicao - cg) ** 2
        for d in derivados
    )

    print(f"n componentes:      {len(derivados)}")
    print(f"massa total:        {massa_total:.4f} kg")
    print(f"CG (x=0 no nariz):  {cg:.4f} m")
    print(f"I_xx (roll):        {I_xx:.6f} kg·m²")
    print(f"I_yy (pitch/yaw):   {I_yy:.4f} kg·m²")

    # --- Validações ---
    assert len(derivados) == 24, f"esperava 24 componentes, obtive {len(derivados)}"
    assert 18.0 < massa_total < 21.0, f"massa suspeita: {massa_total}"
    assert 1.3 < cg < 1.45, f"CG suspeito: {cg}"
    assert 0.05 < I_xx < 0.10, f"I_xx suspeito: {I_xx}"
    assert 8.0 < I_yy < 9.5, f"I_yy suspeito: {I_yy}"

    print("\n✓ componentes OK")


if __name__ == "__main__":
    main()