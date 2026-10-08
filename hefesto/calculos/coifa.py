"""Deriva massa, CG e inércia de uma CoifaSpec por integração numérica.

A coifa é tratada como uma casca fina (t << L) de espessura constante
sobre o perfil `r(x)` do formato escolhido. `x=0` é o bico, `x=L` é a base.
"""
import math
from dataclasses import dataclass

from configs.especificacao import CoifaSpec


# ============================================================
#  Perfis geométricos — r(x), x ∈ [0, L]
# ============================================================

def _perfil_conico(x: float, L: float, R: float) -> float:
    """Cone: r(x) = R · x / L."""
    return R * x / L


def _perfil_lvhaack(x: float, L: float, R: float) -> float:
    """LV-Haack (von Kármán quando C=0).

    θ(x) = arccos(1 − 2x/L)
    r(x) = R/√π · √(θ − sin(2θ)/2)
    """
    arg = 1.0 - 2.0 * x / L
    arg = max(-1.0, min(1.0, arg))          # proteção contra erro numérico
    theta = math.acos(arg)
    val = theta - math.sin(2.0 * theta) / 2.0
    return R / math.sqrt(math.pi) * math.sqrt(max(0.0, val))


def _perfil_ogive(x: float, L: float, R: float) -> float:
    """Ogiva tangente. ρ = (R² + L²) / (2R)."""
    rho = (R**2 + L**2) / (2.0 * R)
    xp = L - x                              # distância da base
    return math.sqrt(max(0.0, rho**2 - xp**2)) + R - rho


_PERFIS = {
    "conical": _perfil_conico,
    "lvhaack": _perfil_lvhaack,
    "ogive":   _perfil_ogive,
}


def perfil(x: float, kind: str, L: float, R: float) -> float:
    if kind not in _PERFIS:
        raise ValueError(f"kind inválido: {kind!r}. Use: {list(_PERFIS)}")
    return _PERFIS[kind](x, L, R)


def _derivada_perfil(x: float, kind: str, L: float, R: float, eps: float = 1e-7) -> float:
    x_lo = max(0.0, x - eps)
    x_hi = min(L, x + eps)
    return (perfil(x_hi, kind, L, R) - perfil(x_lo, kind, L, R)) / (x_hi - x_lo)


# ============================================================
#  Saída
# ============================================================

@dataclass(frozen=True)
class CoifaDerivada:
    nome: str
    massa: float              # kg — casca + massa_extra
    cg: float                 # m — posição axial em coords do foguete
    I_xx_local: float         # kg·m² — em torno do eixo longitudinal
    I_yy_local: float         # kg·m² — transversal pelo próprio CG


# ============================================================
#  Integração numérica
# ============================================================

def calcular_coifa(spec: CoifaSpec, raio_base: float, n: int = 200) -> CoifaDerivada:
    """Integra massa e inércia da casca ao longo do perfil.

    `raio_base` é o raio do corpo do foguete, onde a coifa termina (r(L) = R).
    `n` é o número de fatias axiais.
    """
    L = spec.length
    R = raio_base
    t = spec.thickness
    rho = spec.densidade
    dx = L / n

    # ---------- Passo 1: massa, momento, I_xx ----------
    m_shell = 0.0
    momento = 0.0
    I_xx = 0.0

    for i in range(n):
        x = (i + 0.5) * dx
        r = perfil(x, spec.kind, L, R)
        dr = _derivada_perfil(x, spec.kind, L, R)
        ds = math.sqrt(1.0 + dr**2) * dx        # comprimento de arco
        dA = 2.0 * math.pi * r * ds             # área lateral do anel
        dm = dA * t * rho
        m_shell += dm
        momento += x * dm
        I_xx += r**2 * dm

    cg_shell = momento / m_shell if m_shell > 0 else 0.0

    # ---------- Passo 2: massa extra ----------
    m_extra = spec.massa_extra
    x_extra = spec.posicao_massa_extra if spec.posicao_massa_extra is not None else cg_shell

    m_total = m_shell + m_extra
    cg_total = (m_shell * cg_shell + m_extra * x_extra) / m_total if m_total > 0 else 0.0

    # ---------- Passo 3: I_yy local (referente ao CG total) ----------
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
        # Massa extra em x_extra, tratada como massa pontual (r=0):
        I_yy_local += m_extra * (x_extra - cg_total) ** 2
        # I_xx dela é zero (r=0), então nada a somar

    return CoifaDerivada(
        nome=spec.nome,
        massa=m_total,
        cg=spec.position + cg_total,
        I_xx_local=I_xx,
        I_yy_local=I_yy_local,
    )


# ============================================================
#  Inspeção rápida
# ============================================================

def main() -> None:
    from configs.especificacao import COIFA_IREC

    d = calcular_coifa(COIFA_IREC, raio_base=0.079)
    print(f"massa:      {d.massa:.4f} kg")
    print(f"CG:         {d.cg:.4f} m")
    print(f"I_xx_local: {d.I_xx_local:.6f} kg·m²")
    print(f"I_yy_local: {d.I_yy_local:.6f} kg·m²")


if __name__ == "__main__":
    main()