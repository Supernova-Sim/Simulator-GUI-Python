---
component_id: 1.2
component_name: Component and Nose Cone Analysis
---

# Component and Nose Cone Analysis

## Component Description

Calculates mass and inertia for structural components and nose cones while providing environment configurations and visualization utilities.

---

## Key References:

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/componentes.py (lines 70-73)
```
def derivar_todos(
    componentes: Sequence[TuboSpec | MassaPontualSpec],
) -> list[ComponenteDerivado]:
    return [derivar(c) for c in componentes]
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/componentes.py (lines 62-67)
```
def derivar(componente: TuboSpec | MassaPontualSpec) -> ComponenteDerivado:
    if isinstance(componente, TuboSpec):
        return derivar_tubo(componente)
    if isinstance(componente, MassaPontualSpec):
        return derivar_massa_pontual(componente)
    raise TypeError(f"Tipo de componente não suportado: {type(componente).__name__}")
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/componentes.py (lines 17-22)
```
class ComponenteDerivado:
    nome: str
    massa: float              # kg
    posicao: float            # m — CG axial (x=0 no nariz)
    I_xx_local: float         # kg·m² — longitudinal (roll, eixo e_3)
    I_yy_local: float         # kg·m² — transversal (pitch/yaw, pelo próprio CG)
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/coifa.py (lines 63-116)
```
def calcular_coifa(spec: CoifaSpec, raio_base: float, n: int = 200) -> CoifaDerivada:
    """Integra massa e inércia da casca ao longo do perfil axial."""
    if raio_base <= 0:
        raise ValueError(f"calcular_coifa: raio_base deve ser > 0 (recebido: {raio_base})")

    L = spec.length
    R = raio_base
    t = spec.thickness
    rho = spec.densidade
    dx = L / n

    m_shell = 0.0
    momento = 0.0
    I_xx = 0.0

    for i in range(n):
        x = (i + 0.5) * dx
        r = perfil(x, spec.kind, L, R)
        dr = _derivada_perfil(x, spec.kind, L, R)
        ds = math.sqrt(1.0 + dr**2) * dx
        dA = 2.0 * math.pi * r * ds
        dm = dA * t * rho
        m_shell += dm
        momento += x * dm
        I_xx += r**2 * dm

    cg_shell = momento / m_shell if m_shell > 0 else 0.0

    m_extra = spec.massa_extra
    x_extra = spec.posicao_massa_extra if spec.posicao_massa_extra is not None else cg_shell

    m_total = m_shell + m_extra
    cg_total = (m_shell * cg_shell + m_extra * x_extra) / m_total if m_total > 0 else 0.0

    I_yy_local = 0.0
    for i in range(n):
        x = (i + 0.5) * dx
        r = perfil(x, spec.kind, L, R)
        dr = _derivada_perfil(x, spec.kind, L, R)
        ds = math.sqrt(1.0 + dr**2) * dx
        dA = 2.0 * math.pi * r * ds
        dm = dA * t * rho
        I_yy_local += ((x - cg_total) ** 2 + r**2 / 2.0) * dm

    if m_extra > 0:
        I_yy_local += m_extra * (x_extra - cg_total) ** 2

    return CoifaDerivada(
        nome=spec.nome,
        massa=m_total,
        cg=spec.position + cg_total,
        I_xx_local=I_xx,
        I_yy_local=I_yy_local,
    )
```

### /home/icaro/Hub/01-Projetos_e_UFJF/supernova/simulacoes/github/hefesto privado-estrutura-vibe/src/calculos/coifa.py (lines 55-60)
```
class CoifaDerivada:
    nome: str
    massa: float              # kg — casca + massa_extra
    cg: float                 # m — posição axial em coords do foguete (x=0 no nariz)
    I_xx_local: float         # kg·m² — longitudinal (roll, eixo e_3)
    I_yy_local: float         # kg·m² — transversal pelo próprio CG
```


## Source Files:

- `src/ambiente.py`
- `src/c4_gerador.py`
- `src/calculos/coifa.py`
- `src/calculos/componentes.py`
- `src/smoke.py`
- `src/viz.py`

