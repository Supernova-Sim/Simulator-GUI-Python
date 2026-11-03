# 🧩 C4 Nível 3 (Componentes) — Subsistema de Motor & Segurança

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](c1-contexto.md) · [📦 Nível 2: Containers](c2-containers.md) · [🧩 C3: Execução & Voo](c3-execucao-voo.md) · **🧩 C3: Subsistema de Motor**

---

## 1. Arquitetura Interna do Módulo Profundo de Motor

O subsistema de motor foi desenhado como um **Módulo Profundo (Deep Module)**: o chamador entrega apenas um `MotorSpec` declarativo para `derivar_motor(spec)` e recebe um `MotorDerivado` completo, com a garantia de que **qualquer `override` aplicado ao `.ric` atualiza simultaneamente a curva balística e a geometria dos grãos/tubeira**.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    classDef spec fill:#1e1e38,stroke:#818cf8,stroke-width:2px,color:#f8fafc;
    classDef seam fill:#2a1b18,stroke:#f97316,stroke-width:2px,color:#f8fafc;
    classDef calc fill:#052e16,stroke:#22c55e,stroke-width:2px,color:#f8fafc;
    classDef out fill:#361a29,stroke:#ec4899,stroke-width:2px,color:#f8fafc;

    subgraph ENTRADA["1. Especificação Declarativa"]
        S1["MotorSpec\n(configs/foguetes/hefesto/motor.py)"]:::spec
        S2["Presets / Variações\n(configs/foguetes/hefesto/motor_variacoes.py)"]:::spec
        S2 -->|"dataclasses.replace(overrides=...)"| S1
    end

    subgraph COSTURA["2. Costura OpenMotor (src/calculos/motorlib_*.py)"]
        W1["motorlib_wrapper.carregar_props(ric_path)\nLê .ric isolando side-effects do uilib.logger"]:::seam
        W2["motorlib_variacoes.aplicar_overrides(props, overrides)\nValida whitelist e muta props em memória"]:::seam
        W3["motorlib_wrapper.extrair_geometria_props(props)\nExtrai GrainSpec[], densidade, garganta e saída"]:::seam
        W4["motorlib_wrapper.simular_props(props)\nExecuta solver balístico BATES -> F(t), P0, Kn, mflux"]:::seam

        W1 --> W2 --> W3 & W4
    end

    subgraph FISICA["3. Física Estrutural & Segurança (src/calculos/)"]
        G1["motor._derivar_dos_graos()\nMassa propelente, CG local e r_i efetivo"]:::calc
        G2["motor._derivar_carcaca() & _derivar_inercia_seca()\nTensor RocketPy (I_t, I_t, I_l)"]:::calc
        G3["seguranca.py\nfs_carcaca (Barlow/Lamé), check_p0, check_kn, check_mass_flux"]:::calc

        W3 --> G1 --> G2
        W4 --> G3
    end

    subgraph SAIDA["4. Contrato de Saída"]
        MD["MotorDerivado\nObjeto imutável pronto para RocketPy e inspeção"]:::out
        G1 & G2 & G3 & W4 --> MD
    end

    S1 --> W1
    click W1 href "_gerados_c4/src__calculos__motorlib_wrapper.c4.md" "Abrir C4 de motorlib_wrapper.py"
    click W2 href "_gerados_c4/src__calculos__motorlib_variacoes.c4.md" "Abrir C4 de motorlib_variacoes.py"
    click G1 href "_gerados_c4/src__calculos__motor.c4.md" "Abrir C4 de motor.py"
    click G3 href "_gerados_c4/src__calculos__seguranca.c4.md" "Abrir C4 de seguranca.py"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 2. Componentes do Subsistema

| Componente | Arquivo | Responsabilidade |
| :--- | :--- | :--- |
| **Fachada Profunda** | [`src/calculos/motor.py`](../../src/calculos/motor.py) | Coordena a derivação completa (`.ric` ou fallback `.eng`) e produz `MotorDerivado`. |
| **Costura OpenMotor** | [`src/calculos/motorlib_wrapper.py`](../../src/calculos/motorlib_wrapper.py) | Encapsula `motorlib`/`uilib`, silencia logs intrusivos e extrai geometria/balística de `props`. |
| **Mutador de Overrides** | [`src/calculos/motorlib_variacoes.py`](../../src/calculos/motorlib_variacoes.py) | Aplica alterações via dot-path (`grains.*.properties.coreDiameter`, `nozzle.throat`) com whitelist. |
| **Verificador de Segurança** | [`src/calculos/seguranca.py`](../../src/calculos/seguranca.py) | Calcula tensão circunferencial na carcaça ($\text{FS} \ge 2.0$), $P_0 \le 8\text{ MPa}$, $K_n \le 250$ e fluxo de massa. |
