"""Deriva massa, CG e inércia de uma AletaSpec."""
from dataclasses import dataclass


from configs import AletaSpec


@dataclass(frozen=True)
class AletaDerivada:
    # Geometria
    area_planform: float       # m² por aleta
    volume_unitario: float     # m³

    # Massa
    massa_unitaria: float      # kg
    massa_total: float         # kg (todas as aletas)

    # Posições (em coords do foguete, x=0 no nariz)
    x_cg_local: float          # m — do bordo de ataque da raiz
    y_cg_local: float          # m — da raiz (radial)
    X_cg_absoluto: float       # m — posição axial do CG da aleta no foguete
    r_cg: float                # m — distância radial do CG ao eixo

    # Inércia intrínseca (relativa ao próprio centroide, todas as aletas)
    I_xx: float                # kg·m² — em torno do eixo longitudinal
    I_yy_local: float          # kg·m² — em torno de um eixo transversal

    # Referência
    r_rocket: float            # m — raio do foguete na região das aletas

def _poligono_propriedades(pts: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Área e centroide (x_c, y_c) de um polígono simples.

    Parameters
    ----------
    pts : lista de (x, y) em ordem (sentido horário ou anti-horário).

    Returns
    -------
    (area, x_c, y_c)
        area é sempre positiva; x_c, y_c são as coordenadas do centroide.
    """
    n = len(pts)
    soma_cruzada = 0.0
    soma_x = 0.0
    soma_y = 0.0

    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        soma_cruzada += cross
        soma_x += (x1 + x2) * cross
        soma_y += (y1 + y2) * cross

    area_signed = soma_cruzada / 2.0
    x_c = soma_x / (6.0 * area_signed)
    y_c = soma_y / (6.0 * area_signed)
    return abs(area_signed), x_c, y_c

def calcular_aleta(spec: AletaSpec, r_rocket: float) -> AletaDerivada:
    """Deriva massa, CG e inércia a partir da geometria e material."""
    Cr, Ct, XR, S_le, S_te, t = (
        spec.root_chord, spec.tip_chord, spec.sweep_length,
        spec.span_le, spec.span_te, spec.thickness,
    )

    # ---------- Área e centroide ----------
    pts = [
        (0.0,          0.0),
        (XR,           S_le),
        (XR + Ct,      S_te),
        (Cr,           0.0),
    ]
    A, x_c, y_c = _poligono_propriedades(pts)
    V_unit = A * t

    # ---------- Massa ----------
    m_unit = spec.densidade * V_unit
    m_total = spec.n * m_unit

    X_abs = spec.position + x_c
    r_c = r_rocket + y_c

    # ---------- Inércia intrínseca (aproximação ponto-massa) ----------
    # Todas as n aletas estão a uma distância ≈ r_c do eixo longitudinal.
    # Roll: I_xx = Σ m_i · r_c² = m_total · r_c²
    I_xx = m_total * r_c**2

    # Pitch/yaw: para n=4 aletas em cruz, a "dispersão" em torno do eixo
    # transversal é metade da do roll (só metade das aletas está deslocada
    # em cada direção transversal).
    I_yy_local = m_total * r_c**2 / 2

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



def main() -> None:
    from configs import ALETA_IREC, FOGUETE
    d = calcular_aleta(ALETA_IREC, r_rocket=FOGUETE["radius"])
    print(f"Massa total: {d.massa_total:.4f} kg")
    print(f"Área:        {d.area_planform:.6f} m²")
    print(f"CG axial:    {d.X_cg_absoluto:.4f} m")
    print(f"r_cg:        {d.r_cg:.4f} m")
    print(f"I_xx:        {d.I_xx:.6f} kg·m²")
    print(f"I_yy_local:  {d.I_yy_local:.6f} kg·m²")

    # --- Validações ---
    assert 3.0 < d.massa_total < 4.0, f"massa suspeita: {d.massa_total}"
    assert 0.02 < d.area_planform < 0.03, f"área suspeita: {d.area_planform}"
    assert 2.2 < d.X_cg_absoluto < 2.5, f"CG suspeito: {d.X_cg_absoluto}"
    assert 0.05 < d.I_xx < 0.10, f"I_xx suspeito: {d.I_xx}"

    print("\n✓ aletas OK")


if __name__ == '__main__':
    main()

