from pyprojroot import here

RAIZ = here()
DATA = RAIZ / "data"
ENTRADA = DATA / "entrada"
SAIDA = DATA / "saida"

# Aliases de compatibilidade — evita renomear chamadas em todo o projeto
RESULTADOS = SAIDA

ATMOSFERA  = ENTRADA / "atmosfera"
MOTORES    = ENTRADA / "motores"
ARRASTO    = ENTRADA / "arrasto"
OPENMOTOR  = ENTRADA / "openmotor"
OPENROCKET = ENTRADA / "openrocket"

SAIDA.mkdir(parents=True, exist_ok=True)