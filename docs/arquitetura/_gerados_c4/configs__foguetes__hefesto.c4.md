# ⚡ C4 Nível 4 (Código) — `configs/foguetes/hefesto/__init__.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`__init__.py`](../../../configs/foguetes/hefesto/__init__.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `__init__.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Instância concreta: foguete Hefesto.

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 configs/foguetes/hefesto/__init__.py"]
    INT_0["🧩 configs.foguetes.hefesto.aletas_cfg\n(ALETA_IREC, ALETAS_TRAPEZIO_EQUIV)"] --> MOD
    click INT_0 href "configs__foguetes__hefesto__aletas_cfg.c4.md" "Abrir C4 de configs.foguetes.hefesto.aletas_cfg"
    INT_1["🧩 configs.foguetes.hefesto.coifa_cfg\n(COIFA_IREC)"] --> MOD
    click INT_1 href "configs__foguetes__hefesto__coifa_cfg.c4.md" "Abrir C4 de configs.foguetes.hefesto.coifa_cfg"
    INT_2["🧩 configs.foguetes.hefesto.corpo\n(COMPONENTES)"] --> MOD
    click INT_2 href "configs__foguetes__hefesto__corpo.c4.md" "Abrir C4 de configs.foguetes.hefesto.corpo"
    INT_3["🧩 configs.foguetes.hefesto.estocastico\n(ALETAS_E, ALETAS_POS_E, COIFA_E, COIFA_POS_E, ...)"] --> MOD
    click INT_3 href "configs__foguetes__hefesto__estocastico.c4.md" "Abrir C4 de configs.foguetes.hefesto.estocastico"
    INT_4["🧩 configs.foguetes.hefesto.geometria\n(ALETAS, COIFA, FOGUETE, GEOMETRIA_MEDIDA_HEFESTO, ...)"] --> MOD
    click INT_4 href "configs__foguetes__hefesto__geometria.c4.md" "Abrir C4 de configs.foguetes.hefesto.geometria"
    INT_5["🧩 configs.foguetes.hefesto.motor_cfg\n(ENG_MEDUSA, MOTOR_IREC, RIC_MEDUSA)"] --> MOD
    click INT_5 href "configs__foguetes__hefesto__motor_cfg.c4.md" "Abrir C4 de configs.foguetes.hefesto.motor_cfg"
    INT_6["🧩 configs.foguetes.hefesto.recuperacao\n(REEFED, UNREEFED)"] --> MOD
    click INT_6 href "configs__foguetes__hefesto__recuperacao.c4.md" "Abrir C4 de configs.foguetes.hefesto.recuperacao"
    INT_7["🧩 configs.foguetes.hefesto.voo\n(IREC, IREC_E, IREC_ENSEMBLE_E)"] --> MOD
    click INT_7 href "configs__foguetes__hefesto__voo.c4.md" "Abrir C4 de configs.foguetes.hefesto.voo"
    INT_8["🧩 configs.limites\n(LIMITES_IREC)"] --> MOD
    click INT_8 href "configs__limites.c4.md" "Abrir C4 de configs.limites"
    INT_9["🧩 src.specs\n(FogueteSpec)"] --> MOD
    click INT_9 href "src__specs.c4.md" "Abrir C4 de src.specs"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 configs.foguetes.hefesto.aletas_cfg` | `ALETA_IREC`, `ALETAS_TRAPEZIO_EQUIV` | [⚡ `configs__foguetes__hefesto__aletas_cfg.c4.md`](configs__foguetes__hefesto__aletas_cfg.c4.md) |
| `🧩 configs.foguetes.hefesto.coifa_cfg` | `COIFA_IREC` | [⚡ `configs__foguetes__hefesto__coifa_cfg.c4.md`](configs__foguetes__hefesto__coifa_cfg.c4.md) |
| `🧩 configs.foguetes.hefesto.corpo` | `COMPONENTES` | [⚡ `configs__foguetes__hefesto__corpo.c4.md`](configs__foguetes__hefesto__corpo.c4.md) |
| `🧩 configs.foguetes.hefesto.estocastico` | `ALETAS_E`, `ALETAS_POS_E`, `COIFA_E`, `COIFA_POS_E`, `FOGUETE_E`, ... | [⚡ `configs__foguetes__hefesto__estocastico.c4.md`](configs__foguetes__hefesto__estocastico.c4.md) |
| `🧩 configs.foguetes.hefesto.geometria` | `ALETAS`, `COIFA`, `FOGUETE`, `GEOMETRIA_MEDIDA_HEFESTO`, `MOTOR_POSITION`, ... | [⚡ `configs__foguetes__hefesto__geometria.c4.md`](configs__foguetes__hefesto__geometria.c4.md) |
| `🧩 configs.foguetes.hefesto.motor_cfg` | `ENG_MEDUSA`, `MOTOR_IREC`, `RIC_MEDUSA` | [⚡ `configs__foguetes__hefesto__motor_cfg.c4.md`](configs__foguetes__hefesto__motor_cfg.c4.md) |
| `🧩 configs.foguetes.hefesto.recuperacao` | `REEFED`, `UNREEFED` | [⚡ `configs__foguetes__hefesto__recuperacao.c4.md`](configs__foguetes__hefesto__recuperacao.c4.md) |
| `🧩 configs.foguetes.hefesto.voo` | `IREC`, `IREC_E`, `IREC_ENSEMBLE_E` | [⚡ `configs__foguetes__hefesto__voo.c4.md`](configs__foguetes__hefesto__voo.c4.md) |
| `🧩 configs.limites` | `LIMITES_IREC` | [⚡ `configs__limites.c4.md`](configs__limites.c4.md) |
| `🧩 src.specs` | `FogueteSpec` | [⚡ `src__specs.c4.md`](src__specs.c4.md) |

---

## 3. Catálogo de Símbolos (Links Diretos para o Código)
