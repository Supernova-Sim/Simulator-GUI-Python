---
component_id: 1.1.1
component_name: Motor Derivation and Structural Inspection
---

# Motor Derivation and Structural Inspection

## Component Description

Calculates motor ballistic properties, structural dry mass, safety margins, and structural inspection reports.

---

## Key References:

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/motor.py (lines 103-198)
```
class MotorDerivado:
    nome: str
    fonte: str                          # "ric" ou "eng"

    # ---------- Cinemática (de .ric ou .eng) ----------
    burn_time: tuple[float, float]
    total_impulse: float
    max_thrust: float
    eng_propellant_mass: float          # massa declarada pela fonte (cross-check)

    # ---------- Curva (só se fonte=ric) ----------
    curva_empuxo: tuple[tuple[float, float], ...] | None

    # ---------- Balística interna (só se fonte=ric) ----------
    p0_pico: float | None
    kn_pico: float | None
    mass_flux_pico: float | None
    isp_entregue: float | None

    # ---------- Geometria efetiva resolvida (já pós-overrides) ----------
    grains: tuple[GrainSpec, ...]
    propellant_density: float
    throat_radius: float
    nozzle_exit_radius: float

    # ---------- Propriedades derivadas dos grãos ----------
    propellant_mass: float
    propellant_length: float
    stack_length: float
    cg_propellant: float
    grain_inner_radius_effective: float

    # ---------- Carcaça ----------
    case_length: float
    case_outer_radius: float
    dry_mass: float
    cg_dry: float

    # ---------- Inércia seca ----------
    # Convenção RocketPy: (I_11, I_22, I_33) = (transversal, transversal, longitudinal)
    dry_inertia: tuple[float, float, float]

    # ---------- Agregados ----------
    mass_loaded: float                  # kg — dry_mass + propellant_mass

    # ---------- Fatores de segurança ----------
    diagnosticos: tuple[DiagnosticoFS, ...]

    @property
    def inercia_transversal(self) -> float:
        return self.dry_inertia[0]

    @property
    def inercia_longitudinal(self) -> float:
        return self.dry_inertia[2]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nome": self.nome,
            "fonte": self.fonte,
            "burn_time": list(self.burn_time),
            "total_impulse": self.total_impulse,
            "max_thrust": self.max_thrust,
            "eng_propellant_mass": self.eng_propellant_mass,
            "p0_pico": self.p0_pico,
            "kn_pico": self.kn_pico,
            "mass_flux_pico": self.mass_flux_pico,
            "isp_entregue": self.isp_entregue,
            "grains": [g.to_dict() for g in self.grains],
            "propellant_density": self.propellant_density,
            "throat_radius": self.throat_radius,
            "nozzle_exit_radius": self.nozzle_exit_radius,
            "propellant_mass": self.propellant_mass,
            "propellant_length": self.propellant_length,
            "stack_length": self.stack_length,
            "cg_propellant": self.cg_propellant,
            "grain_inner_radius_effective": self.grain_inner_radius_effective,
            "case_length": self.case_length,
            "case_outer_radius": self.case_outer_radius,
            "dry_mass": self.dry_mass,
            "cg_dry": self.cg_dry,
            "dry_inertia": list(self.dry_inertia),
            "mass_loaded": self.mass_loaded,
            "diagnosticos": [
                {
                    "nome": x.nome,
                    "valor": x.valor,
                    "limite_min": x.limite_min,
                    "limite_max": x.limite_max,
                    "unidade": x.unidade,
                    "ok": x.ok,
                    "detalhe": x.detalhe,
                }
                for x in self.diagnosticos
            ],
        }
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

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/inspecao.py (lines 45-112)
```
def relatorio_motor(
    spec: MotorSpec,
    *,
    derivado: MotorDerivado | None = None,
) -> MotorDerivado:
    """Imprime especificação, propriedades derivadas e balística interna do motor."""
    d = derivado if derivado is not None else derivar_motor(spec)

    _titulo("MOTOR — SPEC & GEOMETRIA EFETIVA")
    _linha("nome", spec.nome)
    _linha("fonte", d.fonte)
    _linha("ric_path", spec.ric_path or "—")
    _linha("thrust_curve", spec.thrust_curve_path or "—")
    if spec.overrides:
        _linha("overrides ativos", f"{len(spec.overrides)} parâmetro(s)")

    _sub(f"Grãos efetivos ({len(d.grains)})")
    for i, g in enumerate(d.grains):
        print(
            f"  [{i}]  L={g.length:.4f} m   "
            f"r_o={g.outer_radius:.5f} m   "
            f"r_i={g.inner_radius:.5f} m"
        )
    _linha("separação", _fmt(spec.grain_separation * 1000, 1, "mm"))
    _linha("ρ propelente", _fmt(d.propellant_density, 1, "kg/m³"))

    _sub("Carcaça")
    _linha("raio interno", _fmt(spec.case_inner_radius * 1000, 3, "mm"))
    _linha("espessura parede", _fmt(spec.case_wall_thickness * 1000, 3, "mm"))
    _linha("ρ carcaça", _fmt(spec.case_density, 1, "kg/m³"))
    _linha("comprimento", _fmt(d.case_length, 4, "m"))
    _linha("massa seca", _fmt(d.dry_mass, 4, "kg"))

    _sub("Tubeira")
    _linha("posição", _fmt(spec.nozzle_position * 1000, 2, "mm"))
    _linha("r de saída", _fmt(d.nozzle_exit_radius * 1000, 2, "mm"))
    _linha("r da garganta", _fmt(d.throat_radius * 1000, 2, "mm"))

    _titulo("MOTOR — DERIVADO")
    _sub("Cinemática")
    _linha("burn_time", f"{d.burn_time[0]:.3f} → {d.burn_time[1]:.3f} s")
    _linha("impulso total", _fmt(d.total_impulse, 1, "N·s"))
    _linha("empuxo máximo", _fmt(d.max_thrust, 1, "N"))
    dur = d.burn_time[1] - d.burn_time[0]
    _linha("empuxo médio", _fmt(d.total_impulse / dur, 1, "N") if dur else "—")
    _linha("ISP entregue", _fmt(d.isp_entregue, 2, "s"))

    _sub("Geometria / Massas")
    _linha("massa propelente", _fmt(d.propellant_mass, 4, "kg"))
    _linha("comprimento propelente", _fmt(d.propellant_length, 4, "m"))
    _linha("stack length", _fmt(d.stack_length, 4, "m"))
    _linha("CG do propelente (local)", _fmt(d.cg_propellant, 4, "m"))
    _linha("r_i efetivo", _fmt(d.grain_inner_radius_effective * 1000, 3, "mm"))
    _linha("massa seca", _fmt(d.dry_mass, 4, "kg"))
    _linha("massa carregada", _fmt(d.mass_loaded, 4, "kg"))

    _sub("Inércia seca — Convenção RocketPy (I_11, I_22, I_33)")
    _linha("I_11 (pitch/transversal)", _fmt(d.dry_inertia[0], 6, "kg·m²"))
    _linha("I_22 (yaw/transversal)", _fmt(d.dry_inertia[1], 6, "kg·m²"))
    _linha("I_33 (roll/longitudinal)", _fmt(d.dry_inertia[2], 6, "kg·m²"))

    if d.p0_pico is not None:
        _sub("Balística interna")
        _linha("P0 de pico", _fmt(d.p0_pico / 1e6, 3, "MPa"))
        _linha("Kn de pico", _fmt(d.kn_pico, 1))
        _linha("mass flux de pico", _fmt(d.mass_flux_pico, 3, "kg/(m²·s)"))

    return d
```


## Source Files:

- `src/calculos/motor.py`
- `src/calculos/seguranca.py`
- `src/inspecao.py`

