# ⚡ C4 Nível 4 (Código) — `src/calculos/coifa.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`coifa.py`](../../../src/calculos/coifa.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `coifa.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Deriva massa, CG e inércia de uma `CoifaSpec` por integração numérica.

A coifa é tratada como uma casca fina (t << L) de espessura constante sobre
o perfil `r(x)` do formato escolhido (`x=0` no bico, `x=L` na base).

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 src/calculos/coifa.py"]
    INT_0["🧩 src.specs\n(CoifaSpec)"] --> MOD
    click INT_0 href "src__specs.c4.md" "Abrir C4 de src.specs"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 src.specs` | `CoifaSpec` | [⚡ `src__specs.c4.md`](src__specs.c4.md) |

---

## 3. Impacto Sistêmico e Fluxo de Execução

### Análise de Impacto Sistêmico (`a2m impact`)

> [!IMPORTANT]
> **Mapeamento de Efeito Cascata ao Modificar `perfil()`:**
> - **Risco de Quebra Ascendente (Vermelho):** Funções e módulos externos que chamam esta lógica.
> - **Impacto Descendente (Azul):** Rotinas internas e dependências consumidas.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
graph TD
    classDef target fill:#ffe6cc,stroke:#d79b00,stroke-width:3px,color:#000
    classDef upward fill:#f8cecc,stroke:#b85450,stroke-width:2px,color:#000
    classDef downward fill:#dae8fc,stroke:#6c8ebf,stroke-width:1px,color:#000

    ALVO(("⭐ perfil (ALVO)")):::target

    subgraph Ascendente["🚨 Risco de Quebra Ascendente (Quem consome esta função)"]
        code_calculos_coifa_py__function___derivada_perfil_H64171571["⚠️ _derivada_perfil"]:::upward
        code_construtor_foguete_py__function__build_rocket_H1ea3317b["⚠️ build_rocket"]:::upward
        code_inspecao_py__function__relatorio_estrutura_He96a1b3e["⚠️ relatorio_estrutura"]:::upward
        code_calculos_coifa_py__function__calcular_coifa_H38e753ce["⚠️ calcular_coifa"]:::upward
        code_agregador_estrutural_py__function__resolver_Hc6e34b79["⚠️ resolver"]:::upward
    end
    code_agregador_estrutural_py__function__resolver_Hc6e34b79 --> code_calculos_coifa_py__function__calcular_coifa_H38e753ce
    code_calculos_coifa_py__function___derivada_perfil_H64171571 --> ALVO
    code_calculos_coifa_py__function__calcular_coifa_H38e753ce --> code_calculos_coifa_py__function___derivada_perfil_H64171571
    code_calculos_coifa_py__function__calcular_coifa_H38e753ce --> ALVO
    code_construtor_foguete_py__function__build_rocket_H1ea3317b --> code_agregador_estrutural_py__function__resolver_Hc6e34b79
    code_inspecao_py__function__relatorio_estrutura_He96a1b3e --> code_agregador_estrutural_py__function__resolver_Hc6e34b79
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

### Diagrama de Sequência de Execução — `perfil()` (`sequenceDiagram`)

> [!NOTE]
> Mostra o fluxo sequencial real de controle de execução da função,
> incluindo condicionais (`alt ... else`) e laços (`loop`).

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'signalColor': '#38bdf8', 'signalTextColor': '#f8fafc', 'actorBkg': '#1e293b', 'actorBorder': '#38bdf8', 'actorTextColor': '#f8fafc' }}}%%
sequenceDiagram
    autonumber
    %% def perfil(x: float, kind: str, L: float, R: float) -> float
    participant self as self
    participant _PERFIS_kind__H4a28ff1c as _PERFIS[kind]
    alt if kind not in _PERFIS
        self->>self: ValueError
        self->>self: list
    end
    self->>_PERFIS_kind__H4a28ff1c: _PERFIS[kind]
```

---

## 4. Estrutura de Classes e Contratos (`classDiagram`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
classDiagram
    class CoifaDerivada {
        <<dataclass>>
        +nome : str
        +massa : float
        +cg : float
        +I_xx_local : float
        +I_yy_local : float
    }
```

---

## 5. Fluxo Lógico de Funções Locais (`flowchart TD`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    F_0["🔒 _perfil_conico()"]
    F_1["🔒 _perfil_lvhaack()"]
    F_2["🔒 _perfil_ogive()"]
    F_3["🟢 perfil()"]
    F_4["🔒 _derivada_perfil()"]
    F_5["🟢 calcular_coifa()"]
    F_4 --> F_3
    CLS_CoifaDerivada(["📦 CoifaDerivada"])
    F_5 -. instancia .-> CLS_CoifaDerivada
    F_5 --> F_3
    F_5 --> F_4
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 6. Catálogo de Símbolos (Links Diretos para o Código)

### Classes / Contratos

| Classe | Linhas | Tipo | Resumo |
| :--- | :--- | :--- | :--- |
| [`CoifaDerivada`](../../../src/calculos/coifa.py#L55-L60) | `L55–L60` | `@dataclass` | — |

### Funções do Módulo

| Função | Linhas | Retorno | Resumo |
| :--- | :--- | :--- | :--- |
| [`_perfil_conico`](../../../src/calculos/coifa.py#L15-L16) | `L15–L16` | `float` | — |
| [`_perfil_lvhaack`](../../../src/calculos/coifa.py#L19-L25) | `L19–L25` | `float` | LV-Haack (von Kármán quando C=0). |
| [`_perfil_ogive`](../../../src/calculos/coifa.py#L28-L32) | `L28–L32` | `float` | Ogiva tangente: ρ = (R² + L²) / (2R). |
| [`perfil`](../../../src/calculos/coifa.py#L42-L45) | `L42–L45` | `float` | — |
| [`_derivada_perfil`](../../../src/calculos/coifa.py#L48-L51) | `L48–L51` | `float` | — |
| [`calcular_coifa`](../../../src/calculos/coifa.py#L63-L116) | `L63–L116` | `CoifaDerivada` | Integra massa e inércia da casca ao longo do perfil axial. |
