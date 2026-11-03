# ⚡ C4 Nível 4 (Código) — `src/inspecao.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`inspecao.py`](../../../src/inspecao.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `inspecao.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Relatórios de inspeção e diagnóstico estrutural, balístico e de voo.

Unifica o antigo `src/dump.py` e a formatação de `centralControle/inspecionar.py`
em um módulo puro (não importa `configs/`, recebendo os objetos por argumento).

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 src/inspecao.py"]
    INT_0["🧩 src.calculos.motor\n(MotorDerivado, derivar_motor)"] --> MOD
    click INT_0 href "src__calculos__motor.c4.md" "Abrir C4 de src.calculos.motor"
    INT_1["🧩 src.agregador_estrutural\n(resolver)"] --> MOD
    click INT_1 href "src__agregador_estrutural.c4.md" "Abrir C4 de src.agregador_estrutural"
    INT_2["🧩 src.specs\n(FogueteSpec, MotorSpec, TuboSpec)"] --> MOD
    click INT_2 href "src__specs.c4.md" "Abrir C4 de src.specs"
    EXT_0["📚 collections ( lib externa )"] -.-> MOD
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 src.agregador_estrutural` | `resolver` | [⚡ `src__agregador_estrutural.c4.md`](src__agregador_estrutural.c4.md) |
| `🧩 src.calculos.motor` | `MotorDerivado`, `derivar_motor` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| `🧩 src.specs` | `FogueteSpec`, `MotorSpec`, `TuboSpec` | [⚡ `src__specs.c4.md`](src__specs.c4.md) |

---

## 3. Impacto Sistêmico e Fluxo de Execução

### Análise de Impacto Sistêmico (`a2m impact`)

> [!IMPORTANT]
> **Mapeamento de Efeito Cascata ao Modificar `relatorio_motor()`:**
> - **Risco de Quebra Ascendente (Vermelho):** Funções e módulos externos que chamam esta lógica.
> - **Impacto Descendente (Azul):** Rotinas internas e dependências consumidas.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
graph TD
    classDef target fill:#ffe6cc,stroke:#d79b00,stroke-width:3px,color:#000
    classDef upward fill:#f8cecc,stroke:#b85450,stroke-width:2px,color:#000
    classDef downward fill:#dae8fc,stroke:#6c8ebf,stroke-width:1px,color:#000

    ALVO(("⭐ relatorio_motor (ALVO)")):::target

    subgraph Descendente["🧩 Impacto Descendente (Dependências consumidas)"]
        code_calculos_seguranca_py__function__check_kn_He000bcfb["check_kn"]:::downward
        code_calculos_seguranca_py__function__fs_carcaca_H13b5bc35["fs_carcaca"]:::downward
        code_calculos_motor_py__function___ler_eng_H458942d7["_ler_eng"]:::downward
        code_calculos_motor_py__function__derivar_motor_H72c18b31["derivar_motor"]:::downward
        code_calculos_motorlib_wrapper_py__function__extrair_geometria_props_Hbcbfe32c["extrair_geometria_props"]:::downward
        code_calculos_seguranca_py__function__check_p0_Hd65d174d["check_p0"]:::downward
        code_calculos_motor_py__function___derivar_carcaca_H48dc928e["_derivar_carcaca"]:::downward
        code_inspecao_py__function___linha_H7f8c9815["_linha"]:::downward
        code_calculos_motorlib_wrapper_py__function__carregar_props_Hb7e62dfb["carregar_props"]:::downward
        code_inspecao_py__function___sub_Ha278da50["_sub"]:::downward
        code_calculos_motor_py__struct__MotorDerivado_Hf96b1b33["MotorDerivado"]:::downward
        code_calculos_motorlib_variacoes_py__function__aplicar_overrides_H8051349c["aplicar_overrides"]:::downward
        code_calculos_motor_py__function___integrar_trapezio_H515d0959["_integrar_trapezio"]:::downward
        code_inspecao_py__function___fmt_H6557fdcc["_fmt"]:::downward
        code_calculos_motor_py__function___derivar_inercia_seca_H6f2bab99["_derivar_inercia_seca"]:::downward
        extern_math__sqrt_H86ccf542["sqrt"]:::downward
        code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041["_resolver_fonte_e_geometria"]:::downward
        code_calculos_seguranca_py__function__check_mass_flux_H1757a559["check_mass_flux"]:::downward
        code_calculos_motor_py__function___diagnosticar_H34040dd9["_diagnosticar"]:::downward
        code_calculos_motor_py__function___derivar_dos_graos_H98100ac7["_derivar_dos_graos"]:::downward
        code_calculos_motorlib_wrapper_py__function__simular_props_Hb21e1ad9["simular_props"]:::downward
        code_inspecao_py__function___titulo_H779bed6c["_titulo"]:::downward
    end
    code_calculos_motor_py__function___derivar_dos_graos_H98100ac7 --> extern_math__sqrt_H86ccf542
    code_calculos_motor_py__function___diagnosticar_H34040dd9 --> code_calculos_seguranca_py__function__check_kn_He000bcfb
    code_calculos_motor_py__function___diagnosticar_H34040dd9 --> code_calculos_seguranca_py__function__check_mass_flux_H1757a559
    code_calculos_motor_py__function___diagnosticar_H34040dd9 --> code_calculos_seguranca_py__function__check_p0_Hd65d174d
    code_calculos_motor_py__function___diagnosticar_H34040dd9 --> code_calculos_seguranca_py__function__fs_carcaca_H13b5bc35
    code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041 --> code_calculos_motor_py__function___integrar_trapezio_H515d0959
    code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041 --> code_calculos_motor_py__function___ler_eng_H458942d7
    code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041 --> code_calculos_motorlib_variacoes_py__function__aplicar_overrides_H8051349c
    code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041 --> code_calculos_motorlib_wrapper_py__function__carregar_props_Hb7e62dfb
    code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041 --> code_calculos_motorlib_wrapper_py__function__extrair_geometria_props_Hbcbfe32c
    code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041 --> code_calculos_motorlib_wrapper_py__function__simular_props_Hb21e1ad9
    code_calculos_motor_py__function__derivar_motor_H72c18b31 --> code_calculos_motor_py__function___derivar_carcaca_H48dc928e
    code_calculos_motor_py__function__derivar_motor_H72c18b31 --> code_calculos_motor_py__function___derivar_dos_graos_H98100ac7
    code_calculos_motor_py__function__derivar_motor_H72c18b31 --> code_calculos_motor_py__function___derivar_inercia_seca_H6f2bab99
    code_calculos_motor_py__function__derivar_motor_H72c18b31 --> code_calculos_motor_py__function___diagnosticar_H34040dd9
    code_calculos_motor_py__function__derivar_motor_H72c18b31 --> code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041
    code_calculos_motor_py__function__derivar_motor_H72c18b31 --> code_calculos_motor_py__struct__MotorDerivado_Hf96b1b33
    ALVO --> code_calculos_motor_py__function__derivar_motor_H72c18b31
    ALVO --> code_inspecao_py__function___fmt_H6557fdcc
    ALVO --> code_inspecao_py__function___linha_H7f8c9815
    ALVO --> code_inspecao_py__function___sub_Ha278da50
    ALVO --> code_inspecao_py__function___titulo_H779bed6c
    click code_calculos_motor_py__function___derivar_carcaca_H48dc928e href "src__calculos__motor.c4.md" "Abrir C4 (_derivar_carcaca)"
    click code_calculos_motor_py__function___derivar_dos_graos_H98100ac7 href "src__calculos__motor.c4.md" "Abrir C4 (_derivar_dos_graos)"
    click code_calculos_motor_py__function___derivar_inercia_seca_H6f2bab99 href "src__calculos__motor.c4.md" "Abrir C4 (_derivar_inercia_seca)"
    click code_calculos_motor_py__function___diagnosticar_H34040dd9 href "src__calculos__motor.c4.md" "Abrir C4 (_diagnosticar)"
    click code_calculos_motor_py__function___integrar_trapezio_H515d0959 href "src__calculos__motor.c4.md" "Abrir C4 (_integrar_trapezio)"
    click code_calculos_motor_py__function___ler_eng_H458942d7 href "src__calculos__motor.c4.md" "Abrir C4 (_ler_eng)"
    click code_calculos_motor_py__function___resolver_fonte_e_geometria_H1a15d041 href "src__calculos__motor.c4.md" "Abrir C4 (_resolver_fonte_e_geometria)"
    click code_calculos_motor_py__function__derivar_motor_H72c18b31 href "src__calculos__motor.c4.md" "Abrir C4 (derivar_motor)"
    click code_calculos_motor_py__struct__MotorDerivado_Hf96b1b33 href "src__calculos__motor.c4.md" "Abrir C4 (MotorDerivado)"
    click code_calculos_motorlib_variacoes_py__function__aplicar_overrides_H8051349c href "src__calculos__motorlib_variacoes.c4.md" "Abrir C4 (aplicar_overrides)"
    click code_calculos_motorlib_wrapper_py__function__carregar_props_Hb7e62dfb href "src__calculos__motorlib_wrapper.c4.md" "Abrir C4 (carregar_props)"
    click code_calculos_motorlib_wrapper_py__function__extrair_geometria_props_Hbcbfe32c href "src__calculos__motorlib_wrapper.c4.md" "Abrir C4 (extrair_geometria_props)"
    click code_calculos_motorlib_wrapper_py__function__simular_props_Hb21e1ad9 href "src__calculos__motorlib_wrapper.c4.md" "Abrir C4 (simular_props)"
    click code_calculos_seguranca_py__function__check_kn_He000bcfb href "src__calculos__seguranca.c4.md" "Abrir C4 (check_kn)"
    click code_calculos_seguranca_py__function__check_mass_flux_H1757a559 href "src__calculos__seguranca.c4.md" "Abrir C4 (check_mass_flux)"
    click code_calculos_seguranca_py__function__check_p0_Hd65d174d href "src__calculos__seguranca.c4.md" "Abrir C4 (check_p0)"
    click code_calculos_seguranca_py__function__fs_carcaca_H13b5bc35 href "src__calculos__seguranca.c4.md" "Abrir C4 (fs_carcaca)"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Atalhos Rápidos de Navegação (Impacto Sistêmico)

| Relação | Símbolo / Função | Arquivo C4 Destino |
| :--- | :--- | :--- |
| 🧩 Impacto Descendente (Callee) | `_derivar_carcaca` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🧩 Impacto Descendente (Callee) | `_derivar_dos_graos` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🧩 Impacto Descendente (Callee) | `_derivar_inercia_seca` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🧩 Impacto Descendente (Callee) | `_diagnosticar` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🧩 Impacto Descendente (Callee) | `_integrar_trapezio` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🧩 Impacto Descendente (Callee) | `_ler_eng` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🧩 Impacto Descendente (Callee) | `_resolver_fonte_e_geometria` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🧩 Impacto Descendente (Callee) | `derivar_motor` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🧩 Impacto Descendente (Callee) | `MotorDerivado` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| 🧩 Impacto Descendente (Callee) | `aplicar_overrides` | [⚡ `src__calculos__motorlib_variacoes.c4.md`](src__calculos__motorlib_variacoes.c4.md) |
| 🧩 Impacto Descendente (Callee) | `carregar_props` | [⚡ `src__calculos__motorlib_wrapper.c4.md`](src__calculos__motorlib_wrapper.c4.md) |
| 🧩 Impacto Descendente (Callee) | `extrair_geometria_props` | [⚡ `src__calculos__motorlib_wrapper.c4.md`](src__calculos__motorlib_wrapper.c4.md) |
| 🧩 Impacto Descendente (Callee) | `simular_props` | [⚡ `src__calculos__motorlib_wrapper.c4.md`](src__calculos__motorlib_wrapper.c4.md) |
| 🧩 Impacto Descendente (Callee) | `check_kn` | [⚡ `src__calculos__seguranca.c4.md`](src__calculos__seguranca.c4.md) |
| 🧩 Impacto Descendente (Callee) | `check_mass_flux` | [⚡ `src__calculos__seguranca.c4.md`](src__calculos__seguranca.c4.md) |
| 🧩 Impacto Descendente (Callee) | `check_p0` | [⚡ `src__calculos__seguranca.c4.md`](src__calculos__seguranca.c4.md) |
| 🧩 Impacto Descendente (Callee) | `fs_carcaca` | [⚡ `src__calculos__seguranca.c4.md`](src__calculos__seguranca.c4.md) |

### Diagrama de Sequência de Execução — `relatorio_motor()` (`sequenceDiagram`)

> [!NOTE]
> Mostra o fluxo sequencial real de controle de execução da função,
> incluindo condicionais (`alt ... else`) e laços (`loop`).

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'signalColor': '#38bdf8', 'signalTextColor': '#f8fafc', 'actorBkg': '#1e293b', 'actorBorder': '#38bdf8', 'actorTextColor': '#f8fafc' }}}%%
sequenceDiagram
    autonumber
    %% def relatorio_motor(
    participant self as self
    self->>self: derivar_motor
    self->>self: _titulo
    self->>self: _linha
    self->>self: _linha
    self->>self: _linha
    self->>self: _linha
    alt if spec.overrides
        self->>self: _linha
        self->>self: len
    end
    self->>self: _sub
    self->>self: len
    self->>self: enumerate
    loop for enumerate(d.grains)
        self->>self: print
    end
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _sub
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _sub
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _titulo
    self->>self: _sub
    self->>self: _linha
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _sub
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _sub
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    self->>self: _linha
    self->>self: _fmt
    alt if d.p0_pico is not None
        self->>self: _sub
        self->>self: _linha
        self->>self: _fmt
        self->>self: _linha
        self->>self: _fmt
        self->>self: _linha
        self->>self: _fmt
    end
```

