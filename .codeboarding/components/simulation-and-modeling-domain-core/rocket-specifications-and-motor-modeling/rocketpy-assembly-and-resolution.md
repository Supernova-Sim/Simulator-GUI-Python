---
component_id: 1.1.2
component_name: RocketPy Assembly and Resolution
---

# RocketPy Assembly and Resolution

## Component Description

Aggregates mass and inertia properties into analytical models and constructs RocketPy rocket and motor instances.

---

## Key References:

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/modelo.py (lines 21-102)
```
class FogueteResolvido:
    """Parâmetros estruturais resolvidos analiticamente (`modo='calculado'`)."""
    componentes: list[ComponenteDerivado]
    spec_aleta: AletaSpec
    aleta: AletaDerivada
    spec_coifa: CoifaSpec
    coifa: CoifaDerivada
    raio: float               # m — raio externo do corpo do foguete

    @property
    def massa_seca(self) -> float:
        m_comp = sum(c.massa for c in self.componentes)
        return m_comp + self.coifa.massa + self.aleta.massa_total

    @property
    def cg_sem_motor(self) -> float:
        partes = (
            [(c.massa, c.posicao) for c in self.componentes]
            + [(self.coifa.massa, self.coifa.cg)]
            + [(self.aleta.massa_total, self.aleta.X_cg_absoluto)]
        )
        m_total = sum(m for m, _ in partes)
        momento = sum(m * x for m, x in partes)
        return momento / m_total

    @property
    def inercia_longitudinal(self) -> float:
        """Momento de inércia axial / roll (eixo de simetria e_3 do RocketPy)."""
        I_comp = sum(c.I_xx_local for c in self.componentes)
        return I_comp + self.coifa.I_xx_local + self.aleta.I_xx

    @property
    def inercia_transversal(self) -> float:
        """Momento de inércia transversal / pitch-yaw (eixos e_1 e e_2 do RocketPy)."""
        cg = self.cg_sem_motor

        I_comp = sum(
            c.I_yy_local + c.massa * (c.posicao - cg) ** 2
            for c in self.componentes
        )

        dx_coifa = self.coifa.cg - cg
        I_coifa = self.coifa.I_yy_local + self.coifa.massa * dx_coifa**2

        dx_aleta = self.aleta.X_cg_absoluto - cg
        I_aleta = self.aleta.I_yy_local + self.aleta.massa_total * dx_aleta**2

        return I_comp + I_coifa + I_aleta

    @property
    def inercia_rocketpy(self) -> tuple[float, float, float]:
        """Convenção RocketPy: (I_11, I_22, I_33) = (transversal, transversal, longitudinal)."""
        I_t = self.inercia_transversal
        I_l = self.inercia_longitudinal
        return (I_t, I_t, I_l)

    def dict_rocket(self, power_off_drag: str, power_on_drag: str) -> dict[str, Any]:
        return {
            "radius": self.raio,
            "mass": self.massa_seca,
            "inertia": self.inercia_rocketpy,
            "center_of_mass_without_motor": self.cg_sem_motor,
            "coordinate_system_orientation": "nose_to_tail",
            "power_off_drag": str(power_off_drag),
            "power_on_drag": str(power_on_drag),
        }

    def dict_coifa(self) -> dict[str, Any]:
        return {
            "length": self.spec_coifa.length,
            "kind": self.spec_coifa.kind,
            "position": self.spec_coifa.position,
        }

    def shape_points(self) -> list[tuple[float, float]]:
        s = self.spec_aleta
        return [
            (0.0, 0.0),
            (s.sweep_length, s.span_le),
            (s.sweep_length + s.tip_chord, s.span_te),
            (s.root_chord, 0.0),
        ]
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/modelo.py (lines 105-122)
```
def resolver(
    componentes: Sequence[TuboSpec | MassaPontualSpec],
    spec_aleta: AletaSpec,
    spec_coifa: CoifaSpec,
    raio: float,
) -> FogueteResolvido:
    """Combina componentes + coifa + aleta num `FogueteResolvido`."""
    derivados = derivar_todos(componentes)
    aleta = calcular_aleta(spec_aleta, r_rocket=raio)
    coifa = calcular_coifa(spec_coifa, raio_base=raio)
    return FogueteResolvido(
        componentes=derivados,
        spec_aleta=spec_aleta,
        aleta=aleta,
        spec_coifa=spec_coifa,
        coifa=coifa,
        raio=raio,
    )
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/modelos.py (lines 35-45)
```
class FogueteMontado:
    rocket: Rocket
    motor: SolidMotor
    motor_derivado: MotorDerivado
    modo: ModoFoguete
    foguete_resolvido: FogueteResolvido | None
    nosecone: object
    fins: object
    rail_buttons: object
    unreefed: object
    reefed: object
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/modelos.py (lines 81-95)
```
def build_motor(
    motor_spec: MotorSpec,
    fator_empuxo: float = 1.0,
    *,
    limites: LimitesSeguranca = LIMITES_PADRAO,
) -> tuple[SolidMotor, MotorDerivado]:
    """Constrói o `SolidMotor` e o `MotorDerivado` a partir de um `MotorSpec`."""
    d = derivar_motor(motor_spec, limites=limites)
    kwargs = _motor_kwargs(motor_spec, d)

    if fator_empuxo != 1.0:
        base = SolidMotor(**kwargs)
        kwargs["thrust_source"] = base.thrust * fator_empuxo

    return SolidMotor(**kwargs), d
```

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


## Source Files:

- `src/modelo.py`
- `src/modelos.py`

