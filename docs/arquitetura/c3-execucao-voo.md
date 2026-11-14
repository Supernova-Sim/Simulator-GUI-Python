# 🧩 C4 Nível 3 (Componentes) — Pipeline de Execução e Voo

**Navegação na Hierarquia C4:**
[🌐 Nível 1: Contexto](c1-contexto.md) · [📦 Nível 2: Containers](c2-containers.md) · **🧩 C3: Execução & Voo** · [🧩 C3: Subsistema de Motor](c3-subsistema-motor.md)

---

## 1. Como os Componentes Conversam em uma Simulação

Este diagrama mostra o fluxo completo quando você executa `cmd_sim()` no console do Positron ou `python centralControle/rodar.py sim` no terminal.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#38bdf8' }}}%%
flowchart TD
    classDef entrada fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef configs fill:#1e1e38,stroke:#818cf8,stroke-width:1.5px,color:#f8fafc;
    classDef motor fill:#2a1b18,stroke:#f97316,stroke-width:1.5px,color:#f8fafc;
    classDef estrutura fill:#052e16,stroke:#22c55e,stroke-width:1.5px,color:#f8fafc;
    classDef voo fill:#172554,stroke:#60a5fa,stroke-width:1.5px,color:#f8fafc;

    subgraph S1["1. Despacho (centralControle/rodar.py)"]
        E1["Console: cmd_sim('calculado')\nou CLI: rodar.py sim"]:::entrada
        R1["_resolver_motor(motor)\nResolve preset de configs/foguetes/hefesto/motor.py"]:::configs
        E1 --> R1
    end

    subgraph S2["2. Orquestrador (scripts/sim_deterministica.py)"]
        D2["main(motor=motor_spec)\nChama build_rocket(HEFESTO, modo=...)"]:::configs
    end

    subgraph S3["3. Derivação do Motor (src/motor/derivador.py)"]
        M1["derivar_motor(motor_spec)\nRetorna MotorDerivado (curva F(t), grãos, inércia, FS)"]:::motor
    end

    subgraph S4["4. Montagem do Foguete (src/simulacao/construtor_foguete.py : build_rocket)"]
        MODO{"modo?"}:::estrutura

        CALC["modo='calculado'\nsrc/estrutura/agregador.py : resolver()\nIntegra TuboSpec + MassaPontualSpec + CoifaSpec + AletaSpec"]:::estrutura
        MED["modo='medido'\nGeometriaMedidaSpec\nUsa massa/CG/inércia de bancada"]:::estrutura

        TENSOR["Convenção de Inércia RocketPy:\n(I_11, I_22, I_33) = (I_transversal, I_transversal, I_longitudinal)"]:::estrutura
        ROK["Objeto FogueteMontado\n(Rocket + SolidMotor + MotorDerivado)"]:::estrutura

        MODO -->|"calculado"| CALC --> TENSOR --> ROK
        MODO -->|"medido"| MED --> TENSOR --> ROK
    end

    subgraph S5["5. Simulação 6-DOF e Persistência"]
        ENV["src/simulacao/ambiente.py : build_irec()\nSpaceport America (elev. 1401 m)"]:::voo
        FLIGHT["rocketpy.Flight(rocket, env, **IREC)\nRampa 6 m a 71°"]:::voo
        OUT["Imprime Apogeu AGL + Margem de Estabilidade\ne salva data/saida/sim_*.json"]:::voo

        ENV & ROK --> FLIGHT --> OUT
    end

    R1 --> D2
    D2 --> M1 & MODO
    M1 --> ROK
    click E1 href "_gerados_c4/centralControle__rodar.c4.md" "Abrir C4 de rodar.py"
    click M1 href "_gerados_c4/src__motor__derivador.c4.md" "Abrir C4 de derivador.py"
    click CALC href "_gerados_c4/src__estrutura__agregador.c4.md" "Abrir C4 de agregador.py"
    click ENV href "_gerados_c4/src__simulacao__ambiente.c4.md" "Abrir C4 de ambiente.py"
    linkStyle default stroke:#38bdf8,stroke-width:2px;
```

---

## 2. Componentes Envolvidos (Clique para abrir o código ou gere o Nível 4 pelo botão no topo)

| Componente | Arquivo | Papel |
| :--- | :--- | :--- |
| **CLI / Dispatcher** | [`centralControle/rodar.py`](../../centralControle/rodar.py) | Ponto de entrada unificado para CLI e console interativo. |
| **Orquestrador de Voo** | [`scripts/sim_deterministica.py`](../../scripts/sim_deterministica.py) | Executa o voo nominal e serializa o resultado em JSON. |
| **Construtor RocketPy** | [`src/simulacao/construtor_foguete.py`](../../src/simulacao/construtor_foguete.py) | Monta `SolidMotor` e `Rocket` nos modos `"calculado"` ou `"medido"`. |
| **Agregador Estrutural** | [`src/estrutura/agregador.py`](../../src/estrutura/agregador.py) | Aplica o teorema de Steiner (eixos paralelos) sobre todos os componentes secos. |
| **Ambiente ERA5** | [`src/simulacao/ambiente.py`](../../src/simulacao/ambiente.py) | Fábricas de `Environment` (Reanalysis e Ensemble) para Spaceport America. |
| **Relatórios & Inspeção** | [`src/relatorios.py`](../../src/relatorios.py) | Formata tabelas comparativas (`calculado` vs `medido`, motor e segurança). |
