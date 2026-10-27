#!/usr/bin/env python
"""Análise de resultados de varredura do motor.

Lê o CSV gerado por `varredura_motor.py` e oferece:
- Carregamento (o mais recente ou específico)
- Filtros (viável, FS mínimo, P0 máximo, etc.)
- Ranking por objetivo
- Ponto ótimo sob restrições
- Plots 1D (linha) e 2D (mapa de calor)
- Resumo tabular

Uso IDE:
    from scripts.analisar_motor import (
        carregar_varredura, filtrar, rankear, achar_otimo, resumo,
    )
    regs = carregar_varredura()          # mais recente
    resumo(regs)

    viaveis = filtrar(regs, fs_min=2.5)
    top5 = rankear(viaveis, "impulse_Ns")[:5]

Uso CLI:
    python centralControle/rodar.py analisar-motor
    python centralControle/rodar.py analisar-motor --csv <path>
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

from src.paths import SAIDA

matplotlib.use("Agg")   # backend headless — evita Qt


DIR_VARREDURAS = SAIDA / "varreduras"

# Colunas que NÃO são parâmetros (do cabeçalho do CSV de varredura)
COLUNAS_FIXAS = {
    "success", "impulse_Ns", "empuxo_max_N", "empuxo_medio_N",
    "isp_s", "burn_time_s", "p0_MPa", "kn", "mass_flux",
    "fs_carcaca", "ok_geral", "erro", "curva_file",
}


# ============================================================
#  Carregamento
# ============================================================
def _ultimo_csv(dir_varreduras: Path = DIR_VARREDURAS) -> Path:
    arquivos = sorted(dir_varreduras.glob("varredura_motor_*.csv"))
    if not arquivos:
        raise FileNotFoundError(
            f"Nenhum CSV em {dir_varreduras}. Rode uma varredura primeiro."
        )
    return arquivos[-1]


def carregar_varredura(caminho: Path | str | None = None) -> list[dict]:
    """Lê o CSV de varredura como lista de dicts.

    Converte automaticamente colunas numéricas para float e
    `success`/`ok_geral` para bool.
    """
    caminho = Path(caminho) if caminho else _ultimo_csv()

    with caminho.open(encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        registros = []
        for row in reader:
            for k, v in row.items():
                if k in ("success", "ok_geral"):
                    row[k] = v.strip().lower() in ("true", "1", "yes")
                else:
                    try:
                        row[k] = float(v)
                    except (ValueError, TypeError):
                        pass  # mantém string
            registros.append(row)

    print(f"Carregado: {caminho.name}  ({len(registros)} registros)")
    return registros


def params_do_registro(registros: list[dict]) -> list[str]:
    """Nomes das colunas que são parâmetros (não fixas)."""
    if not registros:
        return []
    return [k for k in registros[0] if k not in COLUNAS_FIXAS]


# ============================================================
#  Filtros e ranking
# ============================================================
def filtrar(
    registros: list[dict],
    *,
    ok_geral: bool | None = True,
    fs_min: float | None = None,
    p0_max: float | None = None,
    kn_max: float | None = None,
    mass_flux_max: float | None = None,
    success: bool | None = True,
) -> list[dict]:
    """Filtro cumulativo. Cada kwarg é opcional."""
    out = registros

    if success is not None:
        out = [r for r in out if r.get("success") == success]

    if ok_geral is not None:
        out = [r for r in out if r.get("ok_geral") == ok_geral]

    if fs_min is not None:
        out = [r for r in out
               if isinstance(r.get("fs_carcaca"), float)
               and r["fs_carcaca"] >= fs_min]

    if p0_max is not None:
        out = [r for r in out
               if isinstance(r.get("p0_MPa"), float)
               and r["p0_MPa"] <= p0_max]

    if kn_max is not None:
        out = [r for r in out
               if isinstance(r.get("kn"), float) and r["kn"] <= kn_max]

    if mass_flux_max is not None:
        out = [r for r in out
               if isinstance(r.get("mass_flux"), float)
               and r["mass_flux"] <= mass_flux_max]

    return out


def rankear(
    registros: list[dict],
    objetivo: str = "impulse_Ns",
    ascendente: bool = False,
) -> list[dict]:
    """Ordena por objetivo (default: impulse decrescente)."""
    if not registros:
        return []
    if objetivo not in registros[0]:
        raise KeyError(
            f"Objetivo '{objetivo}' não existe. "
            f"Disponíveis: {list(registros[0].keys())}"
        )
    return sorted(
        registros,
        key=lambda r: r.get(objetivo, float("-inf")),
        reverse=not ascendente,
    )


def achar_otimo(
    registros: list[dict],
    objetivo: str = "impulse_Ns",
    *,
    ascendente: bool = False,
    **filtros,
) -> dict | None:
    """Filtra + ranqueia + devolve o melhor. None se nada passar."""
    viaveis = filtrar(registros, **filtros)
    if not viaveis:
        return None
    return rankear(viaveis, objetivo, ascendente)[0]


# ============================================================
#  Resumo
# ============================================================
def resumo(registros: list[dict]) -> None:
    """Estatísticas gerais da varredura."""
    total = len(registros)
    if total == 0:
        print("(sem registros)")
        return

    params = params_do_registro(registros)
    ok = sum(1 for r in registros if r.get("ok_geral"))
    sucesso = sum(1 for r in registros if r.get("success"))

    print()
    print("=" * 70)
    print(f"  RESUMO DA VARREDURA  ({total} registros)")
    print("=" * 70)
    print(f"  Simulações bem-sucedidas: {sucesso}/{total}")
    print(f"  Passaram TODOS os checks: {ok}/{total}")

    if params:
        print()
        print("  Parâmetros varridos:")
        for p in params:
            vals = sorted({r[p] for r in registros
                           if isinstance(r[p], (int, float))})
            if vals:
                print(f"    {p}: {len(vals)} valores  "
                      f"({vals[0]:.4f} … {vals[-1]:.4f})")

    # Cada check falhou quantas vezes?
    if ok < total:
        print()
        print("  Checks que falharam:")
        falhas: dict[str, int] = {}
        for r in registros:
            if r.get("ok_geral"):
                continue
            # Heurística: testar cada limite contra os valores
            if isinstance(r.get("fs_carcaca"), float) and r["fs_carcaca"] < 2.0:
                falhas["FS carcaça < 2.0"] = falhas.get("FS carcaça < 2.0", 0) + 1
            if isinstance(r.get("p0_MPa"), float) and r["p0_MPa"] > 8.0:
                falhas["P0 > 8 MPa"] = falhas.get("P0 > 8 MPa", 0) + 1
            if isinstance(r.get("kn"), float) and r["kn"] > 250.0:
                falhas["Kn > 250"] = falhas.get("Kn > 250", 0) + 1
            if isinstance(r.get("mass_flux"), float) and r["mass_flux"] > 1406.0:
                falhas["mass_flux > 1406"] = falhas.get("mass_flux > 1406", 0) + 1
            if isinstance(r.get("erro"), str) and r["erro"]:
                falhas["erro na simulação"] = falhas.get("erro na simulação", 0) + 1

        for k, v in sorted(falhas.items(), key=lambda x: -x[1]):
            print(f"    {k:<24} {v:>4}×")


# ============================================================
#  Plots
# ============================================================
def plotar_1d(
    registros: list[dict],
    x_param: str,
    y_param: str = "impulse_Ns",
    *,
    filtrar_viaveis: bool = True,
    salvar_em: Path | str | None = None,
):
    """Plota curva 1D. Requer apenas 1 parâmetro na varredura."""
    import matplotlib.pyplot as plt

    regs = filtrar(registros, success=True) if filtrar_viaveis else registros

    # Ordena por x
    pontos = sorted(
        [(r[x_param], r[y_param], r.get("ok_geral", False))
         for r in regs
         if isinstance(r.get(x_param), (int, float))
         and isinstance(r.get(y_param), (int, float))],
        key=lambda t: t[0],
    )

    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    ok = [p[2] for p in pontos]

    fig, ax = plt.subplots(figsize=(9, 5))

    # Linha cinza conecta tudo
    ax.plot(xs, ys, color="gray", alpha=0.5, zorder=1)

    # Pontos: verde = OK, vermelho = alerta
    xs_ok = [x for x, o in zip(xs, ok) if o]
    ys_ok = [y for y, o in zip(ys, ok) if o]
    xs_bad = [x for x, o in zip(xs, ok) if not o]
    ys_bad = [y for y, o in zip(ys, ok) if not o]

    ax.scatter(xs_ok, ys_ok, color="green", s=80, zorder=2, label="OK")
    ax.scatter(xs_bad, ys_bad, color="red", s=80, zorder=2, label="alerta")

    ax.set_xlabel(x_param)
    ax.set_ylabel(y_param)
    ax.set_title(f"{y_param} vs {x_param}")
    ax.grid(alpha=0.3)
    ax.legend()

    if salvar_em:
        plt.savefig(salvar_em, dpi=100, bbox_inches="tight")
        print(f"Plot salvo: {salvar_em}")
    else:
        plt.show()

    return fig, ax


def plotar_2d(
    registros: list[dict],
    x_param: str,
    y_param: str,
    z_param: str = "impulse_Ns",
    *,
    filtrar_viaveis: bool = True,
    salvar_em: Path | str | None = None,
):
    """Mapa de calor 2D. Requer 2 parâmetros na varredura."""
    import matplotlib.pyplot as plt
    import numpy as np

    regs = filtrar(registros, success=True) if filtrar_viaveis else registros

    xs = np.array([r[x_param] for r in regs
                   if isinstance(r.get(x_param), (int, float))
                   and isinstance(r.get(y_param), (int, float))
                   and isinstance(r.get(z_param), (int, float))])
    ys = np.array([r[y_param] for r in regs
                   if isinstance(r.get(x_param), (int, float))
                   and isinstance(r.get(y_param), (int, float))
                   and isinstance(r.get(z_param), (int, float))])
    zs = np.array([r[z_param] for r in regs
                   if isinstance(r.get(x_param), (int, float))
                   and isinstance(r.get(y_param), (int, float))
                   and isinstance(r.get(z_param), (int, float))])
    xs_unique = sorted({r[x_param] for r in regs
                        if isinstance(r.get(x_param), (int, float))})
    ys_unique = sorted({r[y_param] for r in regs
                        if isinstance(r.get(y_param), (int, float))})
    if len(xs_unique) < 2 or len(ys_unique) < 2:
        raise ValueError(
            f"plotar_2d precisa de varredura 2D. "
            f"'{x_param}' tem {len(xs_unique)} valor(es) único(s), "
            f"'{y_param}' tem {len(ys_unique)}. "
            f"Rode uma varredura com 2 parâmetros."
        )

    fig, ax = plt.subplots(figsize=(9, 7))
    tcf = ax.tricontourf(xs, ys, zs, levels=15, cmap="viridis")
    fig.colorbar(tcf, ax=ax, label=z_param)

    # Marca os pontos infactíveis com X vermelho
    for r in regs:
        if not r.get("ok_geral"):
            ax.plot(r[x_param], r[y_param], "x", color="red", markersize=8)

    ax.set_xlabel(x_param)
    ax.set_ylabel(y_param)
    ax.set_title(f"{z_param}  (✗ = alerta)")

    if salvar_em:
        plt.savefig(salvar_em, dpi=100, bbox_inches="tight")
        print(f"Plot salvo: {salvar_em}")
    else:
        plt.show()

    return fig, ax


# ============================================================
#  Impressão de top-N
# ============================================================
def imprimir_top(
    registros: list[dict],
    objetivo: str = "impulse_Ns",
    n: int = 10,
) -> None:
    if not registros:
        print("(sem registros)")
        return

    params = params_do_registro(registros)
    print()
    print("=" * 70)
    print(f"  TOP {n}  (objetivo: {objetivo})")
    print("=" * 70)

    cab = "  #  " + "  ".join(f"{p.split('.')[-1]:>9}" for p in params)
    cab += (f"  {objetivo:>10}  {'P0(MPa)':>8}  {'Kn':>6}  "
            f"{'mflux':>7}  {'FS':>6}")
    print(cab)
    print("  " + "-" * (len(cab) - 2))

    for i, r in enumerate(registros[:n], 1):
        linha = f"  {i:>2} "
        for p in params:
            v = r.get(p)
            if isinstance(v, (int, float)):
                linha += f"  {v:>9.4f}"
            else:
                linha += f"  {v!s:>9}"
        linha += (
            f"  {r.get(objetivo, float('nan')):>10.2f}  "
            f"{r.get('p0_MPa', float('nan')):>8.3f}  "
            f"{r.get('kn', float('nan')):>6.1f}  "
            f"{r.get('mass_flux', float('nan')):>7.1f}  "
            f"{r.get('fs_carcaca', float('nan')):>6.3f}"
        )
        print(linha)


# ============================================================
#  CLI
# ============================================================
def main() -> None:
    p = argparse.ArgumentParser(
        description="Analisa CSV de varredura de motor"
    )
    p.add_argument("--csv", type=Path, default=None,
                   help="CSV específico (default: mais recente)")
    p.add_argument("--fs-min", type=float, default=None,
                   help="Filtro FS mínimo")
    p.add_argument("--objetivo", default="impulse_Ns",
                   help="Coluna para maximizar (default: impulse_Ns)")
    p.add_argument("--top", type=int, default=10,
                   help="Quantos mostrar no top (default: 10)")

    args = p.parse_args()

    regs = carregar_varredura(args.csv)
    resumo(regs)

    viaveis = filtrar(regs, fs_min=args.fs_min)
    imprimir_top(viaveis, objetivo=args.objetivo, n=args.top)

    otimo = achar_otimo(regs, objetivo=args.objetivo, fs_min=args.fs_min)
    if otimo:
        print()
        print("=" * 70)
        print(f"  ÓTIMO VIÁVEL  ({args.objetivo})")
        print("=" * 70)
        for p_name in params_do_registro(regs):
            print(f"  {p_name:<40} {otimo[p_name]}")
        print(f"  {'impulse_Ns':<40} {otimo['impulse_Ns']:.2f}")
        print(f"  {'p0_MPa':<40} {otimo['p0_MPa']:.3f}")
        print(f"  {'kn':<40} {otimo['kn']:.1f}")
        print(f"  {'mass_flux':<40} {otimo['mass_flux']:.1f}")
        print(f"  {'fs_carcaca':<40} {otimo['fs_carcaca']:.3f}")
    else:
        print()
        print("⚠ Nenhum ponto viável com os filtros aplicados.")


if __name__ == "__main__":
    main()