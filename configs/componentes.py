"""Componentes do foguete — specs de entrada.

Modo C (híbrido):
  - TuboSpec:         massa = V·densidade + massa_extra
                      → mexer em raio/comprimento recalcula massa.
  - MassaPontualSpec: massa = valor fixo
                      → eletrônica, paraquedas, payload (massa do OpenRocket).

Densidades efetivas calibradas contra `inertia.py` legado.
Se a densidade real do material for conhecida, use-a e mova a diferença
para `massa_extra`.

Unidades: SI (m, kg, kg/m³). Ordem: nariz → cauda.
"""
from dataclasses import dataclass

from configs.materiais import (
    ALUMINIO_6061,
    COMPOSITO_EFETIVO,
    COIFA_EFETIVA,
)


# ============================================================
#  Tipos de componente
# ============================================================

@dataclass(frozen=True)
class TuboSpec:
    """Cilindro oco. Se r_i = 0, é um disco maciço.

    Massa = π·(r_e² − r_i²)·L·densidade + massa_extra
    """
    nome: str
    raio_externo: float       # m
    raio_interno: float       # m
    comprimento: float        # m
    posicao: float            # m — CG axial (x=0 no nariz)
    densidade: float          # kg/m³
    massa_extra: float = 0.0  # kg — parafusos, cola, flanges (fixo)


@dataclass(frozen=True)
class MassaPontualSpec:
    """Componente sem geometria cilíndrica simples.

    Massa fixa. `raio_equivalente` e `comprimento` só entram
    no cálculo de inércia.
    """
    nome: str
    massa: float              # kg
    posicao: float            # m — CG axial
    raio_equivalente: float   # m — raio p/ inércia de roll
    comprimento: float        # m — comprimento p/ inércia transversal


# ============================================================
#  Lista de componentes (migrada de inertia.py)
# ============================================================

COMPONENTES: list[TuboSpec | MassaPontualSpec] = [

    # ---------- Estrutura externa (compósito) ----------

    TuboSpec("Módulo Aviônica",           0.079, 0.076,  0.540, 0.7200, COMPOSITO_EFETIVO),
    TuboSpec("Módulo Payload",            0.079, 0.076,  0.450, 1.2150, COMPOSITO_EFETIVO),
    TuboSpec("Módulo Propulsão",          0.079, 0.076,  0.910, 1.8950, COMPOSITO_EFETIVO),
    TuboSpec("Módulo Aletas",             0.079, 0.076,  0.400, 2.5500, COMPOSITO_EFETIVO),

    # ---------- Junções (alumínio) ----------
    TuboSpec("Junção Aviônica/Payload",   0.076, 0.073,  0.200, 0.9900, ALUMINIO_6061),
    TuboSpec("Junção Payload/Propulsão",  0.076, 0.073,  0.200, 1.4400, ALUMINIO_6061),
    TuboSpec("Junção Propulsão/Aletas",   0.076, 0.073,  0.200, 2.3500, ALUMINIO_6061),

    # ---------- Fixadores (alumínio) ----------
    TuboSpec("Fixador Superior 1",        0.073, 0.063,  0.012, 0.9400, ALUMINIO_6061),
    TuboSpec("Fixador Inferior 1",        0.073, 0.063,  0.012, 1.0400, ALUMINIO_6061),
    TuboSpec("Fixador Superior 2",        0.073, 0.063,  0.012, 1.3900, ALUMINIO_6061),

    # ---------- Anéis centralizadores (alumínio) ----------
    TuboSpec("Anel centralizador inf 1",  0.073, 0.0625, 0.012, 2.3000, ALUMINIO_6061),
    TuboSpec("Anel centralizador sup 1",  0.073, 0.0625, 0.012, 2.4000, ALUMINIO_6061),
    TuboSpec("Anel centralizador sup 2",  0.076, 0.057,  0.015, 2.6225, ALUMINIO_6061),
    TuboSpec("Anel centralizador médio 2", 0.076, 0.057, 0.015, 2.6625, ALUMINIO_6061),
    TuboSpec("Anel centralizador inf 2",  0.076, 0.057,  0.015, 2.7025, ALUMINIO_6061),

    # ---------- Anteparos (discos maciços, alumínio) ----------
    TuboSpec("Anteparo Recuperação",      0.076, 0.000,  0.012, 0.6680, ALUMINIO_6061),
    TuboSpec("Anteparo Inferior",         0.073, 0.000,  0.020, 1.4900, ALUMINIO_6061),

    # ---------- Massas internas ----------
    MassaPontualSpec("Paraquedas unreefed",      0.6500, 0.4300, 0.070, 0.300),
    MassaPontualSpec("Paraquedas reefed",        0.6500, 0.4300, 0.070, 0.300),
    MassaPontualSpec("Sistemas de recuperação",  1.7670, 0.6300, 0.030, 0.060),
    MassaPontualSpec("Aviônica",                 0.7000, 0.7010, 0.050, 0.050),
    MassaPontualSpec("Satélite",                 1.4000, 1.2020, 0.071, 0.300),
    MassaPontualSpec("Complemento de massa",     2.6000, 1.3680, 0.076, 0.020),

    # ---------- Externos ----------
    MassaPontualSpec("Rail Button (conjunto)",   0.0476, 1.8450, 0.020, 0.027),
]