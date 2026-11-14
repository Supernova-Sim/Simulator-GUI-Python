# Hefesto — Simulação do foguete IREC

numero de refatoracoes da estrutura: 3

Simulação de voo do foguete Hefesto para a IREC. Combina:
- **OpenMotor** (balística interna do motor via `.ric`)
- **RocketPy** (dinâmica de voo com atmosfera ERA5)
- **RASAero** (arrasto aerodinâmico via `.csv`)

Consulte o [GLOSSARY.md](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/GLOSSARY.md) para as definições canônicas de termos, referenciais de coordenadas e convenção de momentos de inércia `(I_11, I_22, I_33) = (I_transversal, I_transversal, I_longitudinal)`.

## Arquitetura e Direção de Dependências

O projeto segue um fluxo **estritamente unidirecional**:
`centralControle/ & scripts/` → `configs/` → `src/`

- **`src/` nunca importa `configs/`**: toda função de `src/` recebe suas especificações (`Specs`) explicitamente por argumento.
- **`configs/` possui zero I/O no `import`**: declara apenas objetos imutáveis (`MotorSpec`, `FogueteSpec`, `TuboSpec`, `AletaSpec`, `CoifaSpec`); a leitura de arquivos `.ric`/`.eng` acontece apenas sob demanda dentro de `derivar_motor()`.

```
src/                         ← MOTOR DE DOMÍNIO (puro, sem importar configs/)
├── caminhos.py                  caminhos canônicos do projeto
├── especificacoes.py            contratos de entrada (Specs), limites padrão e validar_overrides()
├── relatorios.py                relatórios formatados de motor, estrutura, segurança e voo
├── estrutura/
│   ├── agregador.py             resolver() → FogueteResolvido (modo="calculado")
│   ├── componentes.py           TuboSpec / MassaPontualSpec → ComponenteDerivado
│   ├── coifa.py                 CoifaSpec → CoifaDerivada
│   └── aletas.py                AletaSpec → AletaDerivada e conversão RASAero (polegadas)
├── motor/
│   ├── derivador.py             derivar_motor(MotorSpec) → MotorDerivado (+ FS)
│   ├── seguranca.py             fs_carcaca, check_p0, check_kn, check_mass_flux
│   └── adaptador_openmotor.py   adaptador OpenMotor (.ric + overrides → ResultadoRic)
└── simulacao/
    ├── construtor_foguete.py    build_motor() e build_rocket(modo="calculado"|"medido")
    └── ambiente.py              fábricas de Environment (ERA5 Reanalysis/Ensemble)

configs/                     ← DADOS PUROS E INSTÂNCIAS (zero I/O no import)
├── __init__.py                  fachada pública (reexporta Specs + HEFESTO)
├── limites.py                   materiais (Al 6061/6063-T5, compósito, coifa) e LIMITES_IREC
└── foguetes/hefesto/            instância concreta do foguete Hefesto
    ├── __init__.py              HEFESTO (FogueteSpec completa)
    ├── corpo.py                 COMPONENTES (modo="calculado")
    ├── geometria.py             COIFA_IREC, ALETA_IREC, recuperação, rail buttons e GEOMETRIA_MEDIDA_HEFESTO
    ├── motor.py                 MOTOR_IREC, PARAMS_LIVRES, criar_variacao(), VARIACOES
    ├── voo.py                   IREC, IREC_E, IREC_ENSEMBLE_E
    └── estocastico.py           incertezas *_E para Monte Carlo

scripts/                     ← ORQUESTRAÇÃO E ANÁLISES TABULARES (Polars)
├── sim_deterministica.py        simulação determinística 6-DOF e persistência JSON
├── varredura_voo.py             varredura paramétrica de apogeu (empuxo × arrasto)
├── varredura_motor.py           varredura multidimensional sobre .ric (polars.DataFrame)
├── analisar_motor.py            filtragem, ranking, ponto ótimo e plots de varreduras
└── monte_carlo_irec.py          simulação estocástica Monte Carlo + Ensemble ERA5

centralControle/             ← PAINEL OPERACIONAL (CLI & C4)
├── rodar.py                     CLI unificada: sim | motor | variacoes | estrutura | fs | voo | dump | varrer | varrer-motor | analisar-motor | smoke | c4
├── c4_gerador.py                gerador automático de diagramas C4 Nível 4 via AST e a2m
├── README.md                    manual operacional rápido
├── checklists.md                checklists de projeto e submissão
└── GUIA_VISUALIZACAO.md         guia do Modelo C4 e Positron

tests/                       ← SUÍTE AUTOMATIZADA (pytest)
├── test_especificacoes.py       arquitetura (src ↛ configs), caminhos canônicos e contratos fail-fast
├── test_estrutura.py            componentes, coifa, aletas/RASAero e agregador (Steiner)
├── test_motor.py                motor (.ric/.eng), overrides, segurança (FS) e análise Polars
├── test_simulacao.py            build_rocket (calculado vs medido) e integração 6-DOF RocketPy
└── test_c4_gerador.py           geração de documentação C4 Nível 4 e fallback AST
```

## Como rodar

### Pela CLI (`centralControle/rodar.py`)

```bash
python centralControle/rodar.py smoke                  # roda todos os testes (pytest)
python centralControle/rodar.py fs                     # diagnósticos de segurança do motor
python centralControle/rodar.py motor                  # relatório completo do motor
python centralControle/rodar.py variacoes              # comparativo das variações do motor
python centralControle/rodar.py estrutura              # estrutura (compara calculado vs medido)
python centralControle/rodar.py voo                    # parâmetros de lançamento e atmosfera
python centralControle/rodar.py dump                   # imprime toda a configuração
python centralControle/rodar.py sim                    # simulação determinística (modo calculado)
python centralControle/rodar.py sim --modo medido      # simulação determinística (modo medido)
python centralControle/rodar.py sim --motor throat_largo
python centralControle/rodar.py varrer                 # varredura empuxo × arrasto
python centralControle/rodar.py varrer-motor -p nozzle.throat=0.032:0.036:0.002
python centralControle/rodar.py analisar-motor
python centralControle/rodar.py c4 --todos             # regenera todos os C4 Nível 4
```

### Na IDE (`debug.py` ou `scripts/sim_deterministica.py`)

Abra `debug.py` ou `scripts/sim_deterministica.py`, ajuste as constantes no topo (`MODO_FOGUETE = "calculado" | "medido"`, `MOTOR`, etc.) e execute. Presets de variação de motor também podem ser acionados diretamente via CLI (`--motor throat_largo`).
