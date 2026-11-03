# ⚡ C4 Nível 4 (Código) — `src/calculos/motorlib_wrapper.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`motorlib_wrapper.py`](../../../src/calculos/motorlib_wrapper.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Subsistema de Motor & Segurança](../c3-subsistema-motor.md) · **⚡ Nível 4: `motorlib_wrapper.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Adaptador do motorlib/uilib (OpenMotor) — leitura de .ric, extração geométrica e simulação.

Isola todas as peculiaridades do OpenMotor (proteção do backend do matplotlib,
restauração do `sys.excepthook` e silenciamento do logger do `uilib`) em uma
única costura (seam).

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 src/calculos/motorlib_wrapper.py"]
    INT_0["🧩 src.specs\n(GrainSpec)"] --> MOD
    click INT_0 href "src__specs.c4.md" "Abrir C4 de src.specs"
    EXT_0["📚 matplotlib ( lib externa )"] -.-> MOD
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 src.specs` | `GrainSpec` | [⚡ `src__specs.c4.md`](src__specs.c4.md) |

---

## 3. Impacto Sistêmico e Fluxo de Execução

### Análise de Impacto Sistêmico (`a2m impact`)

> [!IMPORTANT]
> **Mapeamento de Efeito Cascata ao Modificar `carregar_props()`:**
> - **Risco de Quebra Ascendente (Vermelho):** Funções e módulos externos que chamam esta lógica.
> - **Impacto Descendente (Azul):** Rotinas internas e dependências consumidas.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
graph TD
    classDef target fill:#ffe6cc,stroke:#d79b00,stroke-width:3px,color:#000
    classDef upward fill:#f8cecc,stroke:#b85450,stroke-width:2px,color:#000
    classDef downward fill:#dae8fc,stroke:#6c8ebf,stroke-width:1px,color:#000

    ALVO(("⭐ carregar_props (ALVO)")):::target

    subgraph Ascendente["🚨 Risco de Quebra Ascendente (Quem consome esta função)"]
        code_calculos_motorlib_wrapper_py__function__simular_ric_Hd88f2f28["⚠️ simular_ric"]:::upward
        code_construtor_foguete_py__function__build_motor_Hffc693a0["⚠️ build_motor"]:::upward
        code_inspecao_py__function__relatorio_motor_H38c86267["⚠️ relatorio_motor"]:::upward
        code_inspecao_py__function__relatorio_motor_variacoes_Hd08348f2["⚠️ relatorio_motor_variacoes"]:::upward
        code_calculos_motor_py__function__derivar_motor_H72c18b31["⚠️ derivar_motor"]:::upward
        code_calculos_motorlib_variacoes_py__function__simular_variacao_H938b2d61["⚠️ simular_variacao"]:::upward
        code_inspecao_py__function__relatorio_seguranca_Hb17b73cd["⚠️ relatorio_seguranca"]:::upward
        code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041["⚠️ _resolver_fonte_e_geometria"]:::upward
    end
    code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041 --> ALVO
    code_calculos_motor_py__function__derivar_motor_H72c18b31 --> code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041
    code_calculos_motorlib_variacoes_py__function__simular_variacao_H938b2d61 --> ALVO
    code_calculos_motorlib_wrapper_py__function__simular_ric_Hd88f2f28 --> ALVO
    code_construtor_foguete_py__function__build_motor_Hffc693a0 --> code_calculos_motor_py__function__derivar_motor_H72c18b31
    code_inspecao_py__function__relatorio_motor_H38c86267 --> code_calculos_motor_py__function__derivar_motor_H72c18b31
    code_inspecao_py__function__relatorio_motor_variacoes_Hd08348f2 --> code_calculos_motor_py__function__derivar_motor_H72c18b31
    code_inspecao_py__function__relatorio_seguranca_Hb17b73cd --> code_calculos_motor_py__function__derivar_motor_H72c18b31
    subgraph Descendente["🧩 Impacto Descendente (Dependências consumidas)"]
        extern_fileIO__loadFile_Hfe8ed6d4["loadFile"]:::downward
        extern_pathlib__Path_Hd2621e53["Path"]:::downward
    end
    ALVO --> extern_fileIO__loadFile_Hfe8ed6d4
    ALVO --> extern_pathlib__Path_Hd2621e53
    click code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041 href "src__calculos__motor.c4.md" "Abrir C4 (_resolver_fonte_e_geometria)"
    click code_calculos_motor_py__function__derivar_motor_H72c18b31 href "src__calculos__motor.c4.md" "Abrir C4 (derivar_motor)"
    click code_calculos_motorlib_variacoes_py__function__simular_variacao_H938b2d61 href "src__calculos__motorlib_variacoes.c4.md" "Abrir C4 (simular_variacao)"
    click code_construtor_foguete_py__function__build_motor_Hffc693a0 href "src__construtor_foguete.c4.md" "Abrir C4 (build_motor)"
    click code_inspecao_py__function__relatorio_motor_H38c86267 href "src__inspecao.c4.md" "Abrir C4 (relatorio_motor)"
    click code_inspecao_py__function__relatorio_motor_variacoes_Hd08348f2 href "src__inspecao.c4.md" "Abrir C4 (relatorio_motor_variacoes)"
    click code_inspecao_py__function__relatorio_seguranca_Hb17b73cd href "src__inspecao.c4.md" "Abrir C4 (relatorio_seguranca)"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Atalhos Rápidos de Navegação (Impacto Sistêmico)

| Relação | Símbolo / Função | Arquivo C4 Destino |
| :--- | :--- | :--- |
| 🚨 Risco Ascendente (Caller) | `_resolver_fonte_e_geometria` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🚨 Risco Ascendente (Caller) | `derivar_motor` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🚨 Risco Ascendente (Caller) | `simular_variacao` | [⚡ `src__calculos__motorlib_variacoes.c4.md`](src__calculos__motorlib_variacoes.c4.md) |
| 🚨 Risco Ascendente (Caller) | `build_motor` | [⚡ `src__construtor_foguete.c4.md`](src__construtor_foguete.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_motor` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_motor_variacoes` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_seguranca` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |

