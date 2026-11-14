# ⚡ C4 Nível 4 (Código) — `src/simulacao/ambiente.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`ambiente.py`](../../../src/simulacao/ambiente.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `ambiente.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Fábricas de `Environment` do RocketPy para simulações determinísticas e ensemble.

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 src/simulacao/ambiente.py"]
    INT_0["🧩 src.caminhos\n(ATMOSFERA)"] --> MOD
    click INT_0 href "src__caminhos.c4.md" "Abrir C4 de src.caminhos"
    EXT_0["📚 rocketpy ( lib externa )"] -.-> MOD
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 src.caminhos` | `ATMOSFERA` | [⚡ `src__caminhos.c4.md`](src__caminhos.c4.md) |

---

## 3. Impacto Sistêmico e Fluxo de Execução

### Análise de Impacto Sistêmico (`a2m impact`)

> [!IMPORTANT]
> **Mapeamento de Efeito Cascata ao Modificar `build_irec()`:**
> - **Risco de Quebra Ascendente (Vermelho):** Funções e módulos externos que chamam esta lógica.
> - **Impacto Descendente (Azul):** Rotinas internas e dependências consumidas.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
graph TD
    classDef target fill:#ffe6cc,stroke:#d79b00,stroke-width:3px,color:#000
    classDef upward fill:#f8cecc,stroke:#b85450,stroke-width:2px,color:#000
    classDef downward fill:#dae8fc,stroke:#6c8ebf,stroke-width:1px,color:#000

    ALVO(("⭐ build_irec (ALVO)")):::target

    subgraph Descendente["🧩 Impacto Descendente (Dependências consumidas)"]
        extern_rocketpy__Environment_Hb6ce86bf["Environment"]:::downward
        code_simulacao_ambiente_py__function___criar_ambiente_base_Hd4409121["_criar_ambiente_base"]:::downward
    end
    code_simulacao_ambiente_py__function___criar_ambiente_base_Hd4409121 --> extern_rocketpy__Environment_Hb6ce86bf
    ALVO --> code_simulacao_ambiente_py__function___criar_ambiente_base_Hd4409121
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

### Diagrama de Sequência de Execução — `build_irec()` (`sequenceDiagram`)

> [!NOTE]
> Mostra o fluxo sequencial real de controle de execução da função,
> incluindo condicionais (`alt ... else`) e laços (`loop`).

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'signalColor': '#38bdf8', 'signalTextColor': '#f8fafc', 'actorBkg': '#1e293b', 'actorBorder': '#38bdf8', 'actorTextColor': '#f8fafc' }}}%%
sequenceDiagram
    autonumber
    %% def build_irec() -> Environment
    participant self as self
    participant env as env
    self->>self: _criar_ambiente_base
    self->>env: set_atmospheric_model
    self->>self: str
```

---

## 4. Fluxo Lógico de Funções Locais (`flowchart TD`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    F_0["🔒 _criar_ambiente_base()"]
    F_1["🟢 build_irec()"]
    F_2["🟢 build_irec_ensemble()"]
    F_1 --> F_0
    F_2 --> F_0
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 5. Catálogo de Símbolos (Links Diretos para o Código)

### Funções do Módulo

| Função | Linhas | Retorno | Resumo |
| :--- | :--- | :--- | :--- |
| [`_criar_ambiente_base`](../../../src/simulacao/ambiente.py#L23-L29) | `L23–L29` | `Environment` | — |
| [`build_irec`](../../../src/simulacao/ambiente.py#L32-L40) | `L32–L40` | `Environment` | Constrói o ambiente atmosférico nominal de Spaceport America (ERA5 Reanalysis). |
| [`build_irec_ensemble`](../../../src/simulacao/ambiente.py#L43-L51) | `L43–L51` | `Environment` | Constrói o ambiente atmosférico Ensemble de Spaceport America (Monte Carlo). |
