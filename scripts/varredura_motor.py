#!/usr/bin/env python
"""Varredura paramétrica do motor — 1 a N dimensões (saída tabular em Polars).

Uso Python (IDE):
    from scripts.varredura_motor import varrer_motor

    df = varrer_motor({"nozzle.throat": [0.030, 0.032, 0.034]})

Uso CLI (terminal):
    python centralControle/rodar.py varrer-motor \\
        --param nozzle.throat=0.030:0.038:0.002 \\
        --param grains.*.properties.coreDiameter=0.041,0.045,0.050
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import itertools
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from configs.foguetes.hefesto.motor import MOTOR_IREC, PARAMS_LIVRES, RIC_MEDUSA
from src.caminhos import SAIDA
from src.especificacoes import LimitesSeguranca, validar_overrides
from src.motor.derivador import derivar_motor

RIC_PADRAO = RIC_MEDUSA
DIR_VARREDURAS = SAIDA / "varreduras"
DIR_CURVAS = DIR_VARREDURAS / "curvas"


def _parse_valores(s: str) -> list[float]:
    """Aceita 'a,b,c' ou 'start:end:step'."""
    s = s.strip()
    if ":" in s:
        partes = s.split(":")
        if len(partes) != 3:
            raise ValueError(
                f"Formato de range inválido: '{s}'. Esperado 'start:end:step'."
            )
        ini, fim, passo = (float(p) for p in partes)
        if passo <= 0:
            raise ValueError(f"Passo deve ser > 0: {passo}")
        valores = []
        v = ini
        while v <= fim + 1e-12:
            valores.append(round(v, 10))
            v += passo
        return valores

    return [float(x.strip()) for x in s.split(",") if x.strip()]


def _parse_param(s: str) -> tuple[str, list[float]]:
    if "=" not in s:
        raise ValueError(f"Formato inválido: '{s}'. Esperado 'nome=valores'.")
    nome, valores = s.split("=", 1)
    return nome.strip(), _parse_valores(valores)


def _gerar_grid(params: dict[str, list[float]]) -> list[dict[str, float]]:
    if not params:
        return []
    chaves = list(params.keys())
    return [dict(zip(chaves, combo)) for combo in itertools.product(*(params[k] for k in chaves))]


def _simular_um(
    ric_path: Path,
    overrides: dict[str, float],
    whitelist: set[str] | None,
    salvar_curva: bool,
    dir_curvas: Path,
    limites: LimitesSeguranca | None = None,
) -> dict[str, Any]:
    """Executa uma variação do `.ric` e devolve um registro tabular para DataFrame."""
    base: dict[str, Any] = dict(overrides)
    try:
        validar_overrides(overrides, whitelist)
        spec_var = dataclasses.replace(
            MOTOR_IREC,
            ric_path=ric_path,
            overrides=dict(overrides),
            nome="(varredura)",
        )
        kwargs = {"limites": limites} if limites is not None else {}
        d = derivar_motor(spec_var, **kwargs)

        fs = d.diagnosticos[0].valor if d.diagnosticos else float("nan")
        ok_geral = bool(d.diagnosticos) and all(x.ok for x in d.diagnosticos)
        dur = d.burn_time[1] - d.burn_time[0]
        empuxo_medio = d.total_impulse / dur if dur > 0 else 0.0

        curva_file = ""
        if salvar_curva and d.curva_empuxo is not None:
            h = hashlib.md5(
                json.dumps(overrides, sort_keys=True).encode()
            ).hexdigest()[:12]
            path_curva = dir_curvas / f"{h}.csv"
            dir_curvas.mkdir(parents=True, exist_ok=True)
            pl.DataFrame(
                d.curva_empuxo,
                schema=["t_s", "F_N"],
                orient="row",
            ).write_csv(path_curva)
            curva_file = str(path_curva)

        return {
            **base,
            "success": True,
            "impulse_Ns": d.total_impulse,
            "empuxo_max_N": d.max_thrust,
            "empuxo_medio_N": empuxo_medio,
            "isp_s": d.isp_entregue or float("nan"),
            "burn_time_s": d.burn_time[1],
            "p0_MPa": (d.p0_pico / 1e6) if d.p0_pico is not None else float("nan"),
            "kn": d.kn_pico if d.kn_pico is not None else float("nan"),
            "mass_flux": d.mass_flux_pico if d.mass_flux_pico is not None else float("nan"),
            "fs_carcaca": fs,
            "ok_geral": ok_geral,
            "erro": "",
            **({"curva_file": curva_file} if salvar_curva else {}),
        }
    except (KeyError, RuntimeError, TypeError, ValueError, FileNotFoundError) as e:
        return {
            **base,
            "success": False,
            "impulse_Ns": float("nan"),
            "empuxo_max_N": float("nan"),
            "empuxo_medio_N": float("nan"),
            "isp_s": float("nan"),
            "burn_time_s": float("nan"),
            "p0_MPa": float("nan"),
            "kn": float("nan"),
            "mass_flux": float("nan"),
            "fs_carcaca": float("nan"),
            "ok_geral": False,
            "erro": f"{type(e).__name__}: {e}",
            **({"curva_file": ""} if salvar_curva else {}),
        }


def varrer_motor(
    params: dict[str, list[float]],
    *,
    ric_path: Path | str | None = None,
    whitelist: set[str] | None = PARAMS_LIVRES,
    curvas: bool = False,
    n_jobs: int = 4,
    salvar: bool = True,
    prefixo: str = "varredura_motor",
    limites: LimitesSeguranca | None = None,
) -> pl.DataFrame:
    """Executa a grade paramétrica sobre o `.ric` e retorna um `polars.DataFrame`."""
    if not params:
        raise ValueError("Nenhum parâmetro definido para varredura.")

    ric_eff = Path(ric_path) if ric_path is not None else RIC_PADRAO
    for nome in params:
        validar_overrides({nome: params[nome][0]}, whitelist)

    grid = _gerar_grid(params)
    total = len(grid)
    print(f"Varredura: {len(params)} parâmetro(s) × {total} combinações")
    for nome, valores in params.items():
        print(f"  {nome}: {len(valores)} valores  ({valores[0]} … {valores[-1]})")
    print()

    try:
        from joblib import Parallel, delayed
        paralelo = True
    except ImportError:
        paralelo = False

    DIR_VARREDURAS.mkdir(parents=True, exist_ok=True)

    if paralelo and n_jobs != 1:
        registros = Parallel(n_jobs=n_jobs, verbose=10)(
            delayed(_simular_um)(ric_eff, ov, whitelist, curvas, DIR_CURVAS, limites)
            for ov in grid
        )
    else:
        registros = [
            _simular_um(ric_eff, ov, whitelist, curvas, DIR_CURVAS, limites)
            for ov in grid
        ]

    df = pl.DataFrame(registros)
    n_ok = int(df["ok_geral"].sum())
    print(f"\nConcluído: {n_ok}/{total} OK, {total - n_ok} com alerta/erro")

    if salvar:
        _salvar_resultados(df, params, ric_eff, prefixo, curvas)

    return df


def _salvar_resultados(
    df: pl.DataFrame,
    params: dict[str, list[float]],
    ric_base: Path,
    prefixo: str,
    curvas: bool,
) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = DIR_VARREDURAS / f"{prefixo}_{ts}.csv"
    meta_path = DIR_VARREDURAS / f"{prefixo}_{ts}_meta.json"

    df.write_csv(csv_path)

    meta = {
        "timestamp": ts,
        "ric_base": str(ric_base),
        "params": dict(params),
        "n_simulacoes": df.height,
        "curvas_salvas": curvas,
        "n_ok": int(df["ok_geral"].sum()),
    }
    with meta_path.open("w", encoding="utf-8") as fp:
        json.dump(meta, fp, indent=2, ensure_ascii=False)

    print(f"\nCSV:  {csv_path}")
    print(f"Meta: {meta_path}")
    if curvas:
        print(f"Curvas em: {DIR_CURVAS}")


def imprimir_tabela(df: pl.DataFrame, params: dict[str, list[float]]) -> None:
    chaves = list(params.keys())

    cab = "  " + "  ".join(f"{k.split('.')[-1]:>8}" for k in chaves)
    cab += f"  {'impulse':>9}  {'P0(MPa)':>8}  {'Kn':>6}  {'mflux':>7}  {'FS':>6}  {'OK':>3}"
    print(cab)
    print("  " + "-" * (len(cab) - 2))

    for row in df.iter_rows(named=True):
        linha = "  " + "  ".join(f"{row[k]:>8.4f}" for k in chaves)
        status = "✓" if row["ok_geral"] else "✗"
        linha += (
            f"  {row['impulse_Ns']:>9.2f}  "
            f"{row['p0_MPa']:>8.3f}  "
            f"{row['kn']:>6.1f}  "
            f"{row['mass_flux']:>7.1f}  "
            f"{row['fs_carcaca']:>6.3f}  "
            f"{status:>3}"
        )
        print(linha)


def main() -> None:
    p = argparse.ArgumentParser(description="Varredura paramétrica do motor Hefesto")
    p.add_argument(
        "--param",
        "-p",
        action="append",
        required=True,
        help="Parâmetro no formato 'nome=valores' ('a,b,c' ou 'start:end:step').",
    )
    p.add_argument("--ric", type=Path, default=None, help=f".ric base (default: {RIC_PADRAO})")
    p.add_argument("--curvas", action="store_true", help="Salva curvas (t, F) por simulação")
    p.add_argument("--n-jobs", "-j", type=int, default=4, help="Paralelismo (default: 4)")
    p.add_argument("--sem-salvar", action="store_true", help="Não salva CSV/meta")
    p.add_argument("--prefixo", default="varredura_motor", help="Prefixo dos arquivos de saída")

    args = p.parse_args()

    params: dict[str, list[float]] = {}
    for p_str in args.param:
        nome, valores = _parse_param(p_str)
        params[nome] = valores

    df = varrer_motor(
        params,
        ric_path=args.ric,
        curvas=args.curvas,
        n_jobs=args.n_jobs,
        salvar=not args.sem_salvar,
        prefixo=args.prefixo,
    )

    print()
    imprimir_tabela(df, params)


if __name__ == "__main__":
    main()
