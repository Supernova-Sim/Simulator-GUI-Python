# ⚡ C4 Nível 4 (Código) — `configs/__init__.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`__init__.py`](../../../configs/__init__.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `__init__.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Fachada pública de configurações do projeto.

Reexporta os tipos de especificação (`src.especificacoes`), limites e materiais
(`configs.limites`) e a instância concreta do foguete `HEFESTO`.

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 configs/__init__.py"]
    INT_0["🧩 configs.foguetes.hefesto\n(ALETA_IREC, ALETAS, ALETAS_E, ALETAS_POS_E, ...)"] --> MOD
    click INT_0 href "configs__foguetes__hefesto.c4.md" "Abrir C4 de configs.foguetes.hefesto"
    INT_1["🧩 configs.limites\n(ALUMINIO_6061, COIFA_EFETIVA, COMPOSITO_EFETIVO, COMPOSITO_G10, ...)"] --> MOD
    click INT_1 href "configs__limites.c4.md" "Abrir C4 de configs.limites"
    INT_2["🧩 src.especificacoes\n(LIMITES_PADRAO, AletaSpec, CoifaSpec, FogueteSpec, ...)"] --> MOD
    click INT_2 href "src__especificacoes.c4.md" "Abrir C4 de src.especificacoes"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 configs.foguetes.hefesto` | `ALETA_IREC`, `ALETAS`, `ALETAS_E`, `ALETAS_POS_E`, `ALETAS_TRAPEZIO_EQUIV`, ... | [⚡ `configs__foguetes__hefesto.c4.md`](configs__foguetes__hefesto.c4.md) |
| `🧩 configs.limites` | `ALUMINIO_6061`, `COIFA_EFETIVA`, `COMPOSITO_EFETIVO`, `COMPOSITO_G10`, `EROSION_MAX_GARGANTA`, ... | [⚡ `configs__limites.c4.md`](configs__limites.c4.md) |
| `🧩 src.especificacoes` | `LIMITES_PADRAO`, `AletaSpec`, `CoifaSpec`, `FogueteSpec`, `GeometriaMedidaSpec`, ... | [⚡ `src__especificacoes.c4.md`](src__especificacoes.c4.md) |

---

## 3. Catálogo de Símbolos (Links Diretos para o Código)
