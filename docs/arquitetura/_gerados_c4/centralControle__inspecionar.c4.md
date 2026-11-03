# ⚡ C4 Nível 4 (Código) — `centralControle/inspecionar.py`

> [!NOTE]
> **Gerado automaticamente a partir da AST do código-fonte e motor a2m.**
> Pela regra do modelo C4, o Nível 4 nunca é desenhado manualmente — ele reflete
> em tempo real as classes, funções, impacto e chamadas presentes em [`inspecionar.py`](../../../centralControle/inspecionar.py).

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](../c1-contexto.md) · [📦 Nível 2: Containers](../c2-containers.md) · [🧩 C3: Pipeline de Execução & Voo](../c3-execucao-voo.md) · **⚡ Nível 4: `inspecionar.py`** · [📖 Guia de Visualização](../../../centralControle/GUIA_VISUALIZACAO.md)

---

## 1. Propósito do Módulo

Inspeção da configuração do foguete Hefesto.

Delega a formatação e os relatórios para `src.inspecao`, injetando as
especificações concretas de `configs`.

Uso pela CLI:
    python centralControle/inspecionar.py motor       # só o motor
    python centralControle/inspecionar.py variacoes   # comparativo das variações
    python centralControle/inspecionar.py estrutura   # calculado vs medido + componentes
    python centralControle/inspecionar.py seguranca   # FS e limites
    python centralControle/inspecionar.py voo         # parâmetros de voo
    python centralControle/inspecionar.py tudo        # tudo acima

---

## 2. Fronteiras e Dependências do Arquivo

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart LR
    MOD["📄 centralControle/inspecionar.py"]
    INT_0["🧩 configs\n(HEFESTO, IREC, IREC_E, IREC_ENSEMBLE_E, ...)"] --> MOD
    click INT_0 href "configs.c4.md" "Abrir C4 de configs"
    INT_1["🧩 configs.foguetes.hefesto.motor_variacoes\n(PARAMS_LIVRES, VARIACOES)"] --> MOD
    click INT_1 href "configs__foguetes__hefesto__motor_variacoes.c4.md" "Abrir C4 de configs.foguetes.hefesto.motor_variacoes"
    INT_2["🧩 src.ambiente\n(build_irec)"] --> MOD
    click INT_2 href "src__ambiente.c4.md" "Abrir C4 de src.ambiente"
    INT_3["🧩 src.inspecao\n(relatorio_estrutura, relatorio_motor, relatorio_motor_variacoes, relatorio_seguranca, ...)"] --> MOD
    click INT_3 href "src__inspecao.c4.md" "Abrir C4 de src.inspecao"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Dependências Internas Navegáveis

| Dependência | Símbolos Importados | Documento C4 |
| :--- | :--- | :--- |
| `🧩 configs` | `HEFESTO`, `IREC`, `IREC_E`, `IREC_ENSEMBLE_E`, `MOTOR_IREC` | [⚡ `configs.c4.md`](configs.c4.md) |
| `🧩 configs.foguetes.hefesto.motor_variacoes` | `PARAMS_LIVRES`, `VARIACOES` | [⚡ `configs__foguetes__hefesto__motor_variacoes.c4.md`](configs__foguetes__hefesto__motor_variacoes.c4.md) |
| `🧩 src.ambiente` | `build_irec` | [⚡ `src__ambiente.c4.md`](src__ambiente.c4.md) |
| `🧩 src.inspecao` | `relatorio_estrutura`, `relatorio_motor`, `relatorio_motor_variacoes`, `relatorio_seguranca`, `relatorio_voo` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |

---

## 3. Fluxo Lógico de Funções Locais (`flowchart TD`)

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    F_0["🟢 inspecionar_motor()"]
    F_1["🟢 inspecionar_motor_variacoes()"]
    F_2["🟢 inspecionar_estrutura()"]
    F_3["🟢 inspecionar_seguranca()"]
    F_4["🟢 inspecionar_voo()"]
    F_5["🟢 inspecionar_tudo()"]
    F_6["🟢 main()"]
    EXTCALL_0["🔗 relatorio_motor()\n(src.inspecao)"]
    click EXTCALL_0 href "src__inspecao.c4.md" "Abrir C4 de src.inspecao"
    F_0 --> EXTCALL_0
    EXTCALL_1["🔗 relatorio_motor_variacoes()\n(src.inspecao)"]
    click EXTCALL_1 href "src__inspecao.c4.md" "Abrir C4 de src.inspecao"
    F_1 --> EXTCALL_1
    EXTCALL_2["🔗 relatorio_estrutura()\n(src.inspecao)"]
    click EXTCALL_2 href "src__inspecao.c4.md" "Abrir C4 de src.inspecao"
    F_2 --> EXTCALL_2
    EXTCALL_3["🔗 relatorio_seguranca()\n(src.inspecao)"]
    click EXTCALL_3 href "src__inspecao.c4.md" "Abrir C4 de src.inspecao"
    F_3 --> EXTCALL_3
    EXTCALL_4["🔗 relatorio_voo()\n(src.inspecao)"]
    click EXTCALL_4 href "src__inspecao.c4.md" "Abrir C4 de src.inspecao"
    F_4 --> EXTCALL_4
    EXTCALL_5["🔗 build_irec()\n(src.ambiente)"]
    click EXTCALL_5 href "src__ambiente.c4.md" "Abrir C4 de src.ambiente"
    F_4 --> EXTCALL_5
    F_5 --> EXTCALL_0
    F_5 --> EXTCALL_1
    F_5 --> EXTCALL_2
    F_5 --> EXTCALL_3
    F_5 --> F_4
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

#### 🧭 Chamadas Externas Identificadas

| Chamada Local | Módulo de Origem | Documento C4 |
| :--- | :--- | :--- |
| `🔗 relatorio_motor()` | `src.inspecao` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |
| `🔗 relatorio_motor_variacoes()` | `src.inspecao` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |
| `🔗 relatorio_estrutura()` | `src.inspecao` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |
| `🔗 relatorio_seguranca()` | `src.inspecao` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |
| `🔗 relatorio_voo()` | `src.inspecao` | [⚡ `src__inspecao.c4.md`](src__inspecao.c4.md) |
| `🔗 build_irec()` | `src.ambiente` | [⚡ `src__ambiente.c4.md`](src__ambiente.c4.md) |

---

## 4. Catálogo de Símbolos (Links Diretos para o Código)

### Funções do Módulo

| Função | Linhas | Retorno | Resumo |
| :--- | :--- | :--- | :--- |
| [`inspecionar_motor`](../../../centralControle/inspecionar.py#L37-L38) | `L37–L38` | `None` | — |
| [`inspecionar_motor_variacoes`](../../../centralControle/inspecionar.py#L41-L42) | `L41–L42` | `None` | — |
| [`inspecionar_estrutura`](../../../centralControle/inspecionar.py#L45-L46) | `L45–L46` | `None` | — |
| [`inspecionar_seguranca`](../../../centralControle/inspecionar.py#L49-L50) | `L49–L50` | `None` | — |
| [`inspecionar_voo`](../../../centralControle/inspecionar.py#L53-L59) | `L53–L59` | `None` | — |
| [`inspecionar_tudo`](../../../centralControle/inspecionar.py#L62-L68) | `L62–L68` | `None` | — |
| [`main`](../../../centralControle/inspecionar.py#L81-L93) | `L81–L93` | `None` | — |