---

## 4. Fluxo Lógico de Funções Locais (`flowchart TD`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    F_0["🔒 _titulo()"]
    F_1["🔒 _sub()"]
    F_2["🔒 _linha()"]
    F_3["🔒 _fmt()"]
    F_4["🟢 relatorio_motor()"]
    F_5["🟢 relatorio_motor_variacoes()"]
    F_6["🟢 relatorio_estrutura()"]
    F_7["🟢 relatorio_seguranca()"]
    F_8["🟢 relatorio_voo()"]
    F_4 --> F_0
    F_4 --> F_2
    F_4 --> F_1
    EXTCALL_0["🔗 derivar_motor()\n(src.calculos.motor)"]
    click EXTCALL_0 href "src__calculos__motor.c4.md" "Abrir C4 de src.calculos.motor"
    F_4 --> EXTCALL_0
    F_4 --> F_3
    F_5 --> F_0
    F_5 --> F_1
    F_5 --> EXTCALL_0
    F_6 --> F_0
    F_6 --> F_2
    F_6 --> F_3
    EXTCALL_1["🔗 resolver()\n(src.agregador_estrutural)"]
    click EXTCALL_1 href "src__agregador_estrutural.c4.md" "Abrir C4 de src.agregador_estrutural"
    F_6 --> EXTCALL_1
    F_6 --> F_1
    F_7 --> F_0
    F_7 --> EXTCALL_0
    F_8 --> F_0
    F_8 --> F_1
    F_8 --> F_2
    F_8 --> F_3
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Chamadas Externas Identificadas

