# ⚡ C4 Nível 4 (Código) — `configs/limites.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`limites.py`](../../../configs/limites.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `limites.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Limites de projeto do foguete (IREC + restrições estruturais/operacionais).

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 configs/limites.py"]
    INT_0["🧩 configs.material\n(SIGMA_LIM_AL6063_T5)"] --> MOD
    click INT_0 href "configs__material.c4.md" "Abrir C4 de configs.material"
    INT_1["🧩 src.specs\n(LimitesSeguranca)"] --> MOD
    click INT_1 href "src__specs.c4.md" "Abrir C4 de src.specs"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 configs.material` | `SIGMA_LIM_AL6063_T5` | [⚡ `configs__material.c4.md`](configs__material.c4.md) |
| `🧩 src.specs` | `LimitesSeguranca` | [⚡ `src__specs.c4.md`](src__specs.c4.md) |

---

## 3. Catálogo de Símbolos (Links Diretos para o Código)