### Diagrama de Sequência de Execução — `carregar_props()` (`sequenceDiagram`)

> [!NOTE]
> Mostra o fluxo sequencial real de controle de execução da função,
> incluindo condicionais (`alt ... else`) e laços (`loop`).

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'signalColor': '#38bdf8', 'signalTextColor': '#f8fafc', 'actorBkg': '#1e293b', 'actorBorder': '#38bdf8', 'actorTextColor': '#f8fafc' }}}%%
sequenceDiagram
    autonumber
    %% def carregar_props(ric_path: str | Path) -> dict
    participant self as self
    participant ric_path as ric_path
    self->>self: Path
    self->>ric_path: exists
    alt if not ric_path.exists()
        self->>self: FileNotFoundError
    end
    self->>self: loadFile
    self->>self: str
```

---

## 4. Estrutura de Classes e Contratos (`classDiagram`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
classDiagram
    class MotorResultado {
        <<dataclass>>
        +success : bool
        +alerts : list
        +nome : str
        +burn_time : float
        +tempo : list~float~
        +empuxo : list~float~
        +pressao : list~float~
        +pressao_saida : list~float~
        +kn : list~float~
        +volume_loading : list~float~
        +d_throat : list~float~
        +massa_por_grao : list~list~float~~
        +mass_flow_por_grao : list~list~float~~
        +mass_flux_por_grao : list~list~float~~
        +regression_por_grao : list~list~float~~
        +web_por_grao : list~list~float~~
        +mach_por_grao : list~list~float~~
        +p0_pico : float
        +kn_pico : float
        +mass_flux_pico : float
        +empuxo_max : float
        +empuxo_medio : float
        +impulso_total : float
        +isp_entregue : float
        +massa_propelente_inicial : float
        +massa_propelente_final : float
        +n_graos : int
        +curva_empuxo() list~tuple~float, float~~
        +resumo() str
    }
```

---

## 5. Fluxo Lógico de Funções Locais (`flowchart TD`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    F_0["🔒 _safe_use()"]
    F_1["🔒 _as_1d()"]
    F_2["🔒 _as_2d()"]
    F_3["🔒 _pico_2d()"]
    F_4["🔒 _integrar_trapezio()"]
    F_5["🟢 carregar_props()"]
    F_6["🟢 extrair_geometria_props()"]
    F_7["🟢 simular_props()"]
    F_8["🟢 simular_ric()"]
    EXTCALL_0["🔗 GrainSpec()\n(src.specs)"]
    click EXTCALL_0 href "src__specs.c4.md" "Abrir C4 de src.specs"
    F_6 --> EXTCALL_0
    F_7 --> F_1
    F_7 --> F_2
    F_7 --> F_4
    CLS_MotorResultado(["📦 MotorResultado"])
    F_7 -. instancia .-> CLS_MotorResultado
    F_7 --> F_3
    F_8 --> F_5
    F_8 --> F_7
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Chamadas Externas Identificadas

| Chamada Local | Módulo de Origem | Documento C4 |
| :--- | :--- | :--- |
| `🔗 GrainSpec()` | `src.specs` | [⚡ `src__specs.c4.md`](src__specs.c4.md) |

---

## 6. Catálogo de Símbolos (Links Diretos para o Código)

### Classes / Contratos

| Classe | Linhas | Tipo | Resumo |
| :--- | :--- | :--- | :--- |
| [`MotorResultado`](../../../src/calculos/motorlib_wrapper.py#L79-L136) | `L79–L136` | `@dataclass` | Resultado da simulação balística interna do OpenMotor. |

### Funções do Módulo

| Função | Linhas | Retorno | Resumo |
| :--- | :--- | :--- | :--- |
| [`_safe_use`](../../../src/calculos/motorlib_wrapper.py#L28-L31) | `L28–L31` | `None` | — |
| [`_as_1d`](../../../src/calculos/motorlib_wrapper.py#L54-L55) | `L54–L55` | `list[float]` | — |
| [`_as_2d`](../../../src/calculos/motorlib_wrapper.py#L58-L61) | `L58–L61` | `list[list[float]]` | — |
| [`_pico_2d`](../../../src/calculos/motorlib_wrapper.py#L64-L65) | `L64–L65` | `float` | — |
| [`_integrar_trapezio`](../../../src/calculos/motorlib_wrapper.py#L68-L72) | `L68–L72` | `float` | — |
| [`carregar_props`](../../../src/calculos/motorlib_wrapper.py#L142-L147) | `L142–L147` | `dict` | Carrega o dicionário de propriedades de um arquivo .ric (já migrado pelo uilib). |
| [`extrair_geometria_props`](../../../src/calculos/motorlib_wrapper.py#L150-L195) | `L150–L195` | `tuple[tuple[GrainSpec, ...], float, float, float]` | Extrai (grains, propellant_density, throat_radius, nozzle_exit_radius) de `props`. |
| [`simular_props`](../../../src/calculos/motorlib_wrapper.py#L198-L277) | `L198–L277` | `MotorResultado` | Roda o solver do OpenMotor sobre um dicionário `props` em memória. |
| [`simular_ric`](../../../src/calculos/motorlib_wrapper.py#L280-L283) | `L280–L283` | `MotorResultado` | Carrega um arquivo .ric e executa a simulação no OpenMotor. |
