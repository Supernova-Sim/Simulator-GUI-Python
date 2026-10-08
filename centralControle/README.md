# centralControle — painel operacional

Este é o lugar onde você mexe no dia a dia. Todo o resto (`src/`, `configs/`)
é biblioteca ou configuração — só edite se souber o que está fazendo.

## Comandos

Todos rodam pela CLI unificada:

```bash
python centralControle/rodar.py <comando>
```

| Comando | O que faz | Quando usar |
|---|---|---|
| `sim` | Simulação determinística completa | Antes de commitar mudanças |
| `motor` | Só o motor (sem voo) | Ajustando o `.ric` |
| `fs` | Diagnósticos de segurança | Sempre, antes de simular oficial |
| `dump` | Imprime toda a configuração formatada | "Será que está tudo certo?" |
| `varrer` | Varredura empuxo × arrasto | Análises paramétricas |
| `smoke` | Smoke test dos módulos de `src/` | Depois de refatorar |

## Fluxo típico

### Ajustar o motor

1. Abra o `.ric` no OpenMotor GUI, mude os grãos, salve.
2. `python centralControle/rodar.py fs` → checar FS, P0, Kn, mass flux.
3. `python centralControle/rodar.py sim` → ver impacto no apogeu.

### Verificar a configuração do foguete

```bash
python centralControle/rodar.py dump
```

Imprime: massa seca, CG, inércia, tabela de componentes, geometria das
aletas, massa e CG da coifa, curva do motor, FS. Útil antes de apresentação
ou para comparar com medições físicas.

### Antes de submeter para a IREC

1. `python centralControle/rodar.py fs` → todos OK?
2. `python centralControle/rodar.py sim` → apogeu na faixa alvo?
3. `centralControle/checklists.md` → todos os itens checados?

## Estrutura do `rodar.py`

```
rodar.py <comando>
    │
    ├── sim      → scripts.simDeterministica.main()
    ├── motor    → derivar_motor(MOTOR_IREC)
    ├── fs       → derivar_motor + imprimir diagnosticos
    ├── dump     → src.dump.dump_tudo()
    ├── varrer   → scripts.varredura.main()
    └── smoke    → src.smoke_test()
```

## Parâmetros de execução

`parametros.yaml` — edite aqui sem tocar em Python:

```yaml
simulacao:
  tipo_aletas: freeform
  usar_spec_aleta: true
  fator_empuxo: 1.00
  fator_arrasto: 1.00

varredura:
  empuxo: { inicio: 0.90, fim: 1.10, passo: 0.01 }
  arrasto: { inicio: 1.00, fim: 1.00, passo: 0.10 }
```

(Integração com o `rodar.py` ainda pendente — por ora os valores estão
hardcoded nos scripts.)

## Diagnósticos — como ler

```
[OK ] FS carcaça              2.9302 —            >= 2.000   σ_circ=49.48 MPa (σ_lim=145 MPa)
[OK ] P0 pico                 2.9122 MPa          <= 8.000
[OK ] Kn pico                232.7390 —            <= 250.000
[OK ] mass flux pico        1249.4661 kg/(m²·s)   <= 1406.000
```

- `[OK ]` → passou
- `[!! ]` → falhou, revisar antes de simular

Limites em `configs/limites.py`.