#!/usr/bin/env python
"""CLI unificada do projeto Hefesto.

Uso:
    python centralControle/rodar.py sim                      # simulação determinística
    python centralControle/rodar.py sim --modo medido        # simulação no modo medido
    python centralControle/rodar.py motor                    # relatório do motor
    python centralControle/rodar.py estrutura                # relatório estrutural (calculado vs medido)
    python centralControle/rodar.py fs                       # diagnósticos de segurança
    python centralControle/rodar.py dump                     # relatório completo
    python centralControle/rodar.py varrer                   # varredura de voo (empuxo × arrasto)
    python centralControle/rodar.py varrer-motor -p ...      # varredura paramétrica do motor
    python centralControle/rodar.py analisar-motor           # análise da última varredura do motor
    python centralControle/rodar.py smoke                    # suíte de testes e contratos
"""
from __future__ import annotations

import argparse
import sys


def cmd_sim(args: argparse.Namespace) -> None:
    import scripts.simDeterministica as sd

    sd.main(
        modo=args.modo,
        variacao_motor=args.motor,
        fator_empuxo=args.fator_empuxo,
        fator_arrasto=args.fator_arrasto,
        salvar_json=not args.sem_salvar,
    )


def cmd_fs(args: argparse.Namespace) -> None:
    from centralControle.inspecionar import inspecionar_seguranca

    inspecionar_seguranca()


def cmd_varrer(args: argparse.Namespace) -> None:
    import scripts.varredura as v

    v.main()


def cmd_dump(args: argparse.Namespace) -> None:
    from centralControle.inspecionar import inspecionar_tudo

    inspecionar_tudo()


def cmd_motor(args: argparse.Namespace) -> None:
    from centralControle.inspecionar import inspecionar_motor

    inspecionar_motor()


def cmd_estrutura(args: argparse.Namespace) -> None:
    from centralControle.inspecionar import inspecionar_estrutura

    inspecionar_estrutura()


def cmd_smoke(args: argparse.Namespace) -> None:
    from src.smoke import main as smoke_main

    smoke_main()


def cmd_varrer_motor(args: argparse.Namespace) -> None:
    from scripts.varredura_motor import _parse_param, imprimir_tabela, varrer_motor

    params = {}
    for p in args.params:
        nome, valores = _parse_param(p)
        params[nome] = valores

    resultados = varrer_motor(
        params,
        curvas=args.curvas,
        n_jobs=args.n_jobs,
    )
    print()
    imprimir_tabela(resultados, params)


def cmd_analisar_motor(args: argparse.Namespace) -> None:
    from scripts.analisar_motor import main as analisar_main

    sys.argv = ["analisar_motor"] + args.resto
    analisar_main()


def main() -> None:
    p = argparse.ArgumentParser(description="Central de controle do projeto Hefesto")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub_sim = sub.add_parser("sim", help="Simulação determinística de voo")
    sub_sim.add_argument(
        "--modo",
        choices=["calculado", "medido"],
        default=None,
        help="Modo estrutural do foguete (default: valor no topo de simDeterministica.py)",
    )
    sub_sim.add_argument(
        "--motor",
        default=None,
        help="Preset de variação do motor (ex.: oficial, throat_estreito, throat_largo)",
    )
    sub_sim.add_argument("--fator-empuxo", type=float, default=None)
    sub_sim.add_argument("--fator-arrasto", type=float, default=None)
    sub_sim.add_argument("--sem-salvar", action="store_true", help="Não salva JSON em data/saida/")
    sub_sim.set_defaults(func=cmd_sim)

    sub.add_parser("motor", help="Inspeciona o motor (sem voo)").set_defaults(func=cmd_motor)
    sub.add_parser("estrutura", help="Inspeciona a estrutura (calculado vs medido)").set_defaults(
        func=cmd_estrutura
    )
    sub.add_parser("fs", help="Diagnósticos de segurança do motor").set_defaults(func=cmd_fs)
    sub.add_parser("dump", help="Imprime toda a configuração do projeto").set_defaults(func=cmd_dump)
    sub.add_parser("varrer", help="Varredura paramétrica de voo (empuxo × arrasto)").set_defaults(
        func=cmd_varrer
    )
    sub.add_parser("smoke", help="Executa a suíte de testes e validação de contratos").set_defaults(
        func=cmd_smoke
    )

    sub_vm = sub.add_parser("varrer-motor", help="Varredura paramétrica do motor (.ric)")
    sub_vm.add_argument(
        "--param",
        "-p",
        action="append",
        required=True,
        dest="params",
        help="nome=valores (ex.: nozzle.throat=0.030:0.038:0.002)",
    )
    sub_vm.add_argument("--curvas", action="store_true")
    sub_vm.add_argument("--n-jobs", "-j", type=int, default=4)
    sub_vm.set_defaults(func=cmd_varrer_motor)

    sub_am = sub.add_parser("analisar-motor", help="Analisa a última varredura de motor")
    sub_am.add_argument("resto", nargs=argparse.REMAINDER)
    sub_am.set_defaults(func=cmd_analisar_motor)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
