# ⚡ C4 Nível 4 (Código) — `configs/foguetes/hefesto/geometria.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`geometria.py`](../../../configs/foguetes/hefesto/geometria.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `geometria.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Geometria completa do Hefesto: coifa, aletas, recuperação e medidas de bancada.

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 configs/foguetes/hefesto/geometria.py"]
    INT_0["🧩 configs.limites\n(ALUMINIO_6061, COIFA_EFETIVA)"] --> MOD
    click INT_0 href "configs__limites.c4.md" "Abrir C4 de configs.limites"
    INT_1["🧩 src.caminhos\n(ARRASTO)"] --> MOD
    click INT_1 href "src__caminhos.c4.md" "Abrir C4 de src.caminhos"
    INT_2["🧩 src.especificacoes\n(AletaSpec, CoifaSpec, GeometriaMedidaSpec)"] --> MOD
    click INT_2 href "src__especificacoes.c4.md" "Abrir C4 de src.especificacoes"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 configs.limites` | `ALUMINIO_6061`, `COIFA_EFETIVA` | [⚡ `configs__limites.c4.md`](configs__limites.c4.md) |
| `🧩 src.caminhos` | `ARRASTO` | [⚡ `src__caminhos.c4.md`](src__caminhos.c4.md) |
| `🧩 src.especificacoes` | `AletaSpec`, `CoifaSpec`, `GeometriaMedidaSpec` | [⚡ `src__especificacoes.c4.md`](src__especificacoes.c4.md) |

---

## 3. Catálogo de Símbolos (Links Diretos para o Código)
