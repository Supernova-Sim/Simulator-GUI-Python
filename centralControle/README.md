# centralControle — Painel Operacional

Este diretório concentra os comandos operacionais do dia a dia e a geração de diagramas C4 Nível 4.

## Comandos (`rodar.py`)

```bash
python centralControle/rodar.py <comando>
```

| Comando | O que faz | Quando usar |
|---|---|---|
| `smoke` | Roda a suíte `pytest` (contratos, física, arquitetura, C4) | Sempre após editar código ou configs |
| `fs` | Diagnósticos de segurança do motor ($FS$, $P_0$, $K_n$, fluxo de massa) | Antes de simular um motor novo |
| `motor` | Relatório detalhado do motor (grãos efetivos, balística, inércia) | Ajustando o `.ric` ou testando variações |
| `variacoes` | Tabela comparativa das variações de motor configuradas | Comparando presets de tubeira e núcleo |
| `estrutura` | Compara `modo="calculado"` vs `modo="medido"` e lista componentes | Conferindo massa seca, CG e inércia |
| `voo` | Exibe parâmetros nominais/estocásticos de voo e ambiente ERA5 | Conferindo elevação, inclinação e trilho |
| `dump` | Relatório completo (motor + variações + estrutura + segurança + voo) | Auditoria geral antes de reuniões/submissão |
| `sim` | Simulação determinística de voo (`--modo`, `--motor`, `--fator-empuxo`) | Avaliar apogeu e margem de estabilidade |
| `varrer` | Varredura de apogeu (`fator_empuxo × fator_arrasto`) | Sensibilidade de voo (`varredura_voo.py`) |
| `varrer-motor` | Varredura paramétrica multidimensional do `.ric` (`polars.DataFrame`) | Otimização de grãos e garganta |
| `analisar-motor` | Filtra, ranqueia e plota resultados da varredura do motor | Pós-processamento de `varrer-motor` |
| `c4` | Gera diagrama C4 Nível 4 (Código) via AST e a2m (`--todos` para lote) | Visualizar arquitetura e risco de quebra de um arquivo |
| `guia-c4` | Exibe o guia rápido de navegação arquitetural no terminal | Consulta rápida de visualização |
| `setup` | Linka extensões visuais (Hefesto C4 e Graph-It-Live) no Positron local | Configurando um novo ambiente |

## Exemplos Rápidos

```bash
# Comparar apogeu no modo calculado (por componentes) vs modo medido (bancada)
python centralControle/rodar.py sim --modo calculado --sem-salvar
python centralControle/rodar.py sim --modo medido --sem-salvar

# Simular voo com uma variação de motor de configs/foguetes/hefesto/motor.py
python centralControle/rodar.py sim --motor throat_largo --sem-salvar

# Inspecionar apenas as variações de motor ou parâmetros de voo
python centralControle/rodar.py variacoes
python centralControle/rodar.py voo
```
