---
component_id: 1
component_name: Simulation and Modeling Domain Core
---

# Simulation and Modeling Domain Core

## Component Description

Core flight simulation, rocket assembly, motor calculations, and telemetry/inspection domain logic.

---

## Key References:

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/modelos.py (lines 98-228)
```
def build_rocket(
    foguete_spec: FogueteSpec,
    *,
    modo: ModoFoguete = "calculado",
    motor_spec: MotorSpec | None = None,
    componentes: Sequence[TuboSpec | MassaPontualSpec] | None = None,
    spec_coifa: CoifaSpec | None = None,
    spec_aleta: AletaSpec | None = None,
    tipo_aletas: str = "freeform",
    fator_empuxo: float = 1.0,
    fator_arrasto: float = 1.0,
) -> FogueteMontado:
    """Constrói o `FogueteMontado` no modo estrutural escolhido (`calculado` ou `medido`).

    Parameters
    ----------
    foguete_spec : FogueteSpec
        Especificação completa do foguete (ex.: `HEFESTO` de `configs`).
    modo : {"calculado", "medido"}
        - `"calculado"`: resolve massa, CG e inércia a partir de componentes, coifa e aletas.
        - `"medido"`: usa os valores medidos de bancada (`foguete_spec.geometria_medida`).
    motor_spec : MotorSpec | None
        Permite substituir o motor nominal (ex.: por uma variação) sem recriar `foguete_spec`.
    """
    if modo not in ("calculado", "medido"):
        raise ValueError(
            f"modo inválido: {modo!r}. Escolha explicitamente 'calculado' ou 'medido'."
        )

    motor_efetivo = motor_spec if motor_spec is not None else foguete_spec.motor
    motor, motor_d = build_motor(
        motor_spec=motor_efetivo,
        fator_empuxo=fator_empuxo,
        limites=foguete_spec.limites,
    )

    resolvido: FogueteResolvido | None = None

    if modo == "calculado":
        comp_eff = componentes if componentes is not None else foguete_spec.componentes
        coifa_eff = spec_coifa if spec_coifa is not None else foguete_spec.coifa
        aleta_eff = spec_aleta if spec_aleta is not None else foguete_spec.aleta

        if not comp_eff or coifa_eff is None or aleta_eff is None:
            raise ValueError(
                f"Foguete '{foguete_spec.nome}' não possui todos os insumos para "
                "modo='calculado' (componentes, coifa, aleta)."
            )

        resolvido = resolver(
            componentes=comp_eff,
            spec_aleta=aleta_eff,
            spec_coifa=coifa_eff,
            raio=foguete_spec.raio,
        )
        parametros_rocket = resolvido.dict_rocket(
            power_off_drag=str(foguete_spec.power_off_drag),
            power_on_drag=str(foguete_spec.power_on_drag),
        )
        nose_kwargs = resolvido.dict_coifa()
    else:
        geom = foguete_spec.geometria_medida
        if geom is None:
            raise ValueError(
                f"Foguete '{foguete_spec.nome}' não possui 'geometria_medida' configurada "
                "para modo='medido'."
            )
        parametros_rocket = geom.dict_rocket(
            power_off_drag=str(foguete_spec.power_off_drag),
            power_on_drag=str(foguete_spec.power_on_drag),
        )
        nose_kwargs = geom.dict_coifa()

    rkt = Rocket(**parametros_rocket)

    if fator_arrasto != 1.0:
        rkt.power_off_drag = rkt.power_off_drag * fator_arrasto
        rkt.power_on_drag = rkt.power_on_drag * fator_arrasto

    nosecone = rkt.add_nose(**nose_kwargs)

    if tipo_aletas == "freeform":
        if modo == "calculado" and resolvido is not None:
            aleta_eff = resolvido.spec_aleta
            fins = rkt.add_free_form_fins(
                n=aleta_eff.n,
                position=aleta_eff.position,
                shape_points=resolvido.shape_points(),
                cant_angle=aleta_eff.cant_angle,
            )
        else:
            geom = foguete_spec.geometria_medida
            assert geom is not None
            fins = rkt.add_free_form_fins(**geom.dict_aletas_freeform())
    elif tipo_aletas == "trapezio":
        geom = foguete_spec.geometria_medida
        if geom is not None and geom.aletas_trapezio_equiv is not None:
            fins = rkt.add_trapezoidal_fins(**geom.aletas_trapezio_equiv)
        elif foguete_spec.aleta is not None:
            a = foguete_spec.aleta
            fins = rkt.add_trapezoidal_fins(
                n=a.n,
                root_chord=a.root_chord,
                tip_chord=a.tip_chord,
                span=a.span_le,
                sweep_length=a.sweep_length,
                position=a.position,
                cant_angle=a.cant_angle,
            )
        else:
            raise ValueError("Sem dados de aleta trapezoidal disponíveis.")
    else:
        raise ValueError(f"tipo_aletas inválido: {tipo_aletas!r}. Use 'freeform' ou 'trapezio'.")

    rail_buttons = rkt.set_rail_buttons(**foguete_spec.rail_buttons)
    unreefed = rkt.add_parachute(**foguete_spec.unreefed)
    reefed = rkt.add_parachute(**foguete_spec.reefed)
    rkt.add_motor(motor, position=foguete_spec.motor_position)

    return FogueteMontado(
        rocket=rkt,
        motor=motor,
        motor_derivado=motor_d,
        modo=modo,
        foguete_resolvido=resolvido,
        nosecone=nosecone,
        fins=fins,
        rail_buttons=rail_buttons,
        unreefed=unreefed,
        reefed=reefed,
    )
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/ambiente.py (lines 23-36)
```
def build_irec() -> Environment:
    """Constrói o ambiente atmosférico nominal de Spaceport America (ERA5 Reanalysis)."""
    env = Environment(
        date=(2026, 6, 15, 12),
        latitude=32.94019,
        longitude=-106.92056,
        elevation=1401,
    )
    env.set_atmospheric_model(
        type="Reanalysis",
        file=str(ATMOSFERA / "irec" / "data_stream-oper_stepType-instant.nc"),
        dictionary=_DIC_NC,
    )
    return env
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/inspecao.py (lines 170-272)
```
def relatorio_estrutura(foguete: FogueteSpec) -> None:
    """Imprime o detalhamento estrutural (comparando modo calculado e modo medido)."""
    _titulo(f"ESTRUTURA — {foguete.nome.upper()}")
    _linha("raio externo", _fmt(foguete.raio * 1000, 1, "mm"))

    if foguete.componentes and foguete.aleta is not None and foguete.coifa is not None:
        r = resolver(
            componentes=foguete.componentes,
            spec_aleta=foguete.aleta,
            spec_coifa=foguete.coifa,
            raio=foguete.raio,
        )
        _sub("Modo Calculado (analítico por componentes)")
        _linha("massa seca", _fmt(r.massa_seca, 4, "kg"))
        _linha("CG sem motor", _fmt(r.cg_sem_motor, 4, "m"))
        _linha("I_11 = I_22 (pitch/yaw)", _fmt(r.inercia_transversal, 6, "kg·m²"))
        _linha("I_33 (roll)", _fmt(r.inercia_longitudinal, 6, "kg·m²"))
    else:
        r = None

    if foguete.geometria_medida is not None:
        gm = foguete.geometria_medida
        _sub("Modo Medido (bancada / OpenRocket)")
        _linha("massa seca", _fmt(gm.massa_seca, 4, "kg"))
        _linha("CG sem motor", _fmt(gm.cg_sem_motor, 4, "m"))
        _linha("I_11 = I_22 (pitch/yaw)", _fmt(gm.inercia_transversal, 6, "kg·m²"))
        _linha("I_33 (roll)", _fmt(gm.inercia_longitudinal, 6, "kg·m²"))

    if r is not None and foguete.coifa is not None and foguete.aleta is not None:
        comp_modulos = sum(
            c.comprimento for c in foguete.componentes if c.nome.startswith("Módulo")
        )
        fim_corpo = foguete.coifa.length + comp_modulos
        comp_total = max(fim_corpo, foguete.motor_position)

        _sub("Comprimentos")
        _linha("coifa", _fmt(foguete.coifa.length, 4, "m"))
        _linha("corpo (módulos)", _fmt(comp_modulos, 4, "m"))
        _linha("fim do corpo", _fmt(fim_corpo, 4, "m"))
        _linha("posição do motor (tubeira)", _fmt(foguete.motor_position, 4, "m"))
        _linha("COMPRIMENTO TOTAL", _fmt(comp_total, 4, "m"))

        _titulo("COMPONENTES (nariz → cauda)")
        print(
            f"  {'#':>2}  {'nome':<30} {'massa':>8} {'pos':>7} "
            f"{'L':>7} {'r_e':>7} {'r_i':>7}"
        )
        print(
            f"  {'-'*2}  {'-'*30} {'-'*8} {'-'*7} "
            f"{'-'*7} {'-'*7} {'-'*7}"
        )

        for i, (spec, deriv) in enumerate(zip(foguete.componentes, r.componentes)):
            if isinstance(spec, TuboSpec):
                re = spec.raio_externo * 1000
                ri = spec.raio_interno * 1000
                L = spec.comprimento
                print(
                    f"  {i:>2}  {spec.nome:<30} {deriv.massa:>8.4f} "
                    f"{spec.posicao:>7.4f} {L:>7.4f} {re:>7.1f} {ri:>7.1f}"
                )
            else:
                print(
                    f"  {i:>2}  {spec.nome:<30} {deriv.massa:>8.4f} "
                    f"{spec.posicao:>7.4f} {'—':>7} {'—':>7} {'—':>7}"
                )

        aleta_spec = foguete.aleta
        a = r.aleta
        _titulo("ALETAS")
        _linha("quantidade", aleta_spec.n)
        _linha("root_chord", _fmt(aleta_spec.root_chord, 4, "m"))
        _linha("tip_chord", _fmt(aleta_spec.tip_chord, 4, "m"))
        _linha("span_le", _fmt(aleta_spec.span_le, 4, "m"))
        _linha("span_te", _fmt(aleta_spec.span_te, 4, "m"))
        _linha("sweep_length", _fmt(aleta_spec.sweep_length, 4, "m"))
        _linha("espessura", _fmt(aleta_spec.thickness, 4, "m"))
        _linha("posição", _fmt(aleta_spec.position, 4, "m"))
        _linha("cant_angle", _fmt(aleta_spec.cant_angle, 2, "°"))

        _sub("Derivadas")
        _linha("área unitária", _fmt(a.area_planform, 6, "m²"))
        _linha("massa unitária", _fmt(a.massa_unitaria, 4, "kg"))
        _linha("massa total", _fmt(a.massa_total, 4, "kg"))
        _linha("CG axial", _fmt(a.X_cg_absoluto, 4, "m"))
        _linha("r_cg", _fmt(a.r_cg, 4, "m"))
        _linha("I_33 roll (todas)", _fmt(a.I_xx, 6, "kg·m²"))
        _linha("I_11/I_22 pitch local", _fmt(a.I_yy_local, 6, "kg·m²"))

        coifa_spec = foguete.coifa
        cf = r.coifa
        _titulo("COIFA")
        _linha("kind", coifa_spec.kind)
        _linha("comprimento", _fmt(coifa_spec.length, 4, "m"))
        _linha("espessura", _fmt(coifa_spec.thickness * 1000, 3, "mm"))
        _linha("ρ casca", _fmt(coifa_spec.densidade, 1, "kg/m³"))
        _linha("massa_extra", _fmt(coifa_spec.massa_extra, 4, "kg"))

        _sub("Derivadas")
        _linha("massa total", _fmt(cf.massa, 4, "kg"))
        _linha("CG", _fmt(cf.cg, 4, "m"))
        _linha("I_33 roll local", _fmt(cf.I_xx_local, 6, "kg·m²"))
        _linha("I_11/I_22 pitch local", _fmt(cf.I_yy_local, 6, "kg·m²"))
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/motor.py (lines 363-423)
```
def derivar_motor(
    spec: MotorSpec,
    *,
    limites: LimitesSeguranca = LIMITES_PADRAO,
) -> MotorDerivado:
    """Deriva cinemática, balística interna, massas, inércias e diagnósticos do motor."""
    info = _resolver_fonte_e_geometria(spec)

    grains_eff: tuple[GrainSpec, ...] = info["grains"]
    rho_eff: float = info["propellant_density"]

    prop_mass, prop_len, stack_len, cg_prop, inner_eff = _derivar_dos_graos(
        grains=grains_eff,
        propellant_density=rho_eff,
        grain_separation=spec.grain_separation,
        margin_forward_side=spec.margin_forward_side,
    )

    case_len, case_r_o, dry_mass = _derivar_carcaca(spec, stack_len)
    cg_dry = case_len / 2.0

    # Convenção RocketPy: (I_11, I_22, I_33) = (transversal, transversal, longitudinal)
    if spec.dry_inertia_override is not None:
        dry_inertia = spec.dry_inertia_override
    else:
        I_long, I_transv = _derivar_inercia_seca(
            dry_mass, case_r_o, spec.case_inner_radius, case_len,
        )
        dry_inertia = (I_transv, I_transv, I_long)

    diagnosticos = _diagnosticar(info, spec, limites)

    return MotorDerivado(
        nome=spec.nome,
        fonte=info["fonte"],
        burn_time=info["burn_time"],
        total_impulse=info["total_impulse"],
        max_thrust=info["max_thrust"],
        eng_propellant_mass=info["eng_propellant_mass"],
        curva_empuxo=info["curva_empuxo"],
        p0_pico=info["p0_pico"],
        kn_pico=info["kn_pico"],
        mass_flux_pico=info["mass_flux_pico"],
        isp_entregue=info["isp_entregue"],
        grains=grains_eff,
        propellant_density=rho_eff,
        throat_radius=info["throat_radius"],
        nozzle_exit_radius=info["nozzle_exit_radius"],
        propellant_mass=prop_mass,
        propellant_length=prop_len,
        stack_length=stack_len,
        cg_propellant=cg_prop,
        grain_inner_radius_effective=inner_eff,
        case_length=case_len,
        case_outer_radius=case_r_o,
        dry_mass=dry_mass,
        cg_dry=cg_dry,
        dry_inertia=dry_inertia,
        mass_loaded=dry_mass + prop_mass,
        diagnosticos=diagnosticos,
    )
```


## Source Files:

- `src/ambiente.py`
- `src/c4_gerador.py`
- `src/calculos/aletas.py`
- `src/calculos/aletas_rasaero.py`
- `src/calculos/coifa.py`
- `src/calculos/componentes.py`
- `src/calculos/motor.py`
- `src/calculos/motorlib_variacoes.py`
- `src/calculos/motorlib_wrapper.py`
- `src/calculos/seguranca.py`
- `src/inspecao.py`
- `src/modelo.py`
- `src/modelos.py`
- `src/smoke.py`
- `src/specs.py`
- `src/viz.py`

