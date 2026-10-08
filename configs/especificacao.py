"""Especificações de entrada — o que você define, não o que se calcula."""
from dataclasses import dataclass

from configs.materiais import ALUMINIO_6061


@dataclass(frozen=True)
class AletaSpec:
    """Aleta trapezoidal. Todas as unidades em SI."""
    nome: str
    n: int
    root_chord: float       # m — corda na raiz (Cr)
    tip_chord: float        # m — corda na ponta (Ct)
    span_le: float          # S_LE — envergadura da ponta no bordo de ataque
    span_te: float          # S_TE — envergadura da ponta no bordo de fuga
    sweep_length: float     # m — recuo do bordo de ataque da ponta (XR)
    thickness: float        # m — espessura (t)
    position: float         # m — posição axial do bordo de ataque da raiz (XB)
    densidade: float        # kg/m³
    cant_angle: float = 0.0 # °


# ============================================================
#  AQUI VOCÊ TROCA A ALETA
# ============================================================

# Solução #1 do otimizador
ALETA_IREC = AletaSpec(
    nome="IREC 2026 — Solução #1",
    n=4,
    root_chord=0.2267,
    tip_chord=0.0699,
    span_le=0.19179,
    span_te=0.17133,
    sweep_length=0.008,
    thickness=0.0119,
    position=2.2369,
    densidade=ALUMINIO_6061,
)

from configs.materiais import COIFA_EFETIVA


@dataclass(frozen=True)
class CoifaSpec:
    """Coifa de foguete. Todas as unidades em SI.

    Modelada como casca de espessura constante (t << L) sobre o perfil
    geométrico do `kind`. Massa e inércia vêm de integração numérica.
    """
    nome: str
    length: float                       # m — comprimento axial
    kind: str                           # "lvhaack" | "conical" | "ogive"
    position: float                     # m — posição do bico em coords do foguete
    thickness: float                    # m — espessura da casca
    densidade: float                    # kg/m³ — densidade efetiva da casca
    massa_extra: float = 0.0            # kg — aviônica, peso de bico, etc.
    posicao_massa_extra: float | None = None  # None → CG da casca


COIFA_IREC = CoifaSpec(
    nome="Coifa Hefesto",
    length=0.45,
    kind="lvhaack",
    position=0.0,
    thickness=0.003,
    densidade=COIFA_EFETIVA,
    massa_extra=1.300 - 0.8724,          # ← calibrar na Etapa C3
    posicao_massa_extra=0.0,
)

