# Relatório Técnico: Desacoplamento entre `simDeterministica` e `motor_variacoes`

**Data:** 02 de Novembro de 2026  
**Projeto:** Hefesto (Módulo de Simulações Estruturais e Voo 6-DOF)  
**Autor:** Antigravity (Gemini 3.8 Flash) com Revisão Cruzada DeepSeek V4.1 Flash (via `peer-coder` / Ponytail)  
**Status:** Concluído e Validado (24/24 testes aprovados)

---

## 1. Resumo Executivo

O objetivo desta refatoração foi **eliminar a incoerência arquitetural** detectada no visualizador de chamadas (Graph-It-Live), onde o script principal de simulação de voo determinístico nominal ([`scripts/simDeterministica.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/scripts/simDeterministica.py)) possuía uma dependência direta e concreta com presets de exploração geométrica de motor ([`configs/foguetes/hefesto/motor_variacoes.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/configs/foguetes/hefesto/motor_variacoes.py)).

A solução adotou o princípio da **Inversão de Dependência (DIP)** e **Responsabilidade Única (SRP)**:
1. O simulador de voo agora depende apenas do contrato abstrato [`MotorSpec`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/src/specs.py), aceitando injeção direta de motor via parâmetro.
2. A responsabilidade de traduzir texto/presets de CLI (ex.: `"throat_largo"`) foi transferida para a camada de despacho e orquestração de comandos ([`centralControle/rodar.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/centralControle/rodar.py)).

---

## 2. O que mudou especificamente na função `_resolver_motor`?

A função `_resolver_motor` sofreu quatro mudanças fundamentais de design, responsabilidade e localização:

### Tabela Comparativa

| Critério | Antes (em `simDeterministica.py`) | Depois (em `centralControle/rodar.py`) |
| :--- | :--- | :--- |
| **Localização** | `scripts/simDeterministica.py` (Script de Física) | `centralControle/rodar.py` (CLI / Despacho) |
| **Camada Arquitetural** | Execução Canônica de Voo | Interface de Entrada / Orquestração |
| **Assinatura de Entrada** | `variacao: str \| None` | `motor: str \| MotorSpec \| None` |
| **Retorno** | Sempre `MotorSpec` (forçava `MOTOR_IREC` se `None`) | `MotorSpec \| None` (retorna `None` se for nominal) |
| **Suporte a Objetos** | Quebrava se recebesse um objeto `MotorSpec` | Permite passar tanto a string do preset quanto a instância pronta |
| **Efeito no Grafo** | Conectava o voo a arquivos de motor experimentais | Mantém o simulador 100% puro e sem arestas indesejadas |

---

### Código Antes vs. Depois

#### 🔴 Como era em `scripts/simDeterministica.py` (Removido):
```python
def _resolver_motor(variacao: str | None) -> MotorSpec:
    """Retorna o `MotorSpec` correspondente à variação escolhida."""
    if variacao is None or variacao == "oficial":
        return MOTOR_IREC

    from configs.foguetes.hefesto.motor_variacoes import VARIACOES  # <--- Acoplava o script

    if variacao not in VARIACOES:
        disponiveis = ", ".join(VARIACOES.keys())
        raise ValueError(
            f"Variação '{variacao}' não existe. Disponíveis: {disponiveis}"
        )
    return VARIACOES[variacao]
```

#### 🟢 Como ficou em `centralControle/rodar.py` (Nova Implementação):
```python
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
```

#### Por que o retorno agora é `MotorSpec | None`?
Porque ao retornar `None` quando o usuário não especifica nada ou passa `"oficial"`, a função [`cmd_sim`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/centralControle/rodar.py#L63) repassa `sd.main(motor=None)`. Dentro do simulador, a linha:
```python
motor_spec: MotorSpec = motor if motor is not None else (MOTOR or MOTOR_IREC)
```
assume naturalmente a precedência: primeiro a constante de IDE `MOTOR` (se o usuário estiver debugando na IDE), ou caso contrário o motor oficial de voo `MOTOR_IREC`.

---

## 3. Mapeamento de Todas as Modificações nos Arquivos

### 1. [`scripts/simDeterministica.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/scripts/simDeterministica.py)
* **Remoção de acoplamento:** Excluída a constante `USAR_VARIACAO_MOTOR` e a função `_resolver_motor()`.
* **Injeção de dependência:** Assinatura de `main()` atualizada de `variacao_motor: str | None = None` para `motor: MotorSpec | None = None`.
* **Fluxo de IDE mantido:** Adicionada a constante declarativa no topo:
  ```python
  MOTOR: MotorSpec | None = None  # None → usa MOTOR_IREC oficial (ou passe um MotorSpec customizado)
  ```
* **Metadados JSON:** O campo no bloco de configuração do JSON salvo passou de `"variacao_motor": var_eff or "oficial"` para `"motor": motor_spec.nome`, tornando os relatórios de saída consistentes e determinísticos.

### 2. [`centralControle/rodar.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/centralControle/rodar.py)
* Centralizou a função `_resolver_motor` em nível de módulo.
* A função `cmd_sim()` agora aceita `motor: str | MotorSpec | None = None`, resolve o objeto via `_resolver_motor()` e o injeta diretamente em `sd.main(motor=motor_spec)`.
* O import de `VARIACOES` permaneceu estritamente *lazy* (dentro de `_resolver_motor`), evitando overhead de importação do OpenMotor ao rodar comandos leves da CLI (como `--help`).

### 3. [`tests/test_motor_e_variacoes.py`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/tests/test_motor_e_variacoes.py)
* Adicionado novo teste unitário de cobertura contratual:
  ```python
  def test_resolver_motor_cli() -> None:
      """Verifica a resolução de presets de motor pela CLI `centralControle.rodar`."""
      from centralControle.rodar import _resolver_motor

      assert _resolver_motor(None) is None
      assert _resolver_motor("oficial") is None
      assert _resolver_motor("throat_estreito") is VARIACOES["throat_estreito"]
      assert _resolver_motor(MOTOR_IREC) is MOTOR_IREC

      with pytest.raises(ValueError, match="não existe"):
          _resolver_motor("inexistente")
  ```

### 4. Documentação e Diagramas
* [`README.md`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/README.md): Instruções de uso na IDE atualizadas de `USAR_VARIACAO_MOTOR` para `MOTOR`.
* [`docs/arquitetura/c3-execucao-voo.md`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/docs/arquitetura/c3-execucao-voo.md): O subgrafo C3 de Despacho (`centralControle/rodar.py`) passou a ser o dono do nó `_resolver_motor`, enquanto o subgrafo do Orquestrador de Voo (`scripts/simDeterministica.py`) apenas consome `motor_spec`.
* Diagramas C4 Nível 4 em [`docs/arquitetura/_gerados_c4/`](file:///home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto%20privado-estrutura-vibe/docs/arquitetura/_gerados_c4/) regenerados em lote via AST.

---

## 4. Análise e Parecer Cruzado (Peer-Coder DeepSeek V4.1)

Antes de efetuar as modificações, a skill `peer-coder` foi acionada. O DeepSeek realizou uma auditoria adversária com a filosofia **Ponytail** e apontou:
1. **Risco de Contrato no JSON:** Se gravássemos `motor.nome` no campo legado `variacao_motor`, clientes externos que esperassem a string do preset sofreriam quebra semântica. A recomendação aprovada foi padronizar o nome da chave como `motor`.
2. **Prevenção de Efeitos Colaterais de Importação:** Alerta crítico para não importar `motor_variacoes` no topo de `rodar.py` para não puxar o backend gráfico do OpenMotor/matplotlib inadvertidamente.
3. **Cobertura Obrigatória de Branch:** Nenhum teste chamava o despachante com `--motor`. A criação do teste `test_resolver_motor_cli()` supriu essa lacuna.

---

## 5. Validação e Evidências

Todas as verificações passaram com êxito:

```bash
# 1. Execução de toda a suíte de testes do repositório
$ uv run pytest
============================== 24 passed in 3.08s ==============================

# 2. Execução da CLI no modo nominal padrão
$ uv run python centralControle/rodar.py sim --sem-salvar
Foguete: Hefesto (modo=calculado)
Motor: Medusa KNSB a
Apogeu AGL: 2900.9 m | Margem mínima: 1.284 cal

# 3. Execução da CLI com variação experimental injetada
$ uv run python centralControle/rodar.py sim --motor throat_largo --sem-salvar
Foguete: Hefesto (modo=calculado)
Motor: Medusa (throat +6%)
Apogeu AGL: 2848.2 m | Margem mínima: 1.284 cal

# 4. Execução canônica na IDE (simulação pura)
$ uv run python scripts/simDeterministica.py
JSON salvo em: data/saida/sim_20261102_001632.json (com chave 'motor' uniforme)
```

No **Graph-It-Live** e ferramentas de AST, a aresta entre `simDeterministica` e `motor_variacoes` foi completamente eliminada.
