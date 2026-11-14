# ⚡ C4 Nível 4 (Código) — `centralControle/rodar.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`rodar.py`](../../../centralControle/rodar.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `rodar.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

CLI unificada do projeto Hefesto.

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

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 centralControle/rodar.py"]
    INT_0["🧩 src.caminhos\n(RAIZ)"] --> MOD
    click INT_0 href "src__caminhos.c4.md" "Abrir C4 de src.caminhos"
    INT_1["🧩 src.especificacoes\n(MotorSpec)"] --> MOD
    click INT_1 href "src__especificacoes.c4.md" "Abrir C4 de src.especificacoes"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 src.caminhos` | `RAIZ` | [⚡ `src__caminhos.c4.md`](src__caminhos.c4.md) |
| `🧩 src.especificacoes` | `MotorSpec` | [⚡ `src__especificacoes.c4.md`](src__especificacoes.c4.md) |

---

## 3. Fluxo Lógico de Funções Locais (`flowchart TD`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    F_0["🔒 _resolver_motor()"]
    F_1["🟢 cmd_sim()"]
    F_2["🟢 cmd_motor()"]
    F_3["🟢 cmd_variacoes()"]
    F_4["🟢 cmd_estrutura()"]
    F_5["🟢 cmd_fs()"]
    F_6["🟢 cmd_voo()"]
    F_7["🟢 cmd_dump()"]
    F_8["🟢 cmd_varrer()"]
    F_9["🟢 cmd_smoke()"]
    F_10["🟢 cmd_varrer_motor()"]
    F_11["🟢 cmd_analisar_motor()"]
    F_12["🔒 _linkar_extensao()"]
    F_13["🟢 cmd_setup()"]
    F_14["🟢 cmd_c4()"]
    F_15["🟢 cmd_guia_c4()"]
    F_16["🟢 main()"]
    F_1 --> F_0
    F_13 --> F_12
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 4. Catálogo de Símbolos (Links Diretos para o Código)

### Funções do Módulo

| Função | Linhas | Retorno | Resumo |
| :--- | :--- | :--- | :--- |
| [`_resolver_motor`](../../../centralControle/rodar.py#L46-L60) | `L46–L60` | `MotorSpec | None` | Resolve uma string de preset de variação para um `MotorSpec`. |
| [`cmd_sim`](../../../centralControle/rodar.py#L63-L94) | `L63–L94` | `None` | Executa a simulação determinística de voo. |
| [`cmd_motor`](../../../centralControle/rodar.py#L97-L101) | `L97–L101` | `None` | — |
| [`cmd_variacoes`](../../../centralControle/rodar.py#L104-L108) | `L104–L108` | `None` | — |
| [`cmd_estrutura`](../../../centralControle/rodar.py#L111-L115) | `L111–L115` | `None` | — |
| [`cmd_fs`](../../../centralControle/rodar.py#L118-L122) | `L118–L122` | `None` | — |
| [`cmd_voo`](../../../centralControle/rodar.py#L125-L135) | `L125–L135` | `None` | — |
| [`cmd_dump`](../../../centralControle/rodar.py#L138-L167) | `L138–L167` | `None` | — |
| [`cmd_varrer`](../../../centralControle/rodar.py#L170-L173) | `L170–L173` | `None` | — |
| [`cmd_smoke`](../../../centralControle/rodar.py#L176-L181) | `L176–L181` | `None` | — |
| [`cmd_varrer_motor`](../../../centralControle/rodar.py#L184-L198) | `L184–L198` | `None` | — |
| [`cmd_analisar_motor`](../../../centralControle/rodar.py#L201-L205) | `L201–L205` | `None` | — |
| [`_linkar_extensao`](../../../centralControle/rodar.py#L208-L218) | `L208–L218` | `None` | — |
| [`cmd_setup`](../../../centralControle/rodar.py#L221-L248) | `L221–L248` | `None` | Configura e ativa as extensões visuais no Positron local. |
| [`cmd_c4`](../../../centralControle/rodar.py#L251-L262) | `L251–L262` | `None` | Gera sob demanda o documento C4 Nível 4 (Código) via AST para um arquivo `.py` ou em lote. |
| [`cmd_guia_c4`](../../../centralControle/rodar.py#L265-L283) | `L265–L283` | `None` | Exibe instruções e caminhos para visualizar a arquitetura C4. |
| [`main`](../../../centralControle/rodar.py#L286-L357) | `L286–L357` | `None` | — |
