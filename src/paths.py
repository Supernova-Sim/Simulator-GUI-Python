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

def main() -> None:
    """Smoke test: confere que os caminhos canônicos existem."""
    esperados = [
        ("RAIZ", RAIZ), ("DATA", DATA), ("ENTRADA", ENTRADA), ("SAIDA", SAIDA),
        ("ATMOSFERA", ATMOSFERA), ("MOTORES", MOTORES),
        ("ARRASTO", ARRASTO), ("OPENMOTOR", OPENMOTOR), ("OPENROCKET", OPENROCKET),
    ]
    for nome, p in esperados:
        marca = "✓" if p.exists() else "✗"
        print(f"  {marca} {nome:<12} {p}")
        assert p.exists(), f"{nome} não existe: {p}"
    print("\n✓ paths OK")


if __name__ == "__main__":
    main()