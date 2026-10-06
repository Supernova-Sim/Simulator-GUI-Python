"""Varredura de apogeu em função de (fator_empuxo × fator_arrasto)."""
import csv

import numpy as np
from rocketpy import Flight

from hefesto.ambiente import build_irec
from hefesto.modelos import build_rocket
from hefesto.paths import RESULTADOS
from configs.voo import IREC


# ============================================================
#  AQUI VOCÊ AJUSTA
# ============================================================
TIPO_ALETAS = "trapezio"

# Se uma lista tiver 1 elemento, a varredura é 1D na outra.
# Se as duas tiverem vários, é grade 2D.
FATORES_EMPUXO  = list(np.arange(0.90, 1.11, 0.01))   # 21 valores
FATORES_ARRASTO = [1.00]                              # só nominal → 1D

ARQUIVO_SAIDA = "varredura.csv"
# ============================================================


def simular(fator_empuxo: float, fator_arrasto: float) -> dict:
    foguete = build_rocket(
        tipo_aletas=TIPO_ALETAS,
        fator_empuxo=fator_empuxo,
        fator_arrasto=fator_arrasto,
    )
    voo = Flight(rocket=foguete.rocket, environment=build_irec(), **IREC)
    return {
        "fator_empuxo":  round(fator_empuxo, 6),
        "fator_arrasto": round(fator_arrasto, 6),
        "apogee_agl":    round(voo.apogee - voo.env.elevation, 3),
        "margem_min":    round(voo.min_stability_margin, 6),
    }


def main() -> None:
    total = len(FATORES_EMPUXO) * len(FATORES_ARRASTO)
    print(f"Total de simulações: {total}")
    if total == 0:
        raise SystemExit("Nenhum fator definido.")

    linhas: list[dict] = []
    i = 0
    for fe in FATORES_EMPUXO:
        for fa in FATORES_ARRASTO:
            i += 1
            linha = simular(float(fe), float(fa))
            linhas.append(linha)
            print(
                f"[{i:>3}/{total}] "
                f"empuxo={linha['fator_empuxo']:.3f}  "
                f"arrasto={linha['fator_arrasto']:.3f}  →  "
                f"apogeu AGL={linha['apogee_agl']:>8.1f} m  "
                f"margem={linha['margem_min']:.3f} cal"
            )

    destino = RESULTADOS / ARQUIVO_SAIDA
    with destino.open("w", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)

    print(f"\nSalvo em {destino}  ({len(linhas)} linhas)")


if __name__ == "__main__":
    main()