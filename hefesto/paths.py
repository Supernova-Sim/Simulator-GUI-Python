from pyprojroot import here

RAIZ      = here()
DATA      = RAIZ / "data"
ENTRADA   = DATA / "entrada"
SAIDA     = DATA / "saida"           # ← era RESULTADOS
RESULTADOS = SAIDA                   # alias temporário pra não quebrar imports

ATMOSFERA = ENTRADA / "atmosfera"
MOTORES   = ENTRADA / "motores"
ARRASTO   = ENTRADA / "arrasto"
OPENMOTOR = ENTRADA / "openmotor"
OPENROCKET= ENTRADA / "openrocket"

SAIDA.mkdir(parents=True, exist_ok=True)