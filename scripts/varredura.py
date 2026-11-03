"""Varredura de apogeu em função de (fator_empuxo × fator_arrasto)."""
from __future__ import annotations

import csv
import json
from datetime import datetime

import numpy as np
from rocketpy import Flight

from configs import HEFESTO, IREC, MOTOR_IREC
from src.ambiente import build_irec
from src.calculos.motor import derivar_motor
from src.construtor_foguete import ModoFoguete, build_rocket
from src.paths import RESULTADOS

# ============================================================
#  AQUI VOCÊ AJUSTA
# ============================================================
MODO_FOGUETE: ModoFoguete = "calculado"   # "calculado" | "medido"
TIPO_ALETAS: str = "freeform"

FATORES_EMPUXO = list(np.arange(0.90, 1.11, 0.01))   # 21 valores
FATORES_ARRASTO = [1.00]                             # só nominal → 1D

ARQUIVO_SAIDA = "varredura.csv"
# ============================================================


def simular(fator_empuxo: float, fator_arrasto: float) -> dict[str, float]:
    foguete = build_rocket(
        HEFESTO,
        modo=MODO_FOGUETE,
        tipo_aletas=TIPO_ALETAS,
        fator_empuxo=fator_empuxo,
        fator_arrasto=fator_arrasto,
    )
    voo = Flight(rocket=foguete.rocket, environment=build_irec(), **IREC)
    return {
        "fator_empuxo": round(fator_empuxo, 6),
        "fator_arrasto": round(fator_arrasto, 6),
        "apogee_agl": round(voo.apogee - voo.env.elevation, 3),
        "margem_min": round(voo.min_stability_margin, 6),
    }


def main() -> None:
    total = len(FATORES_EMPUXO) * len(FATORES_ARRASTO)
    print(f"Total de simulações: {total} (modo={MODO_FOGUETE})")
    if total == 0:
        raise SystemExit("Nenhum fator definido.")

    linhas: list[dict[str, float]] = []
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
    with destino.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)

    meta = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "configuracao": {
            "modo_foguete": MODO_FOGUETE,
            "tipo_aletas": TIPO_ALETAS,
            "n_fatores_empuxo": len(FATORES_EMPUXO),
            "n_fatores_arrasto": len(FATORES_ARRASTO),
        },
        "motor_spec": MOTOR_IREC.to_dict(),
        "motor_derivado": derivar_motor(MOTOR_IREC).to_dict(),
    }
    meta_path = RESULTADOS / ARQUIVO_SAIDA.replace(".csv", "_meta.json")
    with meta_path.open("w", encoding="utf-8") as fp:
        json.dump(meta, fp, indent=2, ensure_ascii=False)

    print(f"\nCSV:  {destino}  ({len(linhas)} linhas)")
    print(f"Meta: {meta_path}")


if __name__ == "__main__":
    main()
