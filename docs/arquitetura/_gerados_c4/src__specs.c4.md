# ⚡ C4 Nível 4 (Código) — `src/specs.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`specs.py`](../../../src/specs.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `specs.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Especificações de domínio (Specs) e validação de contratos (fail-fast).

Este módulo define todas as estruturas de entrada do projeto. Ele NÃO importa
nada de `configs/`, garantindo que a camada de domínio (`src/`) seja 100%
independente de instâncias concretas de foguetes.

Todas as unidades estão no Sistema Internacional (SI: m, kg, s, Pa, kg/m³),
salvo indicação explícita (como ângulos em graus).

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 src/specs.py"]
    NONE["Sem dependências externas (Python puro)"]
    NONE --> MOD
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 3. Estrutura de Classes e Contratos (`classDiagram`)

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
        +resumo() str
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
        +dict_rocket() dict~str, Any~
        +dict_coifa() dict~str, Any~
        +dict_aletas_freeform() dict~str, Any~
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

## 4. Catálogo de Símbolos (Links Diretos para o Código)

### Classes / Contratos

| Classe | Linhas | Tipo | Resumo |
| :--- | :--- | :--- | :--- |
| [`LimitesSeguranca`](../../../src/specs.py#L24-L50) | `L24–L50` | `@dataclass` | Critérios de aceitação estrutural e operacional (ex.: IREC). |
| [`GrainSpec`](../../../src/specs.py#L57-L79) | `L57–L79` | `@dataclass` | Grão propelente cilíndrico oco (BATES). |
| [`MotorSpec`](../../../src/specs.py#L83-L210) | `L83–L210` | `@dataclass` | Especificação declarativa de um motor sólido. |
| [`TuboSpec`](../../../src/specs.py#L217-L242) | `L217–L242` | `@dataclass` | Cilindro oco (ou maciço quando espessura == raio_externo). |
| [`MassaPontualSpec`](../../../src/specs.py#L246-L266) | `L246–L266` | `@dataclass` | Componente interno com massa fixa e geometria equivalente para inércia. |
| [`AletaSpec`](../../../src/specs.py#L270-L298) | `L270–L298` | `@dataclass` | Conjunto de aletas trapezoidais/freeform em SI. |
| [`CoifaSpec`](../../../src/specs.py#L302-L324) | `L302–L324` | `@dataclass` | Coifa modelada como casca fina sobre o perfil `kind`. |
| [`GeometriaMedidaSpec`](../../../src/specs.py#L331-L392) | `L331–L392` | `@dataclass` | Propriedades globais medidas diretamente na bancada/OpenRocket (`modo='medido'`). |
| [`FogueteSpec`](../../../src/specs.py#L399-L433) | `L399–L433` | `@dataclass` | Identidade completa de um foguete (suporta modos 'calculado' e 'medido'). |
