# configs/foguetes/hefesto/aletas.py
"""Especificações concretas das aletas do Hefesto."""
from configs.especificacao import AletaSpec
from configs.material import ALUMINIO_6061


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


# Aletas trapezoidais equivalentes (aproximação da freeform via osweep)
# ALETAS_TRAPEZIO_EQUIV = {
#     "n": 4,
#     "root_chord": 0.18,
#     "tip_chord": 0.07458606,
#     "span": 0.13999711,
#     "sweep_length": 0.10051811,
#     "position": 2.57,
#     "cant_angle": 0.0,
# }