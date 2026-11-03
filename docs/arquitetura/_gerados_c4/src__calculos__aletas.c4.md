# ⚡ C4 Nível 4 (Código) — `src/calculos/aletas.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`aletas.py`](../../../src/calculos/aletas.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `aletas.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Deriva massa, CG e inércia de uma `AletaSpec`.

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 src/calculos/aletas.py"]
    INT_0["🧩 src.specs\n(AletaSpec)"] --> MOD
    click INT_0 href "src__specs.c4.md" "Abrir C4 de src.specs"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 src.specs` | `AletaSpec` | [⚡ `src__specs.c4.md`](src__specs.c4.md) |

---

## 3. Impacto Sistêmico e Fluxo de Execução

### Análise de Impacto Sistêmico (`a2m impact`)

> [!IMPORTANT]
> **Mapeamento de Efeito Cascata ao Modificar `calcular_aleta()`:**
> - **Risco de Quebra Ascendente (Vermelho):** Funções e módulos externos que chamam esta lógica.
> - **Impacto Descendente (Azul):** Rotinas internas e dependências consumidas.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
graph TD
    classDef target fill:#ffe6cc,stroke:#d79b00,stroke-width:3px,color:#000
    classDef upward fill:#f8cecc,stroke:#b85450,stroke-width:2px,color:#000
    classDef downward fill:#dae8fc,stroke:#6c8ebf,stroke-width:1px,color:#000

    ALVO(("⭐ calcular_aleta (ALVO)")):::target

    subgraph Ascendente["🚨 Risco de Quebra Ascendente (Quem consome esta função)"]
        code_agregador_estrutural_py__function__resolver_Hc6e34b79["⚠️ resolver"]:::upward
        code_construtor_foguete_py__function__build_rocket_H1ea3317b["⚠️ build_rocket"]:::upward
        code_inspecao_py__function__relatorio_estrutura_He96a1b3e["⚠️ relatorio_estrutura"]:::upward
    end
    code_agregador_estrutural_py__function__resolver_Hc6e34b79 --> ALVO
    code_construtor_foguete_py__function__build_rocket_H1ea3317b --> code_agregador_estrutural_py__function__resolver_Hc6e34b79
    code_inspecao_py__function__relatorio_estrutura_He96a1b3e --> code_agregador_estrutural_py__function__resolver_Hc6e34b79
    subgraph Descendente["🧩 Impacto Descendente (Dependências consumidas)"]
        code_calculos_aletas_py__struct__AletaDerivada_Hb0df37dc["AletaDerivada"]:::downward
        code_calculos_aletas_py__function___poligono_propriedades_H0e935ca3["_poligono_propriedades"]:::downward
    end
    ALVO --> code_calculos_aletas_py__function___poligono_propriedades_H0e935ca3
    ALVO --> code_calculos_aletas_py__struct__AletaDerivada_Hb0df37dc
    click code_agregador_estrutural_py__function__resolver_Hc6e34b79 href "src__agregador_estrutural.c4.md" "Abrir C4 (resolver)"
    click code_construtor_foguete_py__function__build_rocket_H1ea3317b href "src__construtor_foguete.c4.md" "Abrir C4 (build_rocket)"
    click code_inspecao_py__function__relatorio_estrutura_He96a1b3e href "src__inspecao.c4.md" "Abrir C4 (relatorio_estrutura)"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Atalhos Rápidos de Navegação (Impacto Sistêmico)

| Relação | Símbolo / Função | Arquivo C4 Destino |
| :--- | :--- | :--- |
| 🚨 Risco Ascendente (Caller) | `resolver` | [⚡ `src__agregador_estrutural.c4.md`](src__agregador_estrutural.c4.md) |
| 🚨 Risco Ascendente (Caller) | `build_rocket` | [⚡ `src__construtor_foguete.c4.md`](src__construtor_foguete.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_estrutura` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |

### Diagrama de Sequência de Execução — `calcular_aleta()` (`sequenceDiagram`)

> [!NOTE]
> Mostra o fluxo sequencial real de controle de execução da função,
> incluindo condicionais (`alt ... else`) e laços (`loop`).

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'signalColor': '#38bdf8', 'signalTextColor': '#f8fafc', 'actorBkg': '#1e293b', 'actorBorder': '#38bdf8', 'actorTextColor': '#f8fafc' }}}%%
sequenceDiagram
    autonumber
    %% def calcular_aleta(spec: AletaSpec, r_rocket: float) -> AletaDerivada
    participant self as self
    alt if r_rocket &lt;= 0
        self->>self: ValueError
    end
    self->>self: _poligono_propriedades
    self->>self: AletaDerivada
```

---

## 4. Estrutura de Classes e Contratos (`classDiagram`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
classDiagram
    class AletaDerivada {
        <<dataclass>>
        +area_planform : float
        +volume_unitario : float
        +massa_unitaria : float
        +massa_total : float
        +x_cg_local : float
        +y_cg_local : float
        +X_cg_absoluto : float
        +r_cg : float
        +I_xx : float
        +I_yy_local : float
        +r_rocket : float
    }
```

---

## 5. Fluxo Lógico de Funções Locais (`flowchart TD`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    F_0["🔒 _poligono_propriedades()"]
    F_1["🟢 calcular_aleta()"]
    F_1 --> F_0
    CLS_AletaDerivada(["📦 AletaDerivada"])
    F_1 -. instancia .-> CLS_AletaDerivada
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 6. Catálogo de Símbolos (Links Diretos para o Código)

### Classes / Contratos

| Classe | Linhas | Tipo | Resumo |
| :--- | :--- | :--- | :--- |
| [`AletaDerivada`](../../../src/calculos/aletas.py#L11-L24) | `L11–L24` | `@dataclass` | — |

### Funções do Módulo

| Função | Linhas | Retorno | Resumo |
| :--- | :--- | :--- | :--- |
| [`_poligono_propriedades`](../../../src/calculos/aletas.py#L27-L45) | `L27–L45` | `tuple[float, float, float]` | Área e centroide `(x_c, y_c)` de um polígono simples (fórmula de Shoelace). |
| [`calcular_aleta`](../../../src/calculos/aletas.py#L48-L92) | `L48–L92` | `AletaDerivada` | Deriva massa, CG e inércia a partir da geometria e material. |
