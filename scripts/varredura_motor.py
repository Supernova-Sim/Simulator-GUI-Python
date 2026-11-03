#!/usr/bin/env python
"""Varredura paramétrica do motor — 1 a N dimensões.

Uso Python (IDE):
    from scripts.varredura_motor import varrer_motor

    varrer_motor({"nozzle.throat": [0.030, 0.032, 0.034]})

Uso CLI (terminal):
    python centralControle/rodar.py varrer-motor \\
        --param nozzle.throat=0.030:0.038:0.002 \\
        --param grains.*.properties.coreDiameter=0.041,0.045,0.050
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import itertools
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from configs.foguetes.hefesto.motor_cfg import MOTOR_IREC, RIC_MEDUSA
from configs.foguetes.hefesto.motor_variacoes import PARAMS_LIVRES
from src.calculos.motor import derivar_motor
from src.calculos.motorlib_variacoes import validar_overrides
from src.paths import SAIDA

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


def _gerar_grid(params: dict[str, list[float]]) -> list[dict]:
    if not params:
        return []
    chaves = list(params.keys())
    grades = [params[k] for k in chaves]
    return [dict(zip(chaves, combo)) for combo in itertools.product(*grades)]


@dataclass
class LinhaVarredura:
    overrides: dict
    success: bool
    impulse: float
    empuxo_max: float
    empuxo_medio: float
    isp: float
    burn_time: float
    p0_pico: float
    kn_pico: float
    mass_flux_pico: float
    fs_carcaca: float
    ok_geral: bool
    erro: str | None = None
    curva_file: str | None = None


def _simular_um(
    ric_path: Path,
    overrides: dict,
    whitelist: set[str] | None,
    salvar_curva: bool,
    dir_curvas: Path,
) -> LinhaVarredura:
    try:
        validar_overrides(overrides, whitelist)

        spec_var = dataclasses.replace(
            MOTOR_IREC,
            ric_path=ric_path,
            overrides=dict(overrides),
            nome="(varredura)",
        )
        d = derivar_motor(spec_var)

        fs = d.diagnosticos[0].valor if d.diagnosticos else float("nan")
        ok_geral = bool(d.diagnosticos) and all(x.ok for x in d.diagnosticos)
        dur = d.burn_time[1] - d.burn_time[0]
        empuxo_medio = d.total_impulse / dur if dur > 0 else 0.0

        curva_file = None
        if salvar_curva and d.curva_empuxo is not None:
            h = hashlib.md5(
                json.dumps(overrides, sort_keys=True).encode()
            ).hexdigest()[:12]
            curva_file = str(dir_curvas / f"{h}.csv")
            dir_curvas.mkdir(parents=True, exist_ok=True)
            with open(curva_file, "w", newline="", encoding="utf-8") as fp:
                w = csv.writer(fp)
                w.writerow(["t_s", "F_N"])
                w.writerows(d.curva_empuxo)

        return LinhaVarredura(
            overrides=overrides,
            success=True,
            impulse=d.total_impulse,
            empuxo_max=d.max_thrust,
            empuxo_medio=empuxo_medio,
            isp=d.isp_entregue or float("nan"),
            burn_time=d.burn_time[1],
            p0_pico=d.p0_pico or float("nan"),
            kn_pico=d.kn_pico or float("nan"),
            mass_flux_pico=d.mass_flux_pico or float("nan"),
            fs_carcaca=fs,
            ok_geral=ok_geral,
            curva_file=curva_file,
        )
    except (KeyError, RuntimeError, TypeError, ValueError, FileNotFoundError) as e:
        return LinhaVarredura(
            overrides=overrides,
            success=False,
            impulse=float("nan"),
            empuxo_max=float("nan"),
            empuxo_medio=float("nan"),
            isp=float("nan"),
            burn_time=float("nan"),
            p0_pico=float("nan"),
            kn_pico=float("nan"),
            mass_flux_pico=float("nan"),
            fs_carcaca=float("nan"),
            ok_geral=False,
            erro=f"{type(e).__name__}: {e}",
        )


def varrer_motor(
    params: dict[str, list[float]],
    *,
    ric_path: Path | str | None = None,
    whitelist: set[str] | None = PARAMS_LIVRES,
    curvas: bool = False,
    n_jobs: int = 4,
    salvar: bool = True,
    prefixo: str = "varredura_motor",
) -> list[LinhaVarredura]:
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
        resultados = Parallel(n_jobs=n_jobs, verbose=10)(
            delayed(_simular_um)(ric_eff, ov, whitelist, curvas, DIR_CURVAS)
            for ov in grid
        )
    else:
        resultados = [
            _simular_um(ric_eff, ov, whitelist, curvas, DIR_CURVAS)
            for ov in grid
        ]

    n_ok = sum(1 for r in resultados if r.ok_geral)
    n_falha = total - n_ok
    print(f"\nConcluído: {n_ok}/{total} OK, {n_falha} com alerta/erro")

    if salvar:
        _salvar_resultados(resultados, params, ric_eff, prefixo, curvas)

    return resultados


def _salvar_resultados(
    resultados: list[LinhaVarredura],
    params: dict,
    ric_base: Path,
    prefixo: str,
    curvas: bool,
) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = DIR_VARREDURAS / f"{prefixo}_{ts}.csv"
    meta_path = DIR_VARREDURAS / f"{prefixo}_{ts}_meta.json"

    chaves_params = list(params.keys())
    cabecalho = (
        chaves_params
        + [
            "success",
            "impulse_Ns",
            "empuxo_max_N",
            "empuxo_medio_N",
            "isp_s",
            "burn_time_s",
            "p0_MPa",
            "kn",
            "mass_flux",
            "fs_carcaca",
            "ok_geral",
            "erro",
        ]
        + (["curva_file"] if curvas else [])
    )

    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(cabecalho)
        for r in resultados:
            linha = [r.overrides.get(k, "") for k in chaves_params]
            linha += [
                r.success,
                f"{r.impulse:.4f}",
                f"{r.empuxo_max:.4f}",
                f"{r.empuxo_medio:.4f}",
                f"{r.isp:.4f}",
                f"{r.burn_time:.4f}",
                f"{r.p0_pico / 1e6:.6f}",
                f"{r.kn_pico:.4f}",
                f"{r.mass_flux_pico:.4f}",
                f"{r.fs_carcaca:.4f}",
                r.ok_geral,
                r.erro or "",
            ]
            if curvas:
                linha.append(r.curva_file or "")
            w.writerow(linha)

    meta = {
        "timestamp": ts,
        "ric_base": str(ric_base),
        "params": dict(params),
        "n_simulacoes": len(resultados),
        "curvas_salvas": curvas,
        "n_ok": sum(1 for r in resultados if r.ok_geral),
    }
    with meta_path.open("w", encoding="utf-8") as fp:
        json.dump(meta, fp, indent=2, ensure_ascii=False)

    print(f"\nCSV:  {csv_path}")
    print(f"Meta: {meta_path}")
    if curvas:
        print(f"Curvas em: {DIR_CURVAS}")


def imprimir_tabela(resultados: list[LinhaVarredura], params: dict) -> None:
    chaves = list(params.keys())

    cab = "  " + "  ".join(f"{k.split('.')[-1]:>8}" for k in chaves)
    cab += f"  {'impulse':>9}  {'P0(MPa)':>8}  {'Kn':>6}  {'mflux':>7}  {'FS':>6}  {'OK':>3}"
    print(cab)
    print("  " + "-" * (len(cab) - 2))

    for r in resultados:
        linha = "  " + "  ".join(f"{r.overrides[k]:>8.4f}" for k in chaves)
        status = "✓" if r.ok_geral else "✗"
        linha += (
            f"  {r.impulse:>9.2f}  "
            f"{r.p0_pico / 1e6:>8.3f}  "
            f"{r.kn_pico:>6.1f}  "
            f"{r.mass_flux_pico:>7.1f}  "
            f"{r.fs_carcaca:>6.3f}  "
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

    resultados = varrer_motor(
        params,
        ric_path=args.ric,
        curvas=args.curvas,
        n_jobs=args.n_jobs,
        salvar=not args.sem_salvar,
        prefixo=args.prefixo,
    )

    print()
    imprimir_tabela(resultados, params)


if __name__ == "__main__":
    main()
