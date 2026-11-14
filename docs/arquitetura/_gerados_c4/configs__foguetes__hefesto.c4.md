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
    INT_0["🧩 configs.foguetes.hefesto.corpo\n(COMPONENTES)"] --> MOD
    click INT_0 href "configs__foguetes__hefesto__corpo.c4.md" "Abrir C4 de configs.foguetes.hefesto.corpo"
    INT_1["🧩 configs.foguetes.hefesto.estocastico\n(ALETAS_E, ALETAS_POS_E, COIFA_E, COIFA_POS_E, ...)"] --> MOD
    click INT_1 href "configs__foguetes__hefesto__estocastico.c4.md" "Abrir C4 de configs.foguetes.hefesto.estocastico"
    INT_2["🧩 configs.foguetes.hefesto.geometria\n(ALETA_IREC, ALETAS, ALETAS_TRAPEZIO_EQUIV, COIFA, ...)"] --> MOD
    click INT_2 href "configs__foguetes__hefesto__geometria.c4.md" "Abrir C4 de configs.foguetes.hefesto.geometria"
    INT_3["🧩 configs.foguetes.hefesto.motor\n(ENG_MEDUSA, MOTOR_CORE_FWD_MENOR, MOTOR_CORE_UNIFORME, MOTOR_IREC, ...)"] --> MOD
    click INT_3 href "configs__foguetes__hefesto__motor.c4.md" "Abrir C4 de configs.foguetes.hefesto.motor"
    INT_4["🧩 configs.foguetes.hefesto.voo\n(IREC, IREC_E, IREC_ENSEMBLE_E)"] --> MOD
    click INT_4 href "configs__foguetes__hefesto__voo.c4.md" "Abrir C4 de configs.foguetes.hefesto.voo"
    INT_5["🧩 configs.limites\n(LIMITES_IREC)"] --> MOD
    click INT_5 href "configs__limites.c4.md" "Abrir C4 de configs.limites"
    INT_6["🧩 src.especificacoes\n(FogueteSpec)"] --> MOD
    click INT_6 href "src__especificacoes.c4.md" "Abrir C4 de src.especificacoes"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 configs.foguetes.hefesto.corpo` | `COMPONENTES` | [⚡ `configs__foguetes__hefesto__corpo.c4.md`](configs__foguetes__hefesto__corpo.c4.md) |
| `🧩 configs.foguetes.hefesto.estocastico` | `ALETAS_E`, `ALETAS_POS_E`, `COIFA_E`, `COIFA_POS_E`, `FOGUETE_E`, ... | [⚡ `configs__foguetes__hefesto__estocastico.c4.md`](configs__foguetes__hefesto__estocastico.c4.md) |
| `🧩 configs.foguetes.hefesto.geometria` | `ALETA_IREC`, `ALETAS`, `ALETAS_TRAPEZIO_EQUIV`, `COIFA`, `COIFA_IREC`, ... | [⚡ `configs__foguetes__hefesto__geometria.c4.md`](configs__foguetes__hefesto__geometria.c4.md) |
| `🧩 configs.foguetes.hefesto.motor` | `ENG_MEDUSA`, `MOTOR_CORE_FWD_MENOR`, `MOTOR_CORE_UNIFORME`, `MOTOR_IREC`, `MOTOR_THROAT_ESTREITO`, ... | [⚡ `configs__foguetes__hefesto__motor.c4.md`](configs__foguetes__hefesto__motor.c4.md) |
| `🧩 configs.foguetes.hefesto.voo` | `IREC`, `IREC_E`, `IREC_ENSEMBLE_E` | [⚡ `configs__foguetes__hefesto__voo.c4.md`](configs__foguetes__hefesto__voo.c4.md) |
| `🧩 configs.limites` | `LIMITES_IREC` | [⚡ `configs__limites.c4.md`](configs__limites.c4.md) |
| `🧩 src.especificacoes` | `FogueteSpec` | [⚡ `src__especificacoes.c4.md`](src__especificacoes.c4.md) |

---

## 3. Catálogo de Símbolos (Links Diretos para o Código)
