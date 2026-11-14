# ⚡ C4 Nível 4 (Código) — `src/especificacoes.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`especificacoes.py`](../../../src/especificacoes.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `especificacoes.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Especificações de domínio (Specs), validação fail-fast e whitelist de overrides.

Define todos os contratos de entrada do projeto sem importar `configs/` nem
dependências pesadas (OpenMotor/RocketPy), garantindo pureza no `import`.
Todas as unidades estão no Sistema Internacional (SI: m, kg, s, Pa, kg/m³),
salvo indicação explícita (como ângulos em graus).

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 src/especificacoes.py"]
    NONE["Sem dependências externas (Python puro)"]
    NONE --> MOD
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 3. Impacto Sistêmico e Fluxo de Execução

### Análise de Impacto Sistêmico (`a2m impact`)

> [!IMPORTANT]
> **Mapeamento de Efeito Cascata ao Modificar `validar_overrides()`:**
> - **Risco de Quebra Ascendente (Vermelho):** Funções e módulos externos que chamam esta lógica.
> - **Impacto Descendente (Azul):** Rotinas internas e dependências consumidas.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
graph TD
    classDef target fill:#ffe6cc,stroke:#d79b00,stroke-width:3px,color:#000
    classDef upward fill:#f8cecc,stroke:#b85450,stroke-width:2px,color:#000
    classDef downward fill:#dae8fc,stroke:#6c8ebf,stroke-width:1px,color:#000

    ALVO(("⭐ validar_overrides (ALVO)")):::target

    subgraph Descendente["🧩 Impacto Descendente (Dependências consumidas)"]
        code_especificacoes_py__function___normalizar_path_H458e9349["_normalizar_path"]:::downward
    end
    ALVO --> code_especificacoes_py__function___normalizar_path_H458e9349
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

### Diagrama de Sequência de Execução — `validar_overrides()` (`sequenceDiagram`)

