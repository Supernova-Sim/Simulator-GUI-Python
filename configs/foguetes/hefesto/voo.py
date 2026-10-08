# configs/foguetes/hefesto/voo.py
"""Parâmetros de voo do Hefesto (IREC / Spaceport America)."""

IREC = {
    "inclination": 71,
    "heading": 90,
    "rail_length": 6,
}

IREC_E = {
    "rail_length":  0.01,    # 1 cm — trilho
    "inclination":  0.5,     # 0.5° — inclinação do lançador
    "heading":      1.0,     # 1° — azimute
}

IREC_ENSEMBLE_E = {"elevation": 2.0}