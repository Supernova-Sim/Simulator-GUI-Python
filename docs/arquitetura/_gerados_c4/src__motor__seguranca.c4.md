# ⚡ C4 Nível 4 (Código) — `src/motor/seguranca.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`seguranca.py`](../../../src/motor/seguranca.py).

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
    MOD["📄 src/motor/seguranca.py"]
    INT_0["🧩 src.especificacoes\n(LIMITES_PADRAO, LimitesSeguranca)"] --> MOD
    click INT_0 href "src__especificacoes.c4.md" "Abrir C4 de src.especificacoes"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 src.especificacoes` | `LIMITES_PADRAO`, `LimitesSeguranca` | [⚡ `src__especificacoes.c4.md`](src__especificacoes.c4.md) |

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
        code_relatorios_py__function__relatorio_seguranca_H11f57f78["⚠️ relatorio_seguranca"]:::upward
        code_motor_derivador_py__function___diagnosticar_H516ee10e["⚠️ _diagnosticar"]:::upward
        code_relatorios_py__function__relatorio_motor_H6c9acec8["⚠️ relatorio_motor"]:::upward
        code_relatorios_py__function__relatorio_motor_variacoes_H0b79fa33["⚠️ relatorio_motor_variacoes"]:::upward
        code_motor_derivador_py__function__derivar_motor_H5b17db9e["⚠️ derivar_motor"]:::upward
        code_simulacao_construtor_foguete_py__function__build_motor_Hbe678e56["⚠️ build_motor"]:::upward
    end
    code_motor_derivador_py__function___diagnosticar_H516ee10e --> ALVO
    code_motor_derivador_py__function__derivar_motor_H5b17db9e --> code_motor_derivador_py__function___diagnosticar_H516ee10e
    code_relatorios_py__function__relatorio_motor_H6c9acec8 --> code_motor_derivador_py__function__derivar_motor_H5b17db9e
    code_relatorios_py__function__relatorio_motor_variacoes_H0b79fa33 --> code_motor_derivador_py__function__derivar_motor_H5b17db9e
    code_relatorios_py__function__relatorio_seguranca_H11f57f78 --> code_motor_derivador_py__function__derivar_motor_H5b17db9e
    code_simulacao_construtor_foguete_py__function__build_motor_Hbe678e56 --> code_motor_derivador_py__function__derivar_motor_H5b17db9e
    subgraph Descendente["🧩 Impacto Descendente (Dependências consumidas)"]
        code_motor_seguranca_py__struct__DiagnosticoFS_H08a335bb["DiagnosticoFS"]:::downward
        extern_math__isfinite_H0279690a["isfinite"]:::downward
    end
    ALVO --> code_motor_seguranca_py__struct__DiagnosticoFS_H08a335bb
    ALVO --> extern_math__isfinite_H0279690a
    click code_motor_derivador_py__function___diagnosticar_H516ee10e href "src__motor__derivador.c4.md" "Abrir C4 (_diagnosticar)"
    click code_motor_derivador_py__function__derivar_motor_H5b17db9e href "src__motor__derivador.c4.md" "Abrir C4 (derivar_motor)"
    click code_relatorios_py__function__relatorio_motor_H6c9acec8 href "src__relatorios.c4.md" "Abrir C4 (relatorio_motor)"
    click code_relatorios_py__function__relatorio_motor_variacoes_H0b79fa33 href "src__relatorios.c4.md" "Abrir C4 (relatorio_motor_variacoes)"
    click code_relatorios_py__function__relatorio_seguranca_H11f57f78 href "src__relatorios.c4.md" "Abrir C4 (relatorio_seguranca)"
    click code_simulacao_construtor_foguete_py__function__build_motor_Hbe678e56 href "src__simulacao__construtor_foguete.c4.md" "Abrir C4 (build_motor)"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Atalhos Rápidos de Navegação (Impacto Sistêmico)

| Relação | Símbolo / Função | Arquivo C4 Destino |
| :--- | :--- | :--- |
| 🚨 Risco Ascendente (Caller) | `_diagnosticar` | [⚡ `src__motor__derivador.c4.md`](src__motor__derivador.c4.md) |
| 🚨 Risco Ascendente (Caller) | `derivar_motor` | [⚡ `src__motor__derivador.c4.md`](src__motor__derivador.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_motor` | [⚡ `src__relatorios.c4.md`](src__relatorios.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_motor_variacoes` | [⚡ `src__relatorios.c4.md`](src__relatorios.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_seguranca` | [⚡ `src__relatorios.c4.md`](src__relatorios.c4.md) |
| 🚨 Risco Ascendente (Caller) | `build_motor` | [⚡ `src__simulacao__construtor_foguete.c4.md`](src__simulacao__construtor_foguete.c4.md) |

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
    participant math as math
    self->>self: any
    self->>math: isfinite
    alt if any(v is None or not math.isfini...
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
    F_0["🔒 _verificar_teto()"]
    F_1["🟢 fs_carcaca()"]
    F_2["🟢 check_p0()"]
    F_3["🟢 check_kn()"]
    F_4["🟢 check_mass_flux()"]
    CLS_DiagnosticoFS(["📦 DiagnosticoFS"])
    F_0 -. instancia .-> CLS_DiagnosticoFS
    F_1 -. instancia .-> CLS_DiagnosticoFS
    F_2 --> F_0
    F_3 --> F_0
    F_4 --> F_0
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 6. Catálogo de Símbolos (Links Diretos para o Código)

### Classes / Contratos

| Classe | Linhas | Tipo | Resumo |
| :--- | :--- | :--- | :--- |
| [`DiagnosticoFS`](../../../src/motor/seguranca.py#L16-L36) | `L16–L36` | `@dataclass` | — |

### Funções do Módulo

| Função | Linhas | Retorno | Resumo |
| :--- | :--- | :--- | :--- |
| [`_verificar_teto`](../../../src/motor/seguranca.py#L39-L66) | `L39–L66` | `DiagnosticoFS` | Verifica um critério de teto (`valor <= limite_max`) em modo fail-closed. |
| [`fs_carcaca`](../../../src/motor/seguranca.py#L69-L101) | `L69–L101` | `DiagnosticoFS` | FS da carcaça cilíndrica de paredes finas (Beer & Johnston: σ_circ = P0 · r / t). |
| [`check_p0`](../../../src/motor/seguranca.py#L104-L105) | `L104–L105` | `DiagnosticoFS` | — |
| [`check_kn`](../../../src/motor/seguranca.py#L108-L109) | `L108–L109` | `DiagnosticoFS` | — |
| [`check_mass_flux`](../../../src/motor/seguranca.py#L112-L123) | `L112–L123` | `DiagnosticoFS` | — |