| Chamada Local | Módulo de Origem | Documento C4 |
| :--- | :--- | :--- |
| `🔗 derivar_motor()` | `src.calculos.motor` | [⚡ `src__calculos__motor.c4.md`](src__calculos__motor.c4.md) |
| `🔗 resolver()` | `src.agregador_estrutural` | [⚡ `src__agregador_estrutural.c4.md`](src__agregador_estrutural.c4.md) |

---

## 5. Catálogo de Símbolos (Links Diretos para o Código)

### Funções do Módulo

| Função | Linhas | Retorno | Resumo |
| :--- | :--- | :--- | :--- |
| [`_titulo`](../../../src/inspecao.py#L19-L23) | `L19–L23` | `None` | — |
| [`_sub`](../../../src/inspecao.py#L26-L28) | `L26–L28` | `None` | — |
| [`_linha`](../../../src/inspecao.py#L31-L35) | `L31–L35` | `None` | — |
| [`_fmt`](../../../src/inspecao.py#L38-L42) | `L38–L42` | `str` | — |
| [`relatorio_motor`](../../../src/inspecao.py#L45-L112) | `L45–L112` | `MotorDerivado` | Imprime especificação, propriedades derivadas e balística interna do motor. |
| [`relatorio_motor_variacoes`](../../../src/inspecao.py#L115-L167) | `L115–L167` | `None` | Imprime tabela comparativa lado a lado para um dicionário de variações de motor. |
| [`relatorio_estrutura`](../../../src/inspecao.py#L170-L272) | `L170–L272` | `None` | Imprime o detalhamento estrutural (comparando modo calculado e modo medido). |
| [`relatorio_seguranca`](../../../src/inspecao.py#L275-L293) | `L275–L293` | `None` | Imprime os diagnósticos de segurança do motor. |
| [`relatorio_voo`](../../../src/inspecao.py#L296-L326) | `L296–L326` | `None` | Imprime os parâmetros de lançamento e atmosfera. |
