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
from pathlib import Path

from src.specs import MotorSpec

# Garante que a raiz do repositório esteja no sys.path mesmo se executado de
# outro diretório ou a partir de outro ambiente virtual (.venv externo).
_RAIZ = str(Path(__file__).resolve().parents[1])
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

# ============================================================
#  AÇÃO PADRÃO (usada ao clicar em "Run" na IDE sem argumentos)
#  Opções: "sim", "motor", "estrutura", "fs", "dump", "varrer", "smoke"
# ============================================================
ACAO_PADRAO: str = "sim"


def _resolver_motor(motor: str | MotorSpec | None) -> MotorSpec | None:
    """Resolve uma string de preset de variação para um `MotorSpec`.

    Retorna None para 'oficial' ou None (sinalizando uso do motor padrão).
    """
    if motor is None or motor == "oficial":
        return None
    if isinstance(motor, MotorSpec):
        return motor

    from configs.foguetes.hefesto.motor_variacoes import VARIACOES

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
    """Executa a simulação determinística de voo.

    Funciona tanto como callback do argparse quanto por chamada direta no console:
        cmd_sim()
        cmd_sim("calculado")
        cmd_sim("medido")
        cmd_sim(modo="medido", motor="throat_estreito")
    """
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


def cmd_fs(args: argparse.Namespace | None = None) -> None:
    from centralControle.inspecionar import inspecionar_seguranca

    inspecionar_seguranca()


def cmd_varrer(args: argparse.Namespace | None = None) -> None:
    import scripts.varredura as v

    v.main()


def cmd_dump(args: argparse.Namespace | None = None) -> None:
    from centralControle.inspecionar import inspecionar_tudo

    inspecionar_tudo()


def cmd_motor(args: argparse.Namespace | None = None) -> None:
    from centralControle.inspecionar import inspecionar_motor

    inspecionar_motor()


def cmd_estrutura(args: argparse.Namespace | None = None) -> None:
    from centralControle.inspecionar import inspecionar_estrutura

    inspecionar_estrutura()


def cmd_smoke(args: argparse.Namespace | None = None) -> None:
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

    sys.argv = ["analisar_motor", *args.resto]
    analisar_main()


def cmd_setup(args: argparse.Namespace | None = None) -> None:
    """Configura e ativa a extensão do visualizador no Positron local."""
    import shutil
    import subprocess

    repo_root = Path(_RAIZ)
    ext_src = repo_root / ".vscode" / "extensions" / "hefesto-visualizer"
    ext_dest_dir = Path.home() / ".positron" / "extensions"
    ext_dest = ext_dest_dir / "hefesto-visualizer"

    ext_dest_dir.mkdir(parents=True, exist_ok=True)
    if ext_dest.is_symlink() or ext_dest.exists():
        if ext_dest.is_symlink() or ext_dest.is_file():
            ext_dest.unlink()
        else:
            shutil.rmtree(ext_dest)

    try:
        ext_dest.symlink_to(ext_src, target_is_directory=True)
        print(f"✓ Hefesto Visualizer linkado em: {ext_dest}")
    except OSError:
        shutil.copytree(ext_src, ext_dest)
        print(f"✓ Hefesto Visualizer copiado em: {ext_dest}")

    vsix = ext_src / "hefesto-visualizer-1.1.0.vsix"
    if vsix.exists():
        positron_bin = shutil.which("positron") or (
            "/usr/share/positron/bin/positron"
            if Path("/usr/share/positron/bin/positron").exists()
            else None
        )
        if positron_bin:
            try:
                subprocess.run(
                    [str(positron_bin), "--install-extension", str(vsix), "--force"],
                    capture_output=True,
                    check=False,
                )
            except (subprocess.SubprocessError, OSError):
                pass

    graphit_src = repo_root / ".vscode" / "extensions" / "magic5644.graph-it-live-1.21.3-universal"
    graphit_dest = ext_dest_dir / "magic5644.graph-it-live-1.21.3-universal"
    if graphit_src.exists():
        if graphit_dest.is_symlink() or graphit_dest.is_file():
            graphit_dest.unlink()
        elif graphit_dest.exists():
            shutil.rmtree(graphit_dest)
        try:
            graphit_dest.symlink_to(graphit_src, target_is_directory=True)
            print(f"✓ Graph-It-Live (Runtime V2) linkado em: {graphit_dest}")
        except OSError:
            shutil.copytree(graphit_src, graphit_dest)
            print(f"✓ Graph-It-Live copiado em: {graphit_dest}")

    print("\n🎉 Setup da IDE concluído com sucesso! (C4 e Graph-It-Live Runtime V2 ativados no Positron)")


def cmd_c4(args: argparse.Namespace) -> None:
    """Gera sob demanda o documento C4 Nível 4 (Código) via AST para um arquivo `.py` ou em lote."""
    from src.c4_gerador import gerar_arquivo_c4, gerar_todos

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
    guia_path = Path(_RAIZ) / "centralControle" / "GUIA_VISUALIZACAO.md"
    print("=" * 65)
    print("  🏛️  HEFESTO — ARQUITETURA C4 & VISUALIZAÇÃO EM MERMAID")
    print("=" * 65)
    print("1. No Positron (1 Clique):")
    print("   Abra qualquer arquivo .py e clique no ícone $(graph)")
    print("   no topo direito da aba para ver o C4 Nível 4 renderizado.")
    print("\n2. Pelo Terminal:")
    print("   python centralControle/rodar.py c4 src/calculos/motor.py")
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
    sub.add_parser(
        "setup", help="Configura a extensão visual C4 no Positron local (novo notebook)"
    ).set_defaults(func=cmd_setup)

    sub_c4 = sub.add_parser("c4", help="Gera diagramas C4 Nível 4 (Código) via AST e a2m")
    sub_c4.add_argument("arquivo", nargs="?", default=None, help="Caminho do arquivo Python (ex.: src/calculos/motor.py)")
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
