---
component_id: 1.3
component_name: Fin Geometry and Aerodynamics Calculations
---

# Fin Geometry and Aerodynamics Calculations

## Component Description

Derives fin mass, center of gravity, and moments of inertia, and translates fin geometry for aerodynamic analysis tools.

---

## Key References:

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/aletas.py (lines 48-92)
```
def calcular_aleta(spec: AletaSpec, r_rocket: float) -> AletaDerivada:
    """Deriva massa, CG e inércia a partir da geometria e material."""
    if r_rocket <= 0:
        raise ValueError(f"calcular_aleta: r_rocket deve ser > 0 (recebido: {r_rocket})")

    Cr, Ct, XR, S_le, S_te, t = (
        spec.root_chord,
        spec.tip_chord,
        spec.sweep_length,
        spec.span_le,
        spec.span_te,
        spec.thickness,
    )

    pts = [
        (0.0, 0.0),
        (XR, S_le),
        (XR + Ct, S_te),
        (Cr, 0.0),
    ]
    A, x_c, y_c = _poligono_propriedades(pts)
    V_unit = A * t

    m_unit = spec.densidade * V_unit
    m_total = spec.n * m_unit

    X_abs = spec.position + x_c
    r_c = r_rocket + y_c

    I_xx = m_total * r_c**2
    I_yy_local = m_total * r_c**2 / 2.0

    return AletaDerivada(
        area_planform=A,
        volume_unitario=V_unit,
        massa_unitaria=m_unit,
        massa_total=m_total,
        x_cg_local=x_c,
        y_cg_local=y_c,
        X_cg_absoluto=X_abs,
        r_cg=r_c,
        I_xx=I_xx,
        I_yy_local=I_yy_local,
        r_rocket=r_rocket,
    )
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/aletas.py (lines 11-24)
```
class AletaDerivada:
    area_planform: float       # m² por aleta
    volume_unitario: float     # m³
    massa_unitaria: float      # kg
    massa_total: float         # kg (todas as aletas)

    x_cg_local: float          # m — do bordo de ataque da raiz
    y_cg_local: float          # m — da raiz (radial)
    X_cg_absoluto: float       # m — posição axial do CG da aleta no foguete
    r_cg: float                # m — distância radial do CG ao eixo longitudinal

    I_xx: float                # kg·m² — longitudinal (roll, eixo e_3)
    I_yy_local: float          # kg·m² — transversal (pitch/yaw, pelo próprio CG)
    r_rocket: float            # m — raio do foguete na região das aletas
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/aletas_rasaero.py (lines 33-55)
```
def aleta_para_rasaero(
    spec: AletaSpec,
    *,
    span_modo: str = "le",   # "le", "media", "te"
) -> AletaRASAero:
    """Converte `AletaSpec` (SI) para formato RASAero (polegadas)."""
    if span_modo == "le":
        span = spec.span_le
    elif span_modo == "te":
        span = spec.span_te
    elif span_modo == "media":
        span = (spec.span_le + spec.span_te) / 2.0
    else:
        raise ValueError(f"span_modo inválido: {span_modo!r}. Use 'le', 'media' ou 'te'.")

    return AletaRASAero(
        fin_count=spec.n,
        root_chord_in=spec.root_chord * IN_POR_M,
        span_in=span * IN_POR_M,
        tip_chord_in=spec.tip_chord * IN_POR_M,
        sweep_distance_in=spec.sweep_length * IN_POR_M,
        thickness_in=spec.thickness * IN_POR_M,
    )
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/aletas_rasaero.py (lines 13-30)
```
class AletaRASAero:
    """Campos de aleta prontos para inserção no RASAero II GUI."""
    fin_count: int
    root_chord_in: float
    span_in: float
    tip_chord_in: float
    sweep_distance_in: float
    thickness_in: float
    airfoil_section: str = "Square"

    def imprimir(self) -> None:
        print(f"  Fin Count:               {self.fin_count}")
        print(f"  Root Chord (in):         {self.root_chord_in:.4f}")
        print(f"  Span (in):               {self.span_in:.4f}")
        print(f"  Tip Chord (in):          {self.tip_chord_in:.4f}")
        print(f"  Sweep Distance (in):     {self.sweep_distance_in:.4f}")
        print(f"  Fin Thickness (in):      {self.thickness_in:.4f}")
        print(f"  Airfoil Section:         {self.airfoil_section}")
```


## Source Files:

- `src/calculos/aletas.py`
- `src/calculos/aletas_rasaero.py`

