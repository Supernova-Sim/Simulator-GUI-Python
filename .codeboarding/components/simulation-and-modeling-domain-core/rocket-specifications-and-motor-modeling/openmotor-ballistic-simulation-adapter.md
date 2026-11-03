---
component_id: 1.1.3
component_name: OpenMotor Ballistic Simulation Adapter
---

# OpenMotor Ballistic Simulation Adapter

## Component Description

Adapts OpenMotor simulation runs, reads .ric configuration properties, and applies simulation parameter overrides.

---

## Key References:

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/motorlib_variacoes.py (lines 107-119)
```
def aplicar_overrides(
    props: dict,
    overrides: dict[str, Any],
) -> dict:
    """Retorna uma cópia profunda de `props` com `overrides` aplicados."""
    copia = copy.deepcopy(props)
    chaves_ordenadas = sorted(
        overrides.keys(),
        key=lambda k: (1 if _tem_indice_especifico(k) else 0),
    )
    for chave in chaves_ordenadas:
        _set_path(copia, chave.split("."), overrides[chave])
    return copia
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/motorlib_wrapper.py (lines 79-136)
```
class MotorResultado:
    """Resultado da simulação balística interna do OpenMotor."""
    success: bool
    alerts: list
    nome: str
    burn_time: float                # s

    # ---------- Séries 1D ----------
    tempo: list[float]              # s
    empuxo: list[float]             # N
    pressao: list[float]            # Pa — câmara
    pressao_saida: list[float]      # Pa — saída da tubeira
    kn: list[float]                 # razão Ab/At
    volume_loading: list[float]     # %
    d_throat: list[float]           # m — erosão da garganta

    # ---------- Séries 2D (tempo × grão) ----------
    massa_por_grao: list[list[float]]       # kg
    mass_flow_por_grao: list[list[float]]   # kg/s
    mass_flux_por_grao: list[list[float]]   # kg/(m²·s)
    regression_por_grao: list[list[float]]  # m
    web_por_grao: list[list[float]]         # m
    mach_por_grao: list[list[float]]        # —

    # ---------- Escalares ----------
    p0_pico: float                  # Pa
    kn_pico: float
    mass_flux_pico: float           # kg/(m²·s) — pior caso entre todos os grãos
    empuxo_max: float               # N
    empuxo_medio: float             # N
    impulso_total: float            # N·s
    isp_entregue: float             # s
    massa_propelente_inicial: float # kg — soma de todos os grãos em t=0
    massa_propelente_final: float   # kg — soma de todos os grãos em t=final
    n_graos: int

    @property
    def curva_empuxo(self) -> list[tuple[float, float]]:
        """[(t, F), ...] em s e N — pronta para o RocketPy."""
        return list(zip(self.tempo, self.empuxo))

    def resumo(self) -> str:
        return "\n".join([
            f"Motor: {self.nome}",
            f"  success:             {self.success}",
            f"  alerts:              {len(self.alerts)}",
            f"  n_graos:             {self.n_graos}",
            f"  burn_time:           {self.burn_time:.3f} s",
            f"  impulse_total:       {self.impulso_total:.1f} N·s",
            f"  thrust_max:          {self.empuxo_max:.1f} N",
            f"  thrust_avg:          {self.empuxo_medio:.1f} N",
            f"  ISP_entregue:        {self.isp_entregue:.2f} s",
            f"  P0_pico:             {self.p0_pico / 1e6:.3f} MPa",
            f"  Kn_pico:             {self.kn_pico:.1f}",
            f"  mass_flux_pico:      {self.mass_flux_pico:.3f} kg/(m²·s)",
            f"  propellant_inicial:  {self.massa_propelente_inicial:.4f} kg",
            f"  propellant_final:    {self.massa_propelente_final:.4f} kg",
        ])
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/motorlib_wrapper.py (lines 142-147)
```
def carregar_props(ric_path: str | Path) -> dict:
    """Carrega o dicionário de propriedades de um arquivo .ric (já migrado pelo uilib)."""
    ric_path = Path(ric_path)
    if not ric_path.exists():
        raise FileNotFoundError(f"Arquivo .ric não encontrado: {ric_path}")
    return loadFile(str(ric_path), fileTypes.MOTOR)
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/motorlib_wrapper.py (lines 150-195)
```
def extrair_geometria_props(
    props: dict,
) -> tuple[tuple[GrainSpec, ...], float, float, float]:
    """Extrai (grains, propellant_density, throat_radius, nozzle_exit_radius) de `props`.

    Como opera diretamente sobre o dicionário `props` (antes ou depois de
    `aplicar_overrides`), garante que qualquer override em grãos, propelente
    ou tubeira reflita fielmente nas especificações geométricas do motor.
    """
    grains_raw = props.get("grains")
    if not grains_raw:
        raise KeyError("Dicionário 'props' do .ric não contém a lista 'grains'.")

    grains: list[GrainSpec] = []
    for i, g in enumerate(grains_raw):
        p = g.get("properties", {})
        try:
            length = float(p["length"])
            diameter = float(p["diameter"])
            core_diameter = float(p.get("coreDiameter", p.get("core_diameter")))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Propriedades inválidas no grão [{i}] do .ric: {p}"
            ) from exc

        grains.append(
            GrainSpec(
                length=length,
                outer_radius=diameter / 2.0,
                inner_radius=core_diameter / 2.0,
            )
        )

    prop = props.get("propellant", {})
    propellant_density = float(prop["density"])

    nozzle = props.get("nozzle", {})
    throat_diameter = float(nozzle.get("throat", nozzle.get("throatDiameter")))
    exit_diameter = float(nozzle.get("exit", nozzle.get("exitDiameter")))

    return (
        tuple(grains),
        propellant_density,
        throat_diameter / 2.0,
        exit_diameter / 2.0,
    )
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/motorlib_wrapper.py (lines 198-277)
```
def simular_props(props: dict, *, nome: str | None = None) -> MotorResultado:
    """Roda o solver do OpenMotor sobre um dicionário `props` em memória."""
    motor = Motor(copy.deepcopy(props))
    sim = motor.runSimulation()

    if not sim.success:
        raise RuntimeError(
            f"Simulação do OpenMotor falhou para '{nome or 'Motor'}'. Alertas: "
            f"{[getattr(a, 'message', str(a)) for a in sim.alerts]}"
        )

    ch = sim.channels

    # --- 1D ---
    tempo = _as_1d(ch["time"].getData())
    empuxo = _as_1d(ch["force"].getData())
    pressao = _as_1d(ch["pressure"].getData())
    pressao_saida = _as_1d(ch["exitPressure"].getData())
    kn = _as_1d(ch["kn"].getData())
    vol_loading = _as_1d(ch["volumeLoading"].getData())
    d_throat = _as_1d(ch["dThroat"].getData())

    # --- 2D ---
    massa_por_grao = _as_2d(ch["mass"].getData())
    mass_flow_por_grao = _as_2d(ch["massFlow"].getData())
    mass_flux_por_grao = _as_2d(ch["massFlux"].getData())
    regression_por_grao = _as_2d(ch["regression"].getData())
    web_por_grao = _as_2d(ch["web"].getData())
    mach_por_grao = _as_2d(ch["machNumber"].getData())

    # --- Escalares ---
    impulso = _integrar_trapezio(tempo, empuxo)
    burn_time = tempo[-1] - tempo[0] if len(tempo) > 1 else 0.0
    empuxo_medio = impulso / burn_time if burn_time > 0 else 0.0

    massa_total_inicial = sum(massa_por_grao[0])
    massa_total_final = sum(massa_por_grao[-1])

    if nome is not None:
        nome_final = nome
    else:
        try:
            nome_final = sim.getDesignation()
        except (AttributeError, TypeError, ValueError, ZeroDivisionError):
            nome_final = "Motor (via .ric)"

    try:
        isp = float(sim.getISP())
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        isp = float("nan")

    return MotorResultado(
        success=sim.success,
        alerts=list(sim.alerts),
        nome=nome_final,
        burn_time=burn_time,
        tempo=tempo,
        empuxo=empuxo,
        pressao=pressao,
        pressao_saida=pressao_saida,
        kn=kn,
        volume_loading=vol_loading,
        d_throat=d_throat,
        massa_por_grao=massa_por_grao,
        mass_flow_por_grao=mass_flow_por_grao,
        mass_flux_por_grao=mass_flux_por_grao,
        regression_por_grao=regression_por_grao,
        web_por_grao=web_por_grao,
        mach_por_grao=mach_por_grao,
        p0_pico=max(pressao),
        kn_pico=max(kn),
        mass_flux_pico=_pico_2d(mass_flux_por_grao),
        empuxo_max=max(empuxo),
        empuxo_medio=empuxo_medio,
        impulso_total=impulso,
        isp_entregue=isp,
        massa_propelente_inicial=massa_total_inicial,
        massa_propelente_final=massa_total_final,
        n_graos=len(massa_por_grao[0]),
    )
```


## Source Files:

- `src/calculos/motorlib_variacoes.py`
- `src/calculos/motorlib_wrapper.py`