> [!NOTE]
> Mostra o fluxo sequencial real de controle de execução da função,
> incluindo condicionais (`alt ... else`) e laços (`loop`).

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'signalColor': '#38bdf8', 'signalTextColor': '#f8fafc', 'actorBkg': '#1e293b', 'actorBorder': '#38bdf8', 'actorTextColor': '#f8fafc' }}}%%
sequenceDiagram
    autonumber
    %% def validar_overrides(
    participant self as self
    self->>self: _normalizar_path
    alt if invalidos
        self->>self: sorted
        self->>self: ValueError
        self->>self: join
    end
```

---

## 4. Estrutura de Classes e Contratos (`classDiagram`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
classDiagram
    class LimitesSeguranca {
        <<dataclass>>
        +fs_min_carcaca : float
        +fs_alvo_carcaca : float
        +fs_min_aletas : float
        +fs_min_estrutura : float
        +fs_min_recuperacao : float
        +p0_max : float
        +kn_max : float
        +mass_flux_max : float
        +port_throat_min : float
        +erosion_max_garganta : float
        +sigma_lim_carcaca : float
        +__post_init__() None
    }
    class GrainSpec {
        <<dataclass>>
        +length : float
        +outer_radius : float
        +inner_radius : float
        +__post_init__() None
        +to_dict() dict~str, float~
    }
    class MotorSpec {
        <<dataclass>>
        +nome : str
        +case_inner_radius : float
        +case_wall_thickness : float
        +case_density : float
        +grain_separation : float
        +nozzle_position : float
        +ric_path : str or Path?
        +thrust_curve_path : str or Path?
        +grains : tuple~GrainSpec, ...~
        +propellant_density : float?
        +nozzle_exit_radius : float?
        +throat_radius : float?
        +case_length : float?
        +margin_nozzle_side : float
        +margin_forward_side : float
        +dry_mass : float?
        +dry_mass_extra : float
        +nozzle_mass : float
        +dry_inertia_override : tuple~float, float, float~?
        +overrides : dict~str, Any~?
        +__post_init__() None
        +to_dict() dict~str, Any~
    }
    class TuboSpec {
        <<dataclass>>
        +nome : str
        +raio_externo : float
        +espessura : float
        +comprimento : float
        +posicao : float
        +densidade : float
        +massa_extra : float
        +__post_init__() None
        +raio_interno() float
    }
    class MassaPontualSpec {
        <<dataclass>>
        +nome : str
        +massa : float
        +posicao : float
        +raio_equivalente : float
        +comprimento : float
        +__post_init__() None
    }
    class AletaSpec {
        <<dataclass>>
        +nome : str
        +n : int
        +root_chord : float
        +tip_chord : float
        +span_le : float
        +span_te : float
        +sweep_length : float
        +thickness : float
        +position : float
        +densidade : float
        +cant_angle : float
        +__post_init__() None
        +shape_points() list~tuple~float, float~~
    }
    class CoifaSpec {
        <<dataclass>>
        +nome : str
        +length : float
        +kind : str
        +position : float
        +thickness : float
        +densidade : float
        +massa_extra : float
        +posicao_massa_extra : float?
        +__post_init__() None
    }
    class GeometriaMedidaSpec {
        <<dataclass>>
        +raio : float
        +massa_seca : float
        +inercia_transversal : float
        +inercia_longitudinal : float
        +cg_sem_motor : float
        +coifa_length : float
        +coifa_kind : str
        +coifa_position : float
        +aletas_n : int
        +aletas_position : float
        +aletas_shape_points : tuple~tuple~float, float~, ...~
        +aletas_cant_angle : float
        +aletas_trapezio_equiv : dict~str, Any~?
        +__post_init__() None
        +inercia_rocketpy() tuple~float, float, float~
    }
    class FogueteSpec {
        <<dataclass>>
        +nome : str
        +raio : float
        +motor : MotorSpec
        +motor_position : float
        +power_off_drag : str or Path
        +power_on_drag : str or Path
        +rail_buttons : dict~str, Any~
        +reefed : dict~str, Any~
        +unreefed : dict~str, Any~
        +componentes : tuple~TuboSpec or MassaPontualSpec, ...~
        +coifa : CoifaSpec?
        +aleta : AletaSpec?
        +geometria_medida : GeometriaMedidaSpec?
        +limites : LimitesSeguranca
        +__post_init__() None
    }
    MotorSpec *-- GrainSpec : grains
    FogueteSpec *-- MotorSpec : motor
    FogueteSpec *-- TuboSpec : componentes
    FogueteSpec *-- MassaPontualSpec : componentes
    FogueteSpec *-- CoifaSpec : coifa
    FogueteSpec *-- AletaSpec : aleta
    FogueteSpec *-- GeometriaMedidaSpec : geometria_medida
    FogueteSpec *-- LimitesSeguranca : limites
```

---

## 5. Fluxo Lógico de Funções Locais (`flowchart TD`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    F_0["🔒 _exigir_positivo()"]
    F_1["🔒 _serializar_dataclass()"]
    F_2["🔒 _normalizar_path()"]
    F_3["🟢 validar_overrides()"]
    F_3 --> F_2
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 6. Catálogo de Símbolos (Links Diretos para o Código)

### Classes / Contratos

| Classe | Linhas | Tipo | Resumo |
| :--- | :--- | :--- | :--- |
| [`LimitesSeguranca`](../../../src/especificacoes.py#L69-L93) | `L69–L93` | `@dataclass` | Critérios de aceitação estrutural e operacional (ex.: IREC). |
| [`GrainSpec`](../../../src/especificacoes.py#L103-L118) | `L103–L118` | `@dataclass` | Grão propelente cilíndrico oco (BATES). |
| [`MotorSpec`](../../../src/especificacoes.py#L122-L186) | `L122–L186` | `@dataclass` | Especificação declarativa de um motor sólido. |
| [`TuboSpec`](../../../src/especificacoes.py#L193-L218) | `L193–L218` | `@dataclass` | Cilindro oco (ou maciço quando espessura == raio_externo). |
| [`MassaPontualSpec`](../../../src/especificacoes.py#L222-L236) | `L222–L236` | `@dataclass` | Componente interno com massa fixa e geometria equivalente para inércia. |
| [`AletaSpec`](../../../src/especificacoes.py#L240-L277) | `L240–L277` | `@dataclass` | Conjunto de aletas trapezoidais/freeform em SI. |
| [`CoifaSpec`](../../../src/especificacoes.py#L281-L296) | `L281–L296` | `@dataclass` | Coifa modelada como casca fina sobre o perfil `kind`. |
| [`GeometriaMedidaSpec`](../../../src/especificacoes.py#L303-L336) | `L303–L336` | `@dataclass` | Propriedades globais medidas diretamente na bancada/OpenRocket (`modo='medido'`). |
| [`FogueteSpec`](../../../src/especificacoes.py#L343-L370) | `L343–L370` | `@dataclass` | Identidade completa de um foguete (suporta modos 'calculado' e 'medido'). |

### Funções do Módulo

| Função | Linhas | Retorno | Resumo |
| :--- | :--- | :--- | :--- |
| [`_exigir_positivo`](../../../src/especificacoes.py#L22-L26) | `L22–L26` | `None` | Falha imediatamente quando qualquer campo numérico é `<= 0`. |
| [`_serializar_dataclass`](../../../src/especificacoes.py#L29-L40) | `L29–L40` | `dict[str, Any]` | Serializa uma dataclass convertendo `Path` para `str` e tuplas para listas. |
| [`_normalizar_path`](../../../src/especificacoes.py#L46-L48) | `L46–L48` | `str` | Substitui índices numéricos por '*' para comparação com a whitelist. |
| [`validar_overrides`](../../../src/especificacoes.py#L51-L62) | `L51–L62` | `None` | Verifica se todos os paths de `overrides` pertencem à `whitelist`. |
