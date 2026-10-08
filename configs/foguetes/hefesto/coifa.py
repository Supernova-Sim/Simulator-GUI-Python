# configs/foguetes/hefesto/coifa.py
"""Especificação concreta da coifa do Hefesto."""
from configs.especificacao import CoifaSpec
from configs.material import COIFA_EFETIVA


COIFA_IREC = CoifaSpec(
    nome="Coifa Hefesto",
    length=0.45,
    kind="lvhaack",
    position=0.0,
    thickness=0.003,
    densidade=COIFA_EFETIVA,
    massa_extra=1.300 - 0.8724,
    posicao_massa_extra=0.0,
)