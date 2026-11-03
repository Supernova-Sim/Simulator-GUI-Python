---
component_id: 1.1.4
component_name: Rocket Specification Schemas
---

# Rocket Specification Schemas

## Component Description

Defines domain dataclasses, geometry specifications, safety limits, and serialization schemas for rocket components.

---

## Key References:

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/specs.py (lines 57-79)
```
class GrainSpec:
    """Grão propelente cilíndrico oco (BATES)."""
    length: float             # m
    outer_radius: float       # m
    inner_radius: float       # m

    def __post_init__(self) -> None:
        if self.length <= 0:
            raise ValueError(f"GrainSpec.length deve ser > 0 (recebido: {self.length})")
        if self.outer_radius <= 0:
            raise ValueError(f"GrainSpec.outer_radius deve ser > 0 (recebido: {self.outer_radius})")
        if self.inner_radius < 0 or self.inner_radius >= self.outer_radius:
            raise ValueError(
                f"GrainSpec.inner_radius ({self.inner_radius}) deve estar entre 0 e "
                f"outer_radius ({self.outer_radius})"
            )

    def to_dict(self) -> dict[str, float]:
        return {
            "length": self.length,
            "outer_radius": self.outer_radius,
            "inner_radius": self.inner_radius,
        }
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/specs.py (lines 24-50)
```
class LimitesSeguranca:
    """Critérios de aceitação estrutural e operacional (ex.: IREC)."""
    fs_min_carcaca: float = 2.0
    fs_alvo_carcaca: float = 3.0
    fs_min_aletas: float = 2.0
    fs_min_estrutura: float = 2.0
    fs_min_recuperacao: float = 2.0

    p0_max: float = 8.0e6           # Pa
    kn_max: float = 250.0           # —
    mass_flux_max: float = 1406.0   # kg/(m²·s)
    port_throat_min: float = 2.0    # —
    erosion_max_garganta: float = 0.02

    sigma_lim_carcaca: float = 145e6  # Pa — Alumínio 6063-T5

    def __post_init__(self) -> None:
        if self.fs_min_carcaca <= 0:
            raise ValueError(f"LimitesSeguranca.fs_min_carcaca deve ser > 0 (recebido: {self.fs_min_carcaca})")
        if self.p0_max <= 0:
            raise ValueError(f"LimitesSeguranca.p0_max deve ser > 0 (recebido: {self.p0_max})")
        if self.kn_max <= 0:
            raise ValueError(f"LimitesSeguranca.kn_max deve ser > 0 (recebido: {self.kn_max})")
        if self.mass_flux_max <= 0:
            raise ValueError(f"LimitesSeguranca.mass_flux_max deve ser > 0 (recebido: {self.mass_flux_max})")
        if self.sigma_lim_carcaca <= 0:
            raise ValueError(f"LimitesSeguranca.sigma_lim_carcaca deve ser > 0 (recebido: {self.sigma_lim_carcaca})")
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/specs.py (lines 83-210)
```
class MotorSpec:
    """Especificação declarativa de um motor sólido.

    Quando `ric_path` é fornecido, a geometria dos grãos, densidade do
    propelente e raios da tubeira são extraídos automaticamente do arquivo
    `.ric` (já considerando eventuais `overrides`) dentro de `derivar_motor()`.
    """
    nome: str

    # ---------- Carcaça ----------
    case_inner_radius: float
    case_wall_thickness: float
    case_density: float = 2700.0

    # ---------- Montagem / Tubeira ----------
    grain_separation: float = 0.010
    nozzle_position: float = 0.0

    # ---------- Fontes de dados (pelo menos uma obrigatória) ----------
    ric_path: str | Path | None = None
    thrust_curve_path: str | Path | None = None

    # ---------- Geometria manual (obrigatória apenas se ric_path for None) ----------
    grains: tuple[GrainSpec, ...] = ()
    propellant_density: float | None = None
    nozzle_exit_radius: float | None = None
    throat_radius: float | None = None

    # ---------- Opcionais da carcaça ----------
    case_length: float | None = None
    margin_nozzle_side: float = 0.075
    margin_forward_side: float = 0.075

    dry_mass: float | None = None
    dry_mass_extra: float = 0.0
    nozzle_mass: float = 0.0

    dry_inertia_override: tuple[float, float, float] | None = None

    # ---------- Overrides de simulação (dot-path sobre o .ric em memória) ----------
    overrides: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.nome or not self.nome.strip():
            raise ValueError("MotorSpec.nome não pode ser vazio.")
        if self.case_inner_radius <= 0:
            raise ValueError(
                f"MotorSpec('{self.nome}'): case_inner_radius deve ser > 0 "
                f"(recebido: {self.case_inner_radius})"
            )
        if self.case_wall_thickness <= 0:
            raise ValueError(
                f"MotorSpec('{self.nome}'): case_wall_thickness deve ser > 0 "
                f"(recebido: {self.case_wall_thickness})"
            )
        if self.case_density <= 0:
            raise ValueError(
                f"MotorSpec('{self.nome}'): case_density deve ser > 0 "
                f"(recebido: {self.case_density})"
            )
        if self.grain_separation < 0:
            raise ValueError(
                f"MotorSpec('{self.nome}'): grain_separation deve ser >= 0 "
                f"(recebido: {self.grain_separation})"
            )
        if self.ric_path is None and self.thrust_curve_path is None:
            raise ValueError(
                f"MotorSpec('{self.nome}'): defina pelo menos 'ric_path' ou 'thrust_curve_path'."
            )
        if self.ric_path is None:
            if not self.grains:
                raise ValueError(
                    f"MotorSpec('{self.nome}'): sem 'ric_path', o campo 'grains' é obrigatório."
                )
            if self.propellant_density is None or self.propellant_density <= 0:
                raise ValueError(
                    f"MotorSpec('{self.nome}'): sem 'ric_path', 'propellant_density' > 0 é obrigatório."
                )
            if self.nozzle_exit_radius is None or self.nozzle_exit_radius <= 0:
                raise ValueError(
                    f"MotorSpec('{self.nome}'): sem 'ric_path', 'nozzle_exit_radius' > 0 é obrigatório."
                )
            if self.throat_radius is None or self.throat_radius <= 0:
                raise ValueError(
                    f"MotorSpec('{self.nome}'): sem 'ric_path', 'throat_radius' > 0 é obrigatório."
                )

    def resumo(self) -> str:
        linhas = [
            f"Motor: {self.nome}",
            f"  fonte .ric: {self.ric_path or '—'}",
            f"  fonte .eng: {self.thrust_curve_path or '—'}",
            (
                f"  Carcaça: r_i={self.case_inner_radius:.5f} m, "
                f"t={self.case_wall_thickness:.4f} m, ρ={self.case_density:.1f} kg/m³"
            ),
        ]
        if self.grains:
            linhas.append(f"  Grãos explícitos: {len(self.grains)}")
        if self.overrides:
            linhas.append(f"  ⚠ OVERRIDES ATIVOS: {len(self.overrides)} parâmetro(s)")
        return "\n".join(linhas)

    def to_dict(self) -> dict[str, Any]:
        """Dict serializável (JSON-friendly) com os campos da especificação."""
        return {
            "nome": self.nome,
            "ric_path": str(self.ric_path) if self.ric_path is not None else None,
            "thrust_curve_path": str(self.thrust_curve_path) if self.thrust_curve_path is not None else None,
            "case_inner_radius": self.case_inner_radius,
            "case_wall_thickness": self.case_wall_thickness,
            "case_density": self.case_density,
            "grains": [g.to_dict() for g in self.grains],
            "grain_separation": self.grain_separation,
            "propellant_density": self.propellant_density,
            "nozzle_position": self.nozzle_position,
            "nozzle_exit_radius": self.nozzle_exit_radius,
            "throat_radius": self.throat_radius,
            "case_length": self.case_length,
            "margin_nozzle_side": self.margin_nozzle_side,
            "margin_forward_side": self.margin_forward_side,
            "dry_mass": self.dry_mass,
            "dry_mass_extra": self.dry_mass_extra,
            "nozzle_mass": self.nozzle_mass,
            "dry_inertia_override": list(self.dry_inertia_override)
            if self.dry_inertia_override is not None else None,
            "overrides": dict(self.overrides) if self.overrides else None,
        }
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/specs.py (lines 217-242)
```
class TuboSpec:
    """Cilindro oco (ou maciço quando espessura == raio_externo)."""
    nome: str
    raio_externo: float
    espessura: float
    comprimento: float
    posicao: float
    densidade: float
    massa_extra: float = 0.0

    def __post_init__(self) -> None:
        if self.raio_externo <= 0:
            raise ValueError(f"TuboSpec('{self.nome}'): raio_externo deve ser > 0 (recebido: {self.raio_externo})")
        if self.espessura <= 0 or self.espessura > self.raio_externo:
            raise ValueError(
                f"TuboSpec('{self.nome}'): espessura ({self.espessura}) deve estar entre "
                f"0 e raio_externo ({self.raio_externo})"
            )
        if self.comprimento <= 0:
            raise ValueError(f"TuboSpec('{self.nome}'): comprimento deve ser > 0 (recebido: {self.comprimento})")
        if self.densidade <= 0:
            raise ValueError(f"TuboSpec('{self.nome}'): densidade deve ser > 0 (recebido: {self.densidade})")

    @property
    def raio_interno(self) -> float:
        return self.raio_externo - self.espessura
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/specs.py (lines 331-392)
```
class GeometriaMedidaSpec:
    """Propriedades globais medidas diretamente na bancada/OpenRocket (`modo='medido'`)."""
    raio: float
    massa_seca: float
    inercia_transversal: float
    inercia_longitudinal: float
    cg_sem_motor: float
    coifa_length: float
    coifa_kind: str
    coifa_position: float
    aletas_n: int
    aletas_position: float
    aletas_shape_points: tuple[tuple[float, float], ...]
    aletas_cant_angle: float = 0.0
    aletas_trapezio_equiv: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.raio <= 0:
            raise ValueError(f"GeometriaMedidaSpec: raio deve ser > 0 (recebido: {self.raio})")
        if self.massa_seca <= 0:
            raise ValueError(f"GeometriaMedidaSpec: massa_seca deve ser > 0 (recebido: {self.massa_seca})")
        if self.inercia_transversal <= 0 or self.inercia_longitudinal <= 0:
            raise ValueError(
                "GeometriaMedidaSpec: inercia_transversal e inercia_longitudinal devem ser > 0 "
                f"(recebidos: {self.inercia_transversal}, {self.inercia_longitudinal})"
            )
        if self.coifa_kind not in PERFIS_COIFA_VALIDOS:
            raise ValueError(
                f"GeometriaMedidaSpec: coifa_kind inválido {self.coifa_kind!r}. "
                f"Valores aceitos: {PERFIS_COIFA_VALIDOS}"
            )

    @property
    def inercia_rocketpy(self) -> tuple[float, float, float]:
        """Convenção RocketPy: (I_11, I_22, I_33) = (transversal, transversal, longitudinal)."""
        return (self.inercia_transversal, self.inercia_transversal, self.inercia_longitudinal)

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
            "length": self.coifa_length,
            "kind": self.coifa_kind,
            "position": self.coifa_position,
        }

    def dict_aletas_freeform(self) -> dict[str, Any]:
        return {
            "n": self.aletas_n,
            "position": self.aletas_position,
            "shape_points": list(self.aletas_shape_points),
            "cant_angle": self.aletas_cant_angle,
        }
```


## Source Files:

- `src/specs.py`

