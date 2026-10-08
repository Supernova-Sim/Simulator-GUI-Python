# configs/foguetes/hefesto/recuperacao.py
"""Paraquedas do Hefesto (nominal)."""

REEFED   = {"name": "reefed",   "cd_s": 0.85, "radius": 0.6,      "trigger": "apogee", "lag": 1}
UNREEFED = {"name": "unreefed", "cd_s": 1.5,  "radius": 3.8 / 2,  "trigger": 450,      "lag": 1}