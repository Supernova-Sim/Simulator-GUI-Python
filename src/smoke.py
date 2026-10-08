# src/smoke.py
"""Roda o main() de cada módulo de src/ em sequência."""
import importlib

MODULOS = [
    "src.paths",
    "src.ambiente",
    "src.calculos.motorlib_wrapper",
    "src.calculos.motor",
    "src.calculos.seguranca",
    "src.calculos.componentes",
    "src.calculos.aletas",
    "src.calculos.coifa",
    "src.modelo",
    "src.modelos",
    "src.parsers.openmotor",
]


def main() -> None:
    falhas: list[tuple[str, Exception]] = []

    for nome in MODULOS:
        print(f"\n{'=' * 60}")
        print(f"  {nome}")
        print("=" * 60)
        try:
            mod = importlib.import_module(nome)
            importlib.reload(mod)
            if hasattr(mod, "main"):
                mod.main()
            else:
                print("  (sem main — ignorado)")
        except Exception as e:
            print(f"  ✗ FALHOU: {type(e).__name__}: {e}")
            falhas.append((nome, e))

    print(f"\n{'=' * 60}")
    if falhas:
        print(f"❌ {len(falhas)} módulo(s) com falha:")
        for nome, e in falhas:
            print(f"   - {nome}: {e}")
        raise SystemExit(1)
    print(f"✅ Todos os {len(MODULOS)} módulos passaram")


if __name__ == "__main__":
    main()