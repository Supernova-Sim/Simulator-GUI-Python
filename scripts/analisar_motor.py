#!/usr/bin/env python
"""Análise de resultados de varredura do motor sobre `polars.DataFrame`.

Lê o CSV gerado por `varredura_motor.py` e oferece filtros, ranking, ponto ótimo
sob `LIMITES_PADRAO` (ou limites customizados) e plots 1D/2D.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib
import polars as pl

from src.caminhos import SAIDA
from src.especificacoes import LIMITES_PADRAO, LimitesSeguranca

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


def carregar_varredura(caminho: Path | str | None = None) -> pl.DataFrame:
    """Lê o CSV de varredura diretamente como `polars.DataFrame`."""
    path = Path(caminho) if caminho else _ultimo_csv()
    df = pl.read_csv(path, null_values=["", "nan", "NaN"])
    print(f"Carregado: {path.name}  ({df.height} registros)")
    return df


def params_do_registro(df: pl.DataFrame) -> list[str]:
    """Nomes das colunas que são parâmetros (não fixas)."""
    return [c for c in df.columns if c not in COLUNAS_FIXAS]


# ============================================================
#  Filtros e ranking
# ============================================================
def filtrar(
    df: pl.DataFrame,
    *,
    ok_geral: bool | None = True,
    fs_min: float | None = None,
    p0_max: float | None = None,
    kn_max: float | None = None,
    mass_flux_max: float | None = None,
    success: bool | None = True,
) -> pl.DataFrame:
    """Filtro cumulativo sobre o DataFrame. Cada kwarg é opcional."""
    conds: list[pl.Expr] = []
    if success is not None and "success" in df.columns:
        conds.append(pl.col("success") == success)
    if ok_geral is not None and "ok_geral" in df.columns:
        conds.append(pl.col("ok_geral") == ok_geral)

    limites_numericos = [
        ("fs_carcaca", fs_min, ">="),
        ("p0_MPa", p0_max, "<="),
        ("kn", kn_max, "<="),
        ("mass_flux", mass_flux_max, "<="),
    ]
    for col, val, op in limites_numericos:
        if val is not None and col in df.columns:
            expr = pl.col(col) >= val if op == ">=" else pl.col(col) <= val
            conds.append(pl.col(col).is_not_null() & expr)

    return df.filter(conds) if conds else df


def rankear(
    df: pl.DataFrame,
    objetivo: str = "impulse_Ns",
    ascendente: bool = False,
) -> pl.DataFrame:
    """Ordena por objetivo (default: impulso decrescente)."""
    if df.is_empty():
        return df
    if objetivo not in df.columns:
        raise KeyError(f"Objetivo '{objetivo}' não existe. Disponíveis: {df.columns}")
    return df.sort(objetivo, descending=not ascendente, nulls_last=True)


def achar_otimo(
    df: pl.DataFrame,
    objetivo: str = "impulse_Ns",
    *,
    ascendente: bool = False,
    **filtros: Any,
) -> dict[str, Any] | None:
    """Filtra + ranqueia + devolve a melhor linha como dict, ou None."""
    viaveis = filtrar(df, **filtros)
    if viaveis.is_empty():
        return None
    return rankear(viaveis, objetivo, ascendente).row(0, named=True)


# ============================================================
#  Resumo
# ============================================================
def resumo(
    df: pl.DataFrame,
    *,
    limites: LimitesSeguranca = LIMITES_PADRAO,
) -> None:
    """Estatísticas gerais da varredura usando os tetos de `limites`."""
    total = df.height
    if total == 0:
        print("(sem registros)")
        return

    ok = int(df["ok_geral"].sum()) if "ok_geral" in df.columns else 0
    sucesso = int(df["success"].sum()) if "success" in df.columns else 0

    print()
    print("=" * 70)
    print(f"  RESUMO DA VARREDURA  ({total} registros)")
    print("=" * 70)
    print(f"  Simulações bem-sucedidas: {sucesso}/{total}")
    print(f"  Passaram TODOS os checks: {ok}/{total}")

    params = params_do_registro(df)
    if params:
        print()
        print("  Parâmetros varridos:")
        for p in params:
            serie = df[p].drop_nulls()
            if serie.dtype.is_numeric() and not serie.is_empty():
                n_unicos = serie.n_unique()
                print(f"    {p}: {n_unicos} valores  ({serie.min():.4f} … {serie.max():.4f})")

    if ok < total:
        print()
        print("  Checks que falharam:")
        regras = [
            (f"FS carcaça < {limites.fs_min_carcaca:g}", pl.col("fs_carcaca") < limites.fs_min_carcaca),
            (f"P0 > {limites.p0_max / 1e6:g} MPa", pl.col("p0_MPa") > (limites.p0_max / 1e6)),
            (f"Kn > {limites.kn_max:g}", pl.col("kn") > limites.kn_max),
            (f"mass_flux > {limites.mass_flux_max:g}", pl.col("mass_flux") > limites.mass_flux_max),
        ]
        falhas: list[tuple[str, int]] = []
        reprovados = df.filter(~pl.col("ok_geral"))
        for rotulo, expr in regras:
            col_nome = expr.meta.root_names()[0]
            if col_nome in reprovados.columns:
                n = reprovados.filter(pl.col(col_nome).is_not_null() & expr).height
                if n > 0:
                    falhas.append((rotulo, n))
        if "erro" in reprovados.columns:
            n_err = reprovados.filter(pl.col("erro").is_not_null() & (pl.col("erro") != "")).height
            if n_err > 0:
                falhas.append(("erro na simulação", n_err))

        for rotulo, contagem in sorted(falhas, key=lambda x: -x[1]):
            print(f"    {rotulo:<24} {contagem:>4}×")


# ============================================================
#  Plots
# ============================================================
def _finalizar_plot(salvar_em: Path | str | None) -> None:
    import matplotlib.pyplot as plt

    if salvar_em:
        plt.savefig(salvar_em, dpi=100, bbox_inches="tight")
        print(f"Plot salvo: {salvar_em}")
    else:
        plt.show()


def plotar_1d(
    df: pl.DataFrame,
    x_param: str,
    y_param: str = "impulse_Ns",
    *,
    filtrar_viaveis: bool = True,
    salvar_em: Path | str | None = None,
):
    """Plota curva 1D. Requer apenas 1 parâmetro na varredura."""
    import matplotlib.pyplot as plt

    sub = filtrar(df, ok_geral=None, success=True) if filtrar_viaveis else df
    sub = sub.filter(pl.col(x_param).is_not_null() & pl.col(y_param).is_not_null()).sort(x_param)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(sub[x_param].to_list(), sub[y_param].to_list(), color="gray", alpha=0.5, zorder=1)

    ok_df = sub.filter(pl.col("ok_geral"))
    bad_df = sub.filter(~pl.col("ok_geral"))
    ax.scatter(ok_df[x_param].to_list(), ok_df[y_param].to_list(), color="green", s=80, zorder=2, label="OK")
    ax.scatter(bad_df[x_param].to_list(), bad_df[y_param].to_list(), color="red", s=80, zorder=2, label="alerta")

    ax.set_xlabel(x_param)
    ax.set_ylabel(y_param)
    ax.set_title(f"{y_param} vs {x_param}")
    ax.grid(alpha=0.3)
    ax.legend()

    _finalizar_plot(salvar_em)
    return fig, ax


def plotar_2d(
    df: pl.DataFrame,
    x_param: str,
    y_param: str,
    z_param: str = "impulse_Ns",
    *,
    filtrar_viaveis: bool = True,
    salvar_em: Path | str | None = None,
):
    """Mapa de calor 2D. Requer 2 parâmetros na varredura."""
    import matplotlib.pyplot as plt

    sub = filtrar(df, ok_geral=None, success=True) if filtrar_viaveis else df
    sub = sub.filter(
        pl.col(x_param).is_not_null() & pl.col(y_param).is_not_null() & pl.col(z_param).is_not_null()
    )

    nx = sub[x_param].n_unique()
    ny = sub[y_param].n_unique()
    if nx < 2 or ny < 2:
        raise ValueError(
            f"plotar_2d precisa de varredura 2D. "
            f"'{x_param}' tem {nx} valor(es) único(s), '{y_param}' tem {ny}. "
            f"Rode uma varredura com 2 parâmetros."
        )

    fig, ax = plt.subplots(figsize=(9, 7))
    tcf = ax.tricontourf(
        sub[x_param].to_numpy(),
        sub[y_param].to_numpy(),
        sub[z_param].to_numpy(),
        levels=15,
        cmap="viridis",
    )
    fig.colorbar(tcf, ax=ax, label=z_param)

    bad_df = sub.filter(~pl.col("ok_geral"))
    if not bad_df.is_empty():
        ax.plot(bad_df[x_param].to_list(), bad_df[y_param].to_list(), "x", color="red", markersize=8)

    ax.set_xlabel(x_param)
    ax.set_ylabel(y_param)
    ax.set_title(f"{z_param}  (✗ = alerta)")

    _finalizar_plot(salvar_em)
    return fig, ax


# ============================================================
#  Impressão de top-N
# ============================================================
def imprimir_top(
    df: pl.DataFrame,
    objetivo: str = "impulse_Ns",
    n: int = 10,
) -> None:
    if df.is_empty():
        print("(sem registros)")
        return

    params = params_do_registro(df)
    print()
    print("=" * 70)
    print(f"  TOP {n}  (objetivo: {objetivo})")
    print("=" * 70)

    cab = "  #  " + "  ".join(f"{p.split('.')[-1]:>9}" for p in params)
    cab += f"  {objetivo:>10}  {'P0(MPa)':>8}  {'Kn':>6}  {'mflux':>7}  {'FS':>6}"
    print(cab)
    print("  " + "-" * (len(cab) - 2))

    for i, r in enumerate(rankear(df, objetivo).head(n).iter_rows(named=True), 1):
        linha = f"  {i:>2} "
        for p in params:
            v = r.get(p)
            linha += f"  {v:>9.4f}" if isinstance(v, (int, float)) else f"  {v!s:>9}"
        linha += (
            f"  {(r.get(objetivo) or float('nan')):>10.2f}  "
            f"{(r.get('p0_MPa') or float('nan')):>8.3f}  "
            f"{(r.get('kn') or float('nan')):>6.1f}  "
            f"{(r.get('mass_flux') or float('nan')):>7.1f}  "
            f"{(r.get('fs_carcaca') or float('nan')):>6.3f}"
        )
        print(linha)


# ============================================================
#  CLI
# ============================================================
def main() -> None:
    p = argparse.ArgumentParser(description="Analisa CSV de varredura de motor")
    p.add_argument("--csv", type=Path, default=None, help="CSV específico (default: mais recente)")
    p.add_argument("--fs-min", type=float, default=None, help="Filtro FS mínimo")
    p.add_argument("--objetivo", default="impulse_Ns", help="Coluna para maximizar (default: impulse_Ns)")
    p.add_argument("--top", type=int, default=10, help="Quantos mostrar no top (default: 10)")

    args = p.parse_args()

    df = carregar_varredura(args.csv)
    resumo(df)

    viaveis = filtrar(df, fs_min=args.fs_min)
    imprimir_top(viaveis, objetivo=args.objetivo, n=args.top)

    otimo = achar_otimo(df, objetivo=args.objetivo, fs_min=args.fs_min)
    if otimo:
        print()
        print("=" * 70)
        print(f"  ÓTIMO VIÁVEL  ({args.objetivo})")
        print("=" * 70)
        for p_name in params_do_registro(df):
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
