"""Caminhos canônicos do projeto. Importe daqui, não faça here()/data por aí."""
from pyprojroot import here

RAIZ = here()
DATA = RAIZ / "data"
RESULTADOS = RAIZ / "resultados"

ATMOSFERA = DATA / "atmosfera"
MOTORES   = DATA / "motores"
ARRASTO   = DATA / "arrasto"

RESULTADOS.mkdir(exist_ok=True)