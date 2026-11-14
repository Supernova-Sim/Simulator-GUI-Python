# ⚡ C4 Nível 4 (Código) — `src/motor/adaptador_openmotor.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`adaptador_openmotor.py`](../../../src/motor/adaptador_openmotor.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Subsistema de Motor & Segurança](../c3-subsistema-motor.md) · **⚡ Nível 4: `adaptador_openmotor.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Adaptador profundo do OpenMotor (motorlib/uilib) com suporte a overrides em memória.

Isola os efeitos colaterais de import do `uilib` (matplotlib backend,
`sys.excepthook` e logger) atrás de uma única interface `executar_ric()`.

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 src/motor/adaptador_openmotor.py"]
    INT_0["🧩 src.especificacoes\n(GrainSpec)"] --> MOD
    click INT_0 href "src__especificacoes.c4.md" "Abrir C4 de src.especificacoes"
    EXT_0["📚 matplotlib ( lib externa )"] -.-> MOD
    EXT_1["📚 numpy ( lib externa )"] -.-> MOD
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 src.especificacoes` | `GrainSpec` | [⚡ `src__especificacoes.c4.md`](src__especificacoes.c4.md) |

---

## 3. Impacto Sistêmico e Fluxo de Execução

### Análise de Impacto Sistêmico (`a2m impact`)

> [!IMPORTANT]
> **Mapeamento de Efeito Cascata ao Modificar `executar_ric()`:**
> - **Risco de Quebra Ascendente (Vermelho):** Funções e módulos externos que chamam esta lógica.
> - **Impacto Descendente (Azul):** Rotinas internas e dependências consumidas.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
graph TD
    classDef target fill:#ffe6cc,stroke:#d79b00,stroke-width:3px,color:#000
    classDef upward fill:#f8cecc,stroke:#b85450,stroke-width:2px,color:#000
    classDef downward fill:#dae8fc,stroke:#6c8ebf,stroke-width:1px,color:#000

    ALVO(("⭐ executar_ric (ALVO)")):::target

    subgraph Ascendente["🚨 Risco de Quebra Ascendente (Quem consome esta função)"]
        code_relatorios_py__function__relatorio_seguranca_H11f57f78["⚠️ relatorio_seguranca"]:::upward
        code_motor_derivador_py__function___resolver_fonte_e_geometria_H35eb7443["⚠️ _resolver_fonte_e_geometria"]:::upward
        code_relatorios_py__function__relatorio_motor_H6c9acec8["⚠️ relatorio_motor"]:::upward
        code_relatorios_py__function__relatorio_motor_variacoes_H0b79fa33["⚠️ relatorio_motor_variacoes"]:::upward
        code_motor_derivador_py__function__derivar_motor_H5b17db9e["⚠️ derivar_motor"]:::upward
        code_simulacao_construtor_foguete_py__function__build_motor_Hbe678e56["⚠️ build_motor"]:::upward
    end
    code_motor_derivador_py__function___resolver_fonte_e_geometria_H35eb7443 --> ALVO
    code_motor_derivador_py__function__derivar_motor_H5b17db9e --> code_motor_derivador_py__function___resolver_fonte_e_geometria_H35eb7443
    code_relatorios_py__function__relatorio_motor_H6c9acec8 --> code_motor_derivador_py__function__derivar_motor_H5b17db9e
    code_relatorios_py__function__relatorio_motor_variacoes_H0b79fa33 --> code_motor_derivador_py__function__derivar_motor_H5b17db9e
    code_relatorios_py__function__relatorio_seguranca_H11f57f78 --> code_motor_derivador_py__function__derivar_motor_H5b17db9e
    code_simulacao_construtor_foguete_py__function__build_motor_Hbe678e56 --> code_motor_derivador_py__function__derivar_motor_H5b17db9e
    subgraph Descendente["🧩 Impacto Descendente (Dependências consumidas)"]
        extern_pathlib__Path_Hd2621e53["Path"]:::downward
        code_motor_adaptador_openmotor_py__function___pico_canal_2d_Hb5c40048["_pico_canal_2d"]:::downward
        extern_fileIO__loadFile_Hfe8ed6d4["loadFile"]:::downward
        extern_copy__deepcopy_H618b073e["deepcopy"]:::downward
        extern_numpy__trapezoid_Hbc102c77["trapezoid"]:::downward
        code_motor_adaptador_openmotor_py__struct__ResultadoRic_H7c88ef35["ResultadoRic"]:::downward
        code_motor_adaptador_openmotor_py__function___set_path_H22396aeb["_set_path"]:::downward
        extern_especificacoes__GrainSpec_Hff300395["GrainSpec"]:::downward
        extern_motor__Motor_Hcc0c9bee["Motor"]:::downward
        code_motor_adaptador_openmotor_py__function___aplicar_overrides_H53241152["_aplicar_overrides"]:::downward
        code_motor_adaptador_openmotor_py__function___extrair_geometria_H59c6fe2d["_extrair_geometria"]:::downward
    end
    code_motor_adaptador_openmotor_py__function___aplicar_overrides_H53241152 --> code_motor_adaptador_openmotor_py__function___set_path_H22396aeb
    code_motor_adaptador_openmotor_py__function___aplicar_overrides_H53241152 --> extern_copy__deepcopy_H618b073e
    code_motor_adaptador_openmotor_py__function___extrair_geometria_H59c6fe2d --> extern_especificacoes__GrainSpec_Hff300395
    ALVO --> code_motor_adaptador_openmotor_py__function___aplicar_overrides_H53241152
    ALVO --> code_motor_adaptador_openmotor_py__function___extrair_geometria_H59c6fe2d
    ALVO --> code_motor_adaptador_openmotor_py__function___pico_canal_2d_Hb5c40048
    ALVO --> code_motor_adaptador_openmotor_py__struct__ResultadoRic_H7c88ef35
    ALVO --> extern_copy__deepcopy_H618b073e
    ALVO --> extern_fileIO__loadFile_Hfe8ed6d4
    ALVO --> extern_motor__Motor_Hcc0c9bee
    ALVO --> extern_numpy__trapezoid_Hbc102c77
    ALVO --> extern_pathlib__Path_Hd2621e53
    click code_motor_derivador_py__function___resolver_fonte_e_geometria_H35eb7443 href "src__motor__derivador.c4.md" "Abrir C4 (_resolver_fonte_e_geometria)"
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
| 🚨 Risco Ascendente (Caller) | `_resolver_fonte_e_geometria` | [⚡ `src__motor__derivador.c4.md`](src__motor__derivador.c4.md) |
| 🚨 Risco Ascendente (Caller) | `derivar_motor` | [⚡ `src__motor__derivador.c4.md`](src__motor__derivador.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_motor` | [⚡ `src__relatorios.c4.md`](src__relatorios.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_motor_variacoes` | [⚡ `src__relatorios.c4.md`](src__relatorios.c4.md) |
| 🚨 Risco Ascendente (Caller) | `relatorio_seguranca` | [⚡ `src__relatorios.c4.md`](src__relatorios.c4.md) |
| 🚨 Risco Ascendente (Caller) | `build_motor` | [⚡ `src__simulacao__construtor_foguete.c4.md`](src__simulacao__construtor_foguete.c4.md) |

### Diagrama de Sequência de Execução — `executar_ric()` (`sequenceDiagram`)

> [!NOTE]
> Mostra o fluxo sequencial real de controle de execução da função,
> incluindo condicionais (`alt ... else`) e laços (`loop`).

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'signalColor': '#38bdf8', 'signalTextColor': '#f8fafc', 'actorBkg': '#1e293b', 'actorBorder': '#38bdf8', 'actorTextColor': '#f8fafc' }}}%%
sequenceDiagram
    autonumber
    %% def executar_ric(
    participant self as self
    participant path as path
    participant Motor as Motor
    participant ch as ch
    participant sim as sim
    participant np as np
    self->>self: Path
    self->>path: exists
    alt if not path.exists()
        self->>self: FileNotFoundError
    end
    self->>self: loadFile
    self->>self: str
    alt if overrides
        self->>self: _aplicar_overrides
    end
    self->>self: _extrair_geometria
    self->>Motor: runSimulation
    alt if not sim.success
        self->>self: getattr
        self->>self: str
        self->>self: RuntimeError
    end
    self->>self: float
    self->>ch: getData
    self->>self: float
    self->>ch: getData
    self->>self: float
    self->>ch: getData
    self->>self: float
    self->>ch: getData
    self->>ch: getData
    self->>self: float
    self->>self: sum
    self->>self: isinstance
    self->>self: float
    self->>self: float
    self->>sim: getISP
    self->>self: float
    self->>self: ResultadoRic
    self->>self: float
    self->>np: trapezoid
    self->>self: max
    self->>self: tuple
    self->>self: zip
    self->>self: max
    self->>self: max
    self->>self: _pico_canal_2d
    self->>ch: getData
```

---

## 4. Estrutura de Classes e Contratos (`classDiagram`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
classDiagram
    class ResultadoRic {
        <<dataclass>>
        +grains : tuple~GrainSpec, ...~
        +propellant_density : float
        +throat_radius : float
        +nozzle_exit_radius : float
        +burn_time : tuple~float, float~
        +impulso_total : float
        +empuxo_max : float
        +massa_propelente_inicial : float
        +curva_empuxo : tuple~tuple~float, float~, ...~
        +p0_pico : float
        +kn_pico : float
        +mass_flux_pico : float
        +isp_entregue : float
    }
```

---

## 5. Fluxo Lógico de Funções Locais (`flowchart TD`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    F_0["🔒 _safe_use()"]
    F_1["🔒 _set_path()"]
    F_2["🔒 _aplicar_overrides()"]
    F_3["🔒 _extrair_geometria()"]
    F_4["🔒 _pico_canal_2d()"]
    F_5["🟢 executar_ric()"]
    F_2 --> F_1
    EXTCALL_0["🔗 GrainSpec()\n(src.especificacoes)"]
    click EXTCALL_0 href "src__especificacoes.c4.md" "Abrir C4 de src.especificacoes"
    F_3 --> EXTCALL_0
    F_5 --> F_3
    CLS_ResultadoRic(["📦 ResultadoRic"])
    F_5 -. instancia .-> CLS_ResultadoRic
    F_5 --> F_2
    F_5 --> F_4
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Chamadas Externas Identificadas

| Chamada Local | Módulo de Origem | Documento C4 |
| :--- | :--- | :--- |
| `🔗 GrainSpec()` | `src.especificacoes` | [⚡ `src__especificacoes.c4.md`](src__especificacoes.c4.md) |

---

## 6. Catálogo de Símbolos (Links Diretos para o Código)

### Classes / Contratos

| Classe | Linhas | Tipo | Resumo |
| :--- | :--- | :--- | :--- |
| [`ResultadoRic`](../../../src/motor/adaptador_openmotor.py#L52-L66) | `L52–L66` | `@dataclass` | Geometria efetiva pós-overrides e métricas balísticas da simulação `.ric`. |

### Funções do Módulo

| Função | Linhas | Retorno | Resumo |
| :--- | :--- | :--- | :--- |
| [`_safe_use`](../../../src/motor/adaptador_openmotor.py#L29-L32) | `L29–L32` | `None` | — |
| [`_set_path`](../../../src/motor/adaptador_openmotor.py#L69-L104) | `L69–L104` | `None` | Aplica `valor` em `obj` seguindo `partes` (dot-path com suporte a `*` e índice). |
| [`_aplicar_overrides`](../../../src/motor/adaptador_openmotor.py#L107-L116) | `L107–L116` | `dict` | Retorna uma cópia de `props` com wildcards aplicados antes de índices específicos. |
| [`_extrair_geometria`](../../../src/motor/adaptador_openmotor.py#L119-L141) | `L119–L141` | `tuple[tuple[GrainSpec, ...], float, float, float]` | Extrai `(grains, propellant_density, throat_radius, nozzle_exit_radius)` de `props`. |
| [`_pico_canal_2d`](../../../src/motor/adaptador_openmotor.py#L144-L149) | `L144–L149` | `float` | — |
| [`executar_ric`](../../../src/motor/adaptador_openmotor.py#L152-L201) | `L152–L201` | `ResultadoRic` | Carrega um `.ric`, aplica `overrides` em memória, extrai geometria e roda o OpenMotor. |
