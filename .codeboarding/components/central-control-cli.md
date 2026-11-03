---
component_id: 4
component_name: Central Control CLI
---

# Central Control CLI

## Component Description

Unified command-line interface and dispatch center for inspections, flight runs, and tooling.

---

## Key References:

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/centralControle/rodar.py (lines 219-288)
```
def main(argv: list[str] | None = None) -> None:
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
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/centralControle/inspecionar.py (lines 81-93)
```
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
```


## Source Files:

- `centralControle/inspecionar.py`
- `centralControle/rodar.py`

