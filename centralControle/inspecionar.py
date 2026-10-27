#!/usr/bin/env python
"""Inspeção da configuração do foguete Hefesto.

Delega a formatação e os relatórios para `src.inspecao`, injetando as
especificações concretas de `configs`.

Uso pela CLI:
    python centralControle/inspecionar.py motor       # só o motor
    python centralControle/inspecionar.py variacoes   # comparativo das variações
    python centralControle/inspecionar.py estrutura   # calculado vs medido + componentes
    python centralControle/inspecionar.py seguranca   # FS e limites
    python centralControle/inspecionar.py voo         # parâmetros de voo
    python centralControle/inspecionar.py tudo        # tudo acima
"""
from __future__ import annotations

import argparse

from configs import HEFESTO, IREC, IREC_E, IREC_ENSEMBLE_E, MOTOR_IREC
from configs.foguetes.hefesto.motor_variacoes import PARAMS_LIVRES, VARIACOES
from src.ambiente import build_irec
from src.inspecao import (
    relatorio_estrutura,
    relatorio_motor,
    relatorio_motor_variacoes,
    relatorio_seguranca,
    relatorio_voo,
)


def inspecionar_motor() -> None:
    relatorio_motor(MOTOR_IREC)


def inspecionar_motor_variacoes() -> None:
    relatorio_motor_variacoes(VARIACOES, PARAMS_LIVRES)


def inspecionar_estrutura() -> None:
    relatorio_estrutura(HEFESTO)


def inspecionar_seguranca() -> None:
    relatorio_seguranca(MOTOR_IREC)


def inspecionar_voo() -> None:
    relatorio_voo(
        voo_nominal=IREC,
        voo_estocastico=IREC_E,
        ensemble_estocastico=IREC_ENSEMBLE_E,
        ambiente=build_irec(),
    )


def inspecionar_tudo() -> None:
    d = relatorio_motor(MOTOR_IREC)
    relatorio_motor_variacoes(VARIACOES, PARAMS_LIVRES)
    relatorio_estrutura(HEFESTO)
    relatorio_seguranca(MOTOR_IREC, derivado=d)
    inspecionar_voo()
    print()


FUNCOES = {
    "motor": inspecionar_motor,
    "variacoes": inspecionar_motor_variacoes,
    "estrutura": inspecionar_estrutura,
    "seguranca": inspecionar_seguranca,
    "voo": inspecionar_voo,
    "tudo": inspecionar_tudo,
}


def main() -> None:
    p = argparse.ArgumentParser(
        description="Inspeciona a configuração do foguete Hefesto"
    )
    p.add_argument(
        "alvo",
        choices=list(FUNCOES.keys()),
        nargs="?",
        default="tudo",
        help="seção a inspecionar (default: tudo)",
    )
    args = p.parse_args()
    FUNCOES[args.alvo]()


if __name__ == "__main__":
    main()
