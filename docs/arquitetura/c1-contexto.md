# 🌐 C4 Nível 1 — Contexto do Sistema (Hefesto)

**Navegação na Hierarquia C4:**
**🌐 Nível 1: Contexto** · [📦 Nível 2: Containers](c2-containers.md) · [🧩 C3: Execução & Voo](c3-execucao-voo.md) · [🧩 C3: Subsistema de Motor](c3-subsistema-motor.md)

---

## 1. Visão Geral (Contexto)

O **Hefesto** é a plataforma de engenharia, validação estrutural e simulação de voo 6-DOF da equipe **Supernova Rocketry (UFJF)** para a competição **IREC (Spaceport America Cup)**.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    classDef person fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef system fill:#1e1b4b,stroke:#818cf8,stroke-width:3px,color:#f8fafc;
    classDef ext fill:#1c1917,stroke:#a8a29e,stroke-width:1.5px,color:#e7e5e4;

    ENG["👤 Engenheiro de Propulsão / Estruturas / Voo\n(Equipe Supernova UFJF)"]:::person

    HEF["🚀 Sistema de Simulação Hefesto\n\nValida limites de segurança (FS, P0, Kn),\nresolve massa/inércia (calculado vs medido)\ne simula voo 6-DOF e Monte Carlo."]:::system

    OM["🔥 OpenMotor (motorlib / uilib)\nSolver balístico interno (.ric)"]:::ext
    RP["🪐 RocketPy\nSimulador de voo 6-DOF e atmosfera"]:::ext
    CAD["📐 RASAero / OpenRocket / Bancada\nCurvas de arrasto (.csv) e medições"]:::ext

    ENG -->|"Configura foguete/motor,\ninspeciona FS e roda simulações\n(CLI ou Positron)"| HEF
    HEF -->|"Delega balística interna BATES\ne extrai geometria (.ric)"| OM
    HEF -->|"Monta SolidMotor + Rocket\ne integra trajetória 6-DOF"| RP
    CAD -->|"Fornece Cd(Mach) e dados\nde bancada (modo medido)"| HEF
    click HEF href "c2-containers.md" "Abrir Nível 2: Containers"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 2. Atores e Sistemas Externos

| Elemento | Tipo | Papel no Ecossistema |
| :--- | :--- | :--- |
| **Engenheiro Supernova** | Pessoa | Ajusta geometria, propelente, garganta e analisa estabilidade/apogeu e fatores de segurança. |
| **Hefesto** | Sistema Alvo | Centraliza a verdade física do foguete, garantindo rastreabilidade e validação *fail-fast*. |
| **OpenMotor (`motorlib`)** | Biblioteca Externa | Resolve pressão de câmara $P_0(t)$, $K_n(t)$, fluxo de massa e empuxo a partir do arquivo `.ric`. |
| **RocketPy** | Biblioteca Externa | Integra as equações de movimento 6-DOF sob atmosfera IREC (Spaceport America). |
| **RASAero / Bancada** | Dados Externos | Fornece tabelas de arrasto (`CDpoweroff.csv`, `CDpoweron.csv`) e medições reais para o `modo="medido"`. |

---

### Próximo Nível
👉 Avance para [📦 C4 Nível 2 — Containers (Camadas e Pastas)](c2-containers.md) para ver como o repositório é dividido internamente.
