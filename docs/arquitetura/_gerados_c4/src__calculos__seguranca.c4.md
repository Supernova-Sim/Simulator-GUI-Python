# ⚡ C4 Nível 4 (Código) — `src/calculos/seguranca.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`seguranca.py`](../../../src/calculos/seguranca.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Subsistema de Motor & Segurança](../c3-subsistema-motor.md) · **⚡ Nível 4: `seguranca.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Fatores de segurança e verificação de limites operacionais.

Cada função devolve um `DiagnosticoFS` imutável com valor calculado, limite,
status OK/alerta e detalhamento legível. Não importa nada de `configs/`.

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 src/calculos/seguranca.py"]
    INT_0["🧩 src.specs\n(LimitesSeguranca)"] --> MOD
    click INT_0 href "src__specs.c4.md" "Abrir C4 de src.specs"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 src.specs` | `LimitesSeguranca` | [⚡ `src__specs.c4.md`](src__specs.c4.md) |

---

## 3. Impacto Sistêmico e Fluxo de Execução

### Análise de Impacto Sistêmico (`a2m impact`)

> [!IMPORTANT]
> **Mapeamento de Efeito Cascata ao Modificar `fs_carcaca()`:**
> - **Risco de Quebra Ascendente (Vermelho):** Funções e módulos externos que chamam esta lógica.
> - **Impacto Descendente (Azul):** Rotinas internas e dependências consumidas.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
graph TD
    classDef target fill:#ffe6cc,stroke:#d79b00,stroke-width:3px,color:#000
    classDef upward fill:#f8cecc,stroke:#b85450,stroke-width:2px,color:#000
    classDef downward fill:#dae8fc,stroke:#6c8ebf,stroke-width:1px,color:#000

    ALVO(("⭐ fs_carcaca (ALVO)")):::target

    subgraph Ascendente["🚨 Risco de Quebra Ascendente (Quem consome esta função)"]
        code_construtor_foguete_py__function__build_motor_Hffc693a0["⚠️ build_motor"]:::upward
        code_inspecao_py__function__relatorio_motor_H38c86267["⚠️ relatorio_motor"]:::upward
        code_calculos_motor_py__function___diagnosticar_H34040dd9["⚠️ _diagnosticar"]:::upward
        code_inspecao_py__function__relatorio_motor_variacoes_Hd08348f2["⚠️ relatorio_motor_variacoes"]:::upward
        code_calculos_motor_py__function__derivar_motor_H72c18b31["⚠️ derivar_motor"]:::upward
        code_inspecao_py__function__relatorio_seguranca_Hb17b73cd["⚠️ relatorio_seguranca"]:::upward
    end
    code_calculos_motor_py__function___diagnosticar_H34040dd9 --> ALVO
    code_calculos_motor_py__function__derivar_motor_H72c18b31 --> code_calculos_motor_py__function___diagnosticar_H34040dd9
    code_construtor_foguete_py__function__build_motor_Hffc693a0 --> code_calculos_motor_py__function__derivar_motor_H72c18b31
    code_inspecao_py__function__relatorio_motor_H38c86267 --> code_calculos_motor_py__function__derivar_motor_H72c18b31
    code_inspecao_py__function__relatorio_motor_variacoes_Hd08348f2 --> code_calculos_motor_py__function__derivar_motor_H72c18b31
    code_inspecao_py__function__relatorio_seguranca_Hb17b73cd --> code_calculos_motor_py__function__derivar_motor_H72c18b31
    subgraph Descendente["🧩 Impacto Descendente (Dependências consumidas)"]
        extern_math__isfinite_H0279690a["isfinite"]:::downward
        code_calculos_seguranca_py__struct__DiagnosticoFS_Hf7789bea["DiagnosticoFS"]:::downward
    end
    ALVO --> code_calculos_seguranca_py__struct__DiagnosticoFS_Hf7789bea
    ALVO --> extern_math__isfinite_H0279690a
    click code_calculos_motor_py__function___diagnosticar_H34040dd9 href "src__calculos__motor.c4.md" "Abrir C4 (_diagnosticar)"
    click code_calculos_motor_py__function__derivar_motor_H72c18b31 href "src__calculos__motor.c4.md" "Abrir C4 (derivar_motor)"
    click code_construtor_foguete_py__function__build_motor_Hffc693a0 href "src__construtor_foguete.c4.md" "Abrir C4 (build_motor)"
    click code_inspecao_py__function__relatorio_motor_H38c86267 href "src__inspecao.c4.md" "Abrir C4 (relatorio_motor)"
    click code_inspecao_py__function__relatorio_motor_variacoes_Hd08348f2 href "src__inspecao.c4.md" "Abrir C4 (relatorio_motor_variacoes)"
    click code_inspecao_py__function__relatorio_seguranca_Hb17b73cd href "src__inspecao.c4.md" "Abrir C4 (relatorio_seguranca)"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Atalhos Rápidos de Navegação (Impacto Sistêmico)

| Relação | Símbolo / Função | Arquivo C4 Destino |
| :--- | :--- | :--- |
| 🚨 Risco Ascendente (Caller) | `_diagnosticar` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🚨 Risco Ascendente (Caller) | `derivar_motor` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🚨 Risco Ascendente (Caller) | `build_motor` | [⚡ `src__construtor_foguete.c4.md`](src__construtor_foguete.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_motor` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_motor_variacoes` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_seguranca` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |

### Diagrama de Sequência de Execução — `fs_carcaca()` (`sequenceDiagram`)

> [!NOTE]
> Mostra o fluxo sequencial real de controle de execução da função,
> incluindo condicionais (`alt ... else`) e laços (`loop`).

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'signalColor': '#38bdf8', 'signalTextColor': '#f8fafc', 'actorBkg': '#1e293b', 'actorBorder': '#38bdf8', 'actorTextColor': '#f8fafc' }}}%%
sequenceDiagram
    autonumber
    %% def fs_carcaca(
    participant self as self
    self->>self: isfinite
    self->>self: isfinite
    self->>self: isfinite
    self->>self: isfinite
    alt if p0_pico &lt;= 0 or case_inner_radiu...
        self->>self: DiagnosticoFS
        self->>self: float
    end
    self->>self: float
    self->>self: DiagnosticoFS
```

---

## 4. Estrutura de Classes e Contratos (`classDiagram`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
classDiagram
    class DiagnosticoFS {
        <<dataclass>>
        +nome : str
        +valor : float
        +limite_min : float?
        +limite_max : float?
        +unidade : str
        +ok : bool
        +detalhe : str
        +linha() str
    }
```

---

## 5. Fluxo Lógico de Funções Locais (`flowchart TD`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    F_0["🟢 fs_carcaca()"]
    F_1["🟢 check_p0()"]
    F_2["🟢 check_kn()"]
    F_3["🟢 check_mass_flux()"]
    CLS_DiagnosticoFS(["📦 DiagnosticoFS"])
    F_0 -. instancia .-> CLS_DiagnosticoFS
    F_1 -. instancia .-> CLS_DiagnosticoFS
    F_2 -. instancia .-> CLS_DiagnosticoFS
    F_3 -. instancia .-> CLS_DiagnosticoFS
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 6. Catálogo de Símbolos (Links Diretos para o Código)

### Classes / Contratos

| Classe | Linhas | Tipo | Resumo |
| :--- | :--- | :--- | :--- |
| [`DiagnosticoFS`](../../../src/calculos/seguranca.py#L18-L38) | `L18–L38` | `@dataclass` | — |

### Funções do Módulo

| Função | Linhas | Retorno | Resumo |
| :--- | :--- | :--- | :--- |
| [`fs_carcaca`](../../../src/calculos/seguranca.py#L41-L83) | `L41–L83` | `DiagnosticoFS` | FS da carcaça cilíndrica de paredes finas (Beer & Johnston). |
| [`check_p0`](../../../src/calculos/seguranca.py#L86-L111) | `L86–L111` | `DiagnosticoFS` | — |
| [`check_kn`](../../../src/calculos/seguranca.py#L114-L139) | `L114–L139` | `DiagnosticoFS` | — |
| [`check_mass_flux`](../../../src/calculos/seguranca.py#L142-L167) | `L142–L167` | `DiagnosticoFS` | — |
