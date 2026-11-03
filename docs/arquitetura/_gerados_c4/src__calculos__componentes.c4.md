# ⚡ C4 Nível 4 (Código) — `src/calculos/componentes.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`componentes.py`](../../../src/calculos/componentes.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `componentes.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Deriva massa e inércia dos componentes estruturais a partir de suas Specs.

Cada `TuboSpec` ou `MassaPontualSpec` é traduzida num `ComponenteDerivado`
com massa, posição axial e inércias locais (longitudinal/roll e transversal).

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 src/calculos/componentes.py"]
    INT_0["🧩 src.specs\n(MassaPontualSpec, TuboSpec)"] --> MOD
    click INT_0 href "src__specs.c4.md" "Abrir C4 de src.specs"
    EXT_0["📚 collections ( lib externa )"] -.-> MOD
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 src.specs` | `MassaPontualSpec`, `TuboSpec` | [⚡ `src__specs.c4.md`](src__specs.c4.md) |

---

## 3. Impacto Sistêmico e Fluxo de Execução

### Análise de Impacto Sistêmico (`a2m impact`)

> [!IMPORTANT]
> **Mapeamento de Efeito Cascata ao Modificar `derivar_tubo()`:**
> - **Risco de Quebra Ascendente (Vermelho):** Funções e módulos externos que chamam esta lógica.
> - **Impacto Descendente (Azul):** Rotinas internas e dependências consumidas.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
graph TD
    classDef target fill:#ffe6cc,stroke:#d79b00,stroke-width:3px,color:#000
    classDef upward fill:#f8cecc,stroke:#b85450,stroke-width:2px,color:#000
    classDef downward fill:#dae8fc,stroke:#6c8ebf,stroke-width:1px,color:#000

    ALVO(("⭐ derivar_tubo (ALVO)")):::target

    subgraph Ascendente["🚨 Risco de Quebra Ascendente (Quem consome esta função)"]
        code_calculos_componentes_py__function__derivar_Hc1b956ae["⚠️ derivar"]:::upward
        code_agregador_estrutural_py__function__resolver_Hc6e34b79["⚠️ resolver"]:::upward
        code_calculos_componentes_py__function__derivar_todos_He22d6f33["⚠️ derivar_todos"]:::upward
    end
    code_agregador_estrutural_py__function__resolver_Hc6e34b79 --> code_calculos_componentes_py__function__derivar_todos_He22d6f33
    code_calculos_componentes_py__function__derivar_Hc1b956ae --> ALVO
    code_calculos_componentes_py__function__derivar_todos_He22d6f33 --> code_calculos_componentes_py__function__derivar_Hc1b956ae
    subgraph Descendente["🧩 Impacto Descendente (Dependências consumidas)"]
        code_calculos_componentes_py__struct__ComponenteDerivado_Hef12fa7b["ComponenteDerivado"]:::downward
    end
    ALVO --> code_calculos_componentes_py__struct__ComponenteDerivado_Hef12fa7b
    click code_agregador_estrutural_py__function__resolver_Hc6e34b79 href "src__agregador_estrutural.c4.md" "Abrir C4 (resolver)"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Atalhos Rápidos de Navegação (Impacto Sistêmico)

| Relação | Símbolo / Função | Arquivo C4 Destino |
| :--- | :--- | :--- |
| 🚨 Risco Ascendente (Caller) | `resolver` | [⚡ `src__agregador_estrutural.c4.md`](src__agregador_estrutural.c4.md) |

### Diagrama de Sequência de Execução — `derivar_tubo()` (`sequenceDiagram`)

> [!NOTE]
> Mostra o fluxo sequencial real de controle de execução da função,
> incluindo condicionais (`alt ... else`) e laços (`loop`).

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'signalColor': '#38bdf8', 'signalTextColor': '#f8fafc', 'actorBkg': '#1e293b', 'actorBorder': '#38bdf8', 'actorTextColor': '#f8fafc' }}}%%
sequenceDiagram
    autonumber
    %% def derivar_tubo(spec: TuboSpec) -> ComponenteDerivado
    participant self as self
    self->>self: ComponenteDerivado
```

---

## 4. Estrutura de Classes e Contratos (`classDiagram`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
classDiagram
    class ComponenteDerivado {
        <<dataclass>>
        +nome : str
        +massa : float
        +posicao : float
        +I_xx_local : float
        +I_yy_local : float
    }
```

---

## 5. Fluxo Lógico de Funções Locais (`flowchart TD`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    F_0["🟢 derivar_tubo()"]
    F_1["🟢 derivar_massa_pontual()"]
    F_2["🟢 derivar()"]
    F_3["🟢 derivar_todos()"]
    CLS_ComponenteDerivado(["📦 ComponenteDerivado"])
    F_0 -. instancia .-> CLS_ComponenteDerivado
    F_1 -. instancia .-> CLS_ComponenteDerivado
    F_2 --> F_0
    F_2 --> F_1
    F_3 --> F_2
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 6. Catálogo de Símbolos (Links Diretos para o Código)

### Classes / Contratos

| Classe | Linhas | Tipo | Resumo |
| :--- | :--- | :--- | :--- |
| [`ComponenteDerivado`](../../../src/calculos/componentes.py#L17-L22) | `L17–L22` | `@dataclass` | — |

### Funções do Módulo

| Função | Linhas | Retorno | Resumo |
| :--- | :--- | :--- | :--- |
| [`derivar_tubo`](../../../src/calculos/componentes.py#L25-L41) | `L25–L41` | `ComponenteDerivado` | Cilindro oco. Fórmulas padrão para casca cilíndrica. |
| [`derivar_massa_pontual`](../../../src/calculos/componentes.py#L44-L59) | `L44–L59` | `ComponenteDerivado` | Massa fixa com geometria cilíndrica equivalente para inércia local. |
| [`derivar`](../../../src/calculos/componentes.py#L62-L67) | `L62–L67` | `ComponenteDerivado` | — |
| [`derivar_todos`](../../../src/calculos/componentes.py#L70-L73) | `L70–L73` | `list[ComponenteDerivado]` | — |
