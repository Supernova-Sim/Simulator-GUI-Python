# Hefesto — Simulação do foguete IREC

Simulação de voo do foguete Hefesto para a IREC 2027. Combina:
- **OpenMotor** (balística interna do motor via `.ric`)
- **RocketPy** (dinâmica de voo com atmosfera ERA5)
- **RASAero** (arrasto aerodinâmico, via Windows/VM)

## Estrutura

```
src/                         ← ABSTRAÇÕES (lógica pura, sem valores concretos)
├── paths.py                     caminhos canônicos do projeto
├── ambiente.py                  construtor genérico de Environment
├── modelo.py                    agrega specs + derivados num foguete resolvido
├── modelos.py                   monta o Rocket/SolidMotor do RocketPy
├── dump.py                      imprime toda a configuração formatada
├── calculos/
│   ├── motor.py                 .ric → MotorDerivado (+ FS)
│   ├── motorlib_wrapper.py      wrapper do OpenMotor headless
│   ├── seguranca.py             fs_carcaca, check_p0/kn/mass_flux
│   ├── componentes.py           TuboSpec/MassaPontualSpec → derivado
│   ├── aletas.py                AletaSpec → derivado
│   └── coifa.py                 CoifaSpec → derivado
└── parsers/
    ├── openmotor.py             .ric → RicMotorSpec → MotorSpec
    └── openrocket.py            .ork → specs (a implementar)

configs/                     ← ABSTRAÇÕES (formas) + RECURSOS + INSTÂNCIA
├── __init__.py                  FACADE — todo mundo importa daqui
├── especificacao.py             AletaSpec, CoifaSpec
├── componentes.py               TuboSpec, MassaPontualSpec
├── material.py                  σ_lim, densidades
├── limites.py                   FS_MIN, P0_MAX, Kn_MAX, MASS_FLUX_MAX
├── motor/spec.py                MotorSpec, GrainSpec
└── foguetes/hefesto/            INSTÂNCIA — valores concretos do Hefesto
    ├── corpo.py                 COMPONENTES (lista)
    ├── geometria.py             FOGUETE, ALETAS, COIFA, RAIL_BUTTONS
    ├── recuperacao.py           REEFED, UNREEFED
    ├── aletas.py                ALETA_IREC, ALETAS_TRAPEZIO_EQUIV
    ├── coifa.py                 COIFA_IREC
    ├── motor.py                 MOTOR_IREC
    ├── voo.py                   IREC, IREC_E, IREC_ENSEMBLE_E
    └── estocastico.py           todos os *_E (Monte Carlo)

centralControle/             ← PAINEL OPERACIONAL
├── rodar.py                     CLI: sim | motor | fs | varrer | dump
├── README.md                    manual de uso (leia antes de mexer)
├── parametros.yaml              parâmetros de execução
└── checklists.md                checklists de projeto e submissão

data/
├── entrada/
│   ├── motores/*.eng            curvas RASP de referência
│   ├── openmotor/*.ric          geometria do motor (OpenMotor)
│   ├── openrocket/*.ork         geometria do foguete (OpenRocket)
│   ├── arrasto/*.csv            coeficientes de arrasto
│   └── atmosfera/*.nc           ERA5 (reanálise + ensemble)
└── saida/                       JSONs de simulações, CSVs de varredura

vendor/openMotor/            ← OpenMotor clonado (gitignorado)
scripts/                     ← scripts específicos (não é API)
debug.py                     ← runner rápido na IDE (seu playground)
```

## Fluxo de uma simulação

```
data/entrada/openmotor/MotorNovo.ric
        │
        │  (src.parsers.openmotor + motorlib)
        ▼
curva_empuxo + P0_pico + Kn + mass_flux + FS
        │
        │  (src.calculos.motor.derivar_motor)
        ▼
MotorDerivado ──────────► diagnostico de segurança
        │
        │  (src.modelos.build_rocket)
        ▼
RocketPy.Rocket + SolidMotor
        │
        │  (RocketPy.Flight + Environment ERA5)
        ▼
apogeu, estabilidade, dispersão
```

## Como rodar

### Na IDE (rápido)

Abra `debug.py`, ajuste os parâmetros no topo e dê Run. Ideal para exploração.

### Pelo centralControle

```bash
python centralControle/rodar.py sim      # determinística
python centralControle/rodar.py motor    # só o motor (sem voo)
python centralControle/rodar.py fs       # diagnósticos de segurança
python centralControle/rodar.py dump     # imprime toda a configuração
python centralControle/rodar.py varrer   # varredura paramétrica
```

### Smoke test (verifica se tudo importa e valores batem)

```bash
python centralControle/rodar.py smoke
```

## Como adicionar um novo foguete

1. Crie `configs/foguetes/<nome>/` copiando o conteúdo de `hefesto/`.
2. Ajuste `geometria.py`, `corpo.py`, `aletas.py`, `coifa.py`, `motor.py`.
3. Atualize `configs/__init__.py` para expor as novas instâncias:
   ```python
   from configs.foguetes.<nome> import *   # noqa
   ```
4. Se quiser usar em simulações, passe explicitamente:
   ```python
   from configs.foguetes.novo import MOTOR_NOVO, ALETA_NOVA
   build_rocket(motor_spec=MOTOR_NOVO, spec_aleta=ALETA_NOVA, tipo_aletas="freeform")
   ```

## Como adicionar um novo motor

1. Crie o `.ric` no OpenMotor GUI, salve em `data/entrada/openmotor/`.
2. Crie `configs/foguetes/<nome>/motor.py`:
   ```python
   from src.parsers.openmotor import motor_spec_do_ric
   from src.paths import OPENMOTOR, MOTORES

   MOTOR_NOVO = motor_spec_do_ric(
       OPENMOTOR / "MotorNovo.ric",
       nome="Nome do Motor",
       case_inner_radius=...,
       case_wall_thickness=...,
       case_density=2700,
       grain_separation=...,
       nozzle_position=...,
       case_length=...,
       dry_mass=...,
   )
   ```
3. Rode `python centralControle/rodar.py fs` para ver os diagnósticos.

## Limitações conhecidas

| Item | Estado |
|---|---|
| Monte Carlo | Reformulação pendente (usa OOP do RocketPy antigo) |
| Parser `.ork` | Não implementado |
| Arrasto RASAero | Manual (Windows/VM), `.csv` versionado |
| Análise de sensibilidade (Sobol/Morris) | Não implementada |

## Referências

- Relatório do motor Medusa (`docs/Relatório de Modificações do Medusa.pdf`)
- OpenMotor: https://github.com/reilleya/openMotor
- RocketPy: https://docs.rocketpy.org