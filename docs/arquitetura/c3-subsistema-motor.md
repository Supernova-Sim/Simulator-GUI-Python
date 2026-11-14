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
        S1["MotorSpec & VARIACOES\n(configs/foguetes/hefesto/motor.py)"]:::spec
        S2["validar_overrides()\n(src/especificacoes.py)"]:::spec
        S2 -->|"dataclasses.replace(overrides=...)"| S1
    end

    subgraph ADAPTADOR["2. Adaptador OpenMotor (src/motor/adaptador_openmotor.py)"]
        W1["executar_ric(ric_path, overrides)\nCarrega .ric isolando logger do uilib,\naplica overrides dot-path/wildcard em memória,\nextrai GrainSpec[] e executa o solver BATES -> ResultadoRic"]:::seam
    end

    subgraph FISICA["3. Derivação & Segurança (src/motor/)"]
        G1["derivador._derivar_dos_graos()\nMassa propelente, CG local e r_i efetivo"]:::calc
        G2["derivador._derivar_carcaca() & _derivar_inercia_seca()\nTensor RocketPy (I_t, I_t, I_l)"]:::calc
        G3["seguranca.py\nfs_carcaca (Barlow/Lamé), check_p0, check_kn, check_mass_flux"]:::calc

        W1 --> G1 --> G2
        W1 --> G3
    end

    subgraph SAIDA["4. Contrato de Saída"]
        MD["MotorDerivado\nObjeto imutável pronto para RocketPy e inspeção"]:::out
        G1 & G2 & G3 & W1 --> MD
    end

    S1 --> W1
    click S2 href "_gerados_c4/src__especificacoes.c4.md" "Abrir C4 de especificacoes.py"
    click W1 href "_gerados_c4/src__motor__adaptador_openmotor.c4.md" "Abrir C4 de adaptador_openmotor.py"
    click G1 href "_gerados_c4/src__motor__derivador.c4.md" "Abrir C4 de derivador.py"
    click G3 href "_gerados_c4/src__motor__seguranca.c4.md" "Abrir C4 de seguranca.py"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 2. Componentes do Subsistema

| Componente | Arquivo | Responsabilidade |
| :--- | :--- | :--- |
| **Configuração & Presets** | [`configs/foguetes/hefesto/motor.py`](../../configs/foguetes/hefesto/motor.py) | Define `MOTOR_IREC`, `PARAMS_LIVRES`, `criar_variacao()` e o mapa `VARIACOES`. |
| **Contratos & Whitelist** | [`src/especificacoes.py`](../../src/especificacoes.py) | Define `MotorSpec`, `LimitesSeguranca`, `LIMITES_PADRAO` e `validar_overrides()`. |
| **Fachada Profunda** | [`src/motor/derivador.py`](../../src/motor/derivador.py) | Coordena a derivação completa (`.ric` ou fallback `.eng`) e produz `MotorDerivado`. |
| **Adaptador OpenMotor** | [`src/motor/adaptador_openmotor.py`](../../src/motor/adaptador_openmotor.py) | Encapsula `motorlib`/`uilib`, aplica overrides e retorna `ResultadoRic` via `executar_ric()`. |
| **Verificador de Segurança** | [`src/motor/seguranca.py`](../../src/motor/seguranca.py) | Calcula tensão circunferencial na carcaça ($\text{FS} \ge 2.0$), $P_0 \le 8\text{ MPa}$, $K_n \le 250$ e fluxo de massa. |
