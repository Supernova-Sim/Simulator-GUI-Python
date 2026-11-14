#!/usr/bin/env python
"""CLI unificada do projeto Hefesto.

🧩 Arquitetura C4 (Nível 3): docs/arquitetura/c3-execucao-voo.md
⚡ Arquitetura C4 (Nível 4): clique no botão de Grafo no topo direito ao lado de 'More Actions'

Pode ser executada tanto pelo terminal (passando subcomandos) quanto clicando
diretamente em "Run" na IDE/Positron (nesse caso executa `ACAO_PADRAO`).

Uso no terminal:
    python centralControle/rodar.py sim                      # simulação determinística
    python centralControle/rodar.py sim --modo medido        # simulação no modo medido
    python centralControle/rodar.py motor                    # relatório do motor
    python centralControle/rodar.py variacoes                # comparativo das variações do motor
    python centralControle/rodar.py estrutura                # relatório estrutural (calculado vs medido)
    python centralControle/rodar.py fs                       # diagnósticos de segurança
    python centralControle/rodar.py voo                      # parâmetros de lançamento e atmosfera
    python centralControle/rodar.py dump                     # relatório completo
    python centralControle/rodar.py varrer                   # varredura de voo (empuxo × arrasto)
    python centralControle/rodar.py varrer-motor -p ...      # varredura paramétrica do motor
    python centralControle/rodar.py analisar-motor           # análise da última varredura do motor
    python centralControle/rodar.py smoke                    # suíte de testes e contratos
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Garante que a raiz do repositório esteja no sys.path antes de importar `src`/`configs`.
_RAIZ = str(Path(__file__).resolve().parents[1])
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from src.caminhos import RAIZ
from src.especificacoes import MotorSpec

# ============================================================
#  AÇÃO PADRÃO (usada ao clicar em "Run" na IDE sem argumentos)
#  Opções: "sim", "motor", "variacoes", "estrutura", "fs", "voo", "dump", "varrer", "smoke"
# ============================================================
ACAO_PADRAO: str = "sim"


def _resolver_motor(motor: str | MotorSpec | None) -> MotorSpec | None:
    """Resolve uma string de preset de variação para um `MotorSpec`."""
    if motor is None or motor == "oficial":
        return None
    if isinstance(motor, MotorSpec):
        return motor

    from configs.foguetes.hefesto.motor import VARIACOES

    if motor not in VARIACOES:
        disponiveis = ", ".join(VARIACOES.keys())
        raise ValueError(
            f"Variação '{motor}' não existe. Disponíveis: {disponiveis}"
        )
    return VARIACOES[motor]


def cmd_sim(
    args: argparse.Namespace | str | None = None,
    *,
    modo: str | None = None,
    motor: str | MotorSpec | None = None,
    fator_empuxo: float | None = None,
    fator_arrasto: float | None = None,
    sem_salvar: bool = False,
) -> None:
    """Executa a simulação determinística de voo."""
    import scripts.sim_deterministica as sd

    if isinstance(args, str):
        modo = args
        args = None

    if isinstance(args, argparse.Namespace):
        modo = args.modo if modo is None else modo
        motor = args.motor if motor is None else motor
        fator_empuxo = args.fator_empuxo if fator_empuxo is None else fator_empuxo
        fator_arrasto = args.fator_arrasto if fator_arrasto is None else fator_arrasto
        sem_salvar = getattr(args, "sem_salvar", False)

    motor_spec = _resolver_motor(motor)

    sd.main(
        modo=modo,  # type: ignore[arg-type]
        motor=motor_spec,
        fator_empuxo=fator_empuxo,
        fator_arrasto=fator_arrasto,
        salvar_json=not sem_salvar,
    )


def cmd_motor(args: argparse.Namespace | None = None) -> None:
    from configs import MOTOR_IREC
    from src.relatorios import relatorio_motor

    relatorio_motor(MOTOR_IREC)


def cmd_variacoes(args: argparse.Namespace | None = None) -> None:
    from configs import PARAMS_LIVRES, VARIACOES
    from src.relatorios import relatorio_motor_variacoes

    relatorio_motor_variacoes(VARIACOES, PARAMS_LIVRES)


def cmd_estrutura(args: argparse.Namespace | None = None) -> None:
    from configs import HEFESTO
    from src.relatorios import relatorio_estrutura

    relatorio_estrutura(HEFESTO)


def cmd_fs(args: argparse.Namespace | None = None) -> None:
    from configs import MOTOR_IREC
    from src.relatorios import relatorio_seguranca

    relatorio_seguranca(MOTOR_IREC)


def cmd_voo(args: argparse.Namespace | None = None) -> None:
    from configs import IREC, IREC_E, IREC_ENSEMBLE_E
    from src.relatorios import relatorio_voo
    from src.simulacao.ambiente import build_irec

    relatorio_voo(
        voo_nominal=IREC,
        voo_estocastico=IREC_E,
        ensemble_estocastico=IREC_ENSEMBLE_E,
        ambiente=build_irec(),
    )


def cmd_dump(args: argparse.Namespace | None = None) -> None:
    from configs import (
        HEFESTO,
        IREC,
        IREC_E,
        IREC_ENSEMBLE_E,
        MOTOR_IREC,
        PARAMS_LIVRES,
        VARIACOES,
    )
    from src.relatorios import (
        relatorio_estrutura,
        relatorio_motor,
        relatorio_motor_variacoes,
        relatorio_seguranca,
        relatorio_voo,
    )
    from src.simulacao.ambiente import build_irec

    derivado = relatorio_motor(MOTOR_IREC)
    relatorio_motor_variacoes(VARIACOES, PARAMS_LIVRES)
    relatorio_estrutura(HEFESTO)
    relatorio_seguranca(MOTOR_IREC, derivado=derivado)
    relatorio_voo(
        voo_nominal=IREC,
        voo_estocastico=IREC_E,
        ensemble_estocastico=IREC_ENSEMBLE_E,
        ambiente=build_irec(),
    )
    print()


def cmd_varrer(args: argparse.Namespace | None = None) -> None:
    import scripts.varredura_voo as v

    v.main()


def cmd_smoke(args: argparse.Namespace | None = None) -> None:
    import pytest

    code = pytest.main(["-v", str(RAIZ / "tests")])
    if code != 0:
        raise SystemExit(int(code))


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

    sys.argv = ["analisar_motor", *args.resto]
    analisar_main()


def _linkar_extensao(src: Path, dest: Path, nome: str) -> None:
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.exists():
        shutil.rmtree(dest)
    try:
        dest.symlink_to(src, target_is_directory=True)
        print(f"✓ {nome} linkado em: {dest}")
    except OSError:
        shutil.copytree(src, dest)
        print(f"✓ {nome} copiado em: {dest}")


def cmd_setup(args: argparse.Namespace | None = None) -> None:
    """Configura e ativa as extensões visuais no Positron local."""
    ext_dir = RAIZ / ".vscode" / "extensions"
    ext_dest_dir = Path.home() / ".positron" / "extensions"
    ext_dest_dir.mkdir(parents=True, exist_ok=True)

    # Remove instalações antigas via .vsix que poderiam sombrear o symlink editável
    for obsoleta in ext_dest_dir.glob("hefesto.hefesto-visualizer*"):
        if obsoleta.is_symlink() or obsoleta.is_file():
            obsoleta.unlink()
        elif obsoleta.is_dir():
            shutil.rmtree(obsoleta)

    _linkar_extensao(
        ext_dir / "hefesto-visualizer",
        ext_dest_dir / "hefesto-visualizer",
        "Hefesto Visualizer",
    )

    graphit_src = ext_dir / "magic5644.graph-it-live-1.21.3-universal"
    if graphit_src.exists():
        _linkar_extensao(
            graphit_src,
            ext_dest_dir / "magic5644.graph-it-live-1.21.3-universal",
            "Graph-It-Live (Runtime V2)",
        )

    print("\n🎉 Setup da IDE concluído com sucesso! (C4 e Graph-It-Live Runtime V2 ativados no Positron)")


def cmd_c4(args: argparse.Namespace) -> None:
    """Gera sob demanda o documento C4 Nível 4 (Código) via AST para um arquivo `.py` ou em lote."""
    from centralControle.c4_gerador import gerar_arquivo_c4, gerar_todos

    if getattr(args, "todos", False) or args.arquivo in ("--todos", "todos", "all", None):
        gerados = gerar_todos()
        print(f"✓ {len(gerados)} diagramas C4 Nível 4 gerados com sucesso:")
        for g in gerados:
            print(f"  - {g.name}")
    else:
        destino = gerar_arquivo_c4(args.arquivo)
        print(f"✓ C4 Nível 4 gerado via AST em: {destino}")


def cmd_guia_c4(args: argparse.Namespace) -> None:
    """Exibe instruções e caminhos para visualizar a arquitetura C4."""
    guia_path = RAIZ / "centralControle" / "GUIA_VISUALIZACAO.md"
    print("=" * 65)
    print("  🏛️  HEFESTO — ARQUITETURA C4 & VISUALIZAÇÃO EM MERMAID")
    print("=" * 65)
    print("1. No Positron (1 Clique):")
    print("   Abra qualquer arquivo .py e clique no ícone $(graph)")
    print("   no topo direito da aba para ver o C4 Nível 4 renderizado.")
    print("\n2. Pelo Terminal:")
    print("   python centralControle/rodar.py c4 src/motor/derivador.py")
    print("   python centralControle/rodar.py c4 --todos")
    print("\n3. Documentos da Hierarquia C4:")
    print("   - C1 (Contexto):    docs/arquitetura/c1-contexto.md")
    print("   - C2 (Containers):  docs/arquitetura/c2-containers.md")
    print("   - C3 (Componentes): docs/arquitetura/c3-subsistema-motor.md")
    print("   - C4 (Código):      docs/arquitetura/_gerados_c4/")
    print(f"\n📖 Guia detalhado completo disponível em:\n   {guia_path}")
    print("=" * 65)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Central de controle do projeto Hefesto")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub_sim = sub.add_parser("sim", help="Simulação determinística de voo")
    sub_sim.add_argument(
        "--modo",
        choices=["calculado", "medido"],
        default=None,
        help="Modo estrutural do foguete (default: valor no topo de sim_deterministica.py)",
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
    sub.add_parser("variacoes", help="Comparativo das variações de motor").set_defaults(func=cmd_variacoes)
    sub.add_parser("estrutura", help="Inspeciona a estrutura (calculado vs medido)").set_defaults(
        func=cmd_estrutura
    )
    sub.add_parser("fs", help="Diagnósticos de segurança do motor").set_defaults(func=cmd_fs)
    sub.add_parser("voo", help="Parâmetros de lançamento e atmosfera").set_defaults(func=cmd_voo)
    sub.add_parser("dump", help="Imprime toda a configuração do projeto").set_defaults(func=cmd_dump)
    sub.add_parser("varrer", help="Varredura paramétrica de voo (empuxo × arrasto)").set_defaults(
        func=cmd_varrer
    )
    sub.add_parser("smoke", help="Executa a suíte de testes e validação de contratos").set_defaults(
        func=cmd_smoke
    )
    sub.add_parser(
        "setup", help="Configura as extensões visuais no Positron local"
    ).set_defaults(func=cmd_setup)

    sub_c4 = sub.add_parser("c4", help="Gera diagramas C4 Nível 4 (Código) via AST e a2m")
    sub_c4.add_argument("arquivo", nargs="?", default=None, help="Caminho do arquivo Python (ex.: src/motor/derivador.py)")
    sub_c4.add_argument("--todos", "-t", action="store_true", help="Gera todos os módulos do projeto em lote")
    sub_c4.set_defaults(func=cmd_c4)

    sub.add_parser("guia-c4", help="Exibe o guia operacional de visualização arquitetural C4").set_defaults(
        func=cmd_guia_c4
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

    raw_args = sys.argv[1:] if argv is None else argv
    if not raw_args:
        print(f"[rodar] Sem argumentos na CLI → executando ACAO_PADRAO='{ACAO_PADRAO}'")
        raw_args = [ACAO_PADRAO]

    args = p.parse_args(raw_args)
    args.func(args)


if __name__ == "__main__":
    main()
