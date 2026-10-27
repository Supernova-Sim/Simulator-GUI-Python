# src/paths.py
"""Caminhos canônicos de dados e artefatos do projeto."""
from __future__ import annotations

from pyprojroot import here

RAIZ = here()
DATA = RAIZ / "data"
ENTRADA = DATA / "entrada"
SAIDA = DATA / "saida"

# Alias de compatibilidade
RESULTADOS = SAIDA

ATMOSFERA = ENTRADA / "atmosfera"
MOTORES = ENTRADA / "motores"
ARRASTO = ENTRADA / "arrasto"
OPENMOTOR = ENTRADA / "openmotor"
OPENROCKET = ENTRADA / "openrocket"

SAIDA.mkdir(parents=True, exist_ok=True)
