# configs/foguetes/hefesto/coifa.py
"""Especificação concreta da coifa do Hefesto."""
from __future__ import annotations

from configs.material import COIFA_EFETIVA
from src.specs import CoifaSpec

# ════════════════════════════════════════════════════════════
#  PARÂMETRO GLOBAL — parede da coifa
# ════════════════════════════════════════════════════════════
ESPESSURA_COIFA = 0.003   # m — 3 mm

COIFA_IREC = CoifaSpec(
    nome="Coifa Hefesto",
    length=0.45,
    kind="lvhaack",
    position=0.0,
    thickness=ESPESSURA_COIFA,
    densidade=COIFA_EFETIVA,
    massa_extra=1.300 - 0.8724,
    posicao_massa_extra=0.0,
)
