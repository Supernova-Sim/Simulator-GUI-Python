"""Varredura de apogeu em função de (fator_empuxo × fator_arrasto)."""
import csv
import json
from datetime import datetime

import numpy as np
from rocketpy import Flight

from hefesto.ambiente import build_irec
from hefesto.modelos import build_rocket
from hefesto.paths import RESULTADOS
from hefesto.calculos.motor import derivar_motor
from configs.voo import IREC
from configs.especificacao import ALETA_IREC
from configs.motor.medusa import MOTOR_IREC


# ============================================================
#  AQUI VOCÊ AJUSTA
# ============================================================
TIPO_ALETAS     = "freeform"
USAR_SPEC_ALETA = True

FATORES_EMPUXO  = list(np.arange(0.90, 1.11, 0.01))   # 21 valores
FATORES_ARRASTO = [1.00]                              # só nominal → 1D

ARQUIVO_SAIDA = "varredura.csv"
# ============================================================


def simular(fator_empuxo: float, fator_arrasto: float) -> dict:
    foguete = build_rocket(
        tipo_aletas=TIPO_ALETAS,
        spec_aleta=ALETA_IREC if USAR_SPEC_ALETA else None,
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

    # --- CSV principal (uma linha por simulação) ---
    destino = RESULTADOS / ARQUIVO_SAIDA
    with destino.open("w", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)

    # --- Metadata fixa do run (spec + derivado) ---
    meta = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "configuracao": {
            "tipo_aletas": TIPO_ALETAS,
            "usar_spec_aleta": USAR_SPEC_ALETA,
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