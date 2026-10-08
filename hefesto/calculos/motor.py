"""Deriva propriedades do motor a partir de MotorSpec + arquivo .eng.

Dois tipos de informação:
  1. Curva de empuxo (do .eng) → burn_time, total_impulse, max_thrust
  2. Geometria (dos grãos + carcaça) → propellant_mass, cg, dry_inertia

Coordenadas locais: x=0 no TOPO do motor (extremidade forward),
x=case_length na base. O `resolver` soma a posição absoluta do motor no foguete.
"""
import math
from dataclasses import dataclass
from pathlib import Path

from configs.motor.spec import MotorSpec, GrainSpec
from hefesto.calculos.motorlib_wrapper import MotorResultado, simular_ric


# ============================================================
#  Parser do arquivo .eng (formato RASP)
# ============================================================

def _ler_eng(path: str | Path) -> tuple[list[float], list[float], dict]:
    """Parser RASP .eng.

    Returns
    -------
    (tempos, empuxos, header)
        header: dict com designation, diameter_mm, length_mm, delay,
                propellant_mass, total_mass.
    """
    tempos: list[float] = []
    empuxos: list[float] = []
    header_line: str | None = None

    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            if header_line is None:
                header_line = line
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                t = float(parts[0])
                ft = float(parts[1])
            except ValueError:
                continue
            tempos.append(t)
            empuxos.append(ft)

    if header_line is None:
        raise ValueError(f"arquivo .eng sem header: {path}")
    if len(tempos) < 2:
        raise ValueError(f"arquivo .eng sem dados suficientes: {path}")

    hp = header_line.split()
    header = {
        "designation":     hp[0] if len(hp) > 0 else "",
        "diameter_mm":     float(hp[1]) if len(hp) > 1 else 0.0,
        "length_mm":       float(hp[2]) if len(hp) > 2 else 0.0,
        "delay":           hp[3] if len(hp) > 3 else "",
        "propellant_mass": float(hp[4]) if len(hp) > 4 else 0.0,
        "total_mass":      float(hp[5]) if len(hp) > 5 else 0.0,
    }
    return tempos, empuxos, header


def _integrar_trapezio(tempos: list[float], empuxos: list[float]) -> float:
    """∫ F(t) dt por regra do trapézio."""
    total = 0.0
    for i in range(1, len(tempos)):
        dt = tempos[i] - tempos[i - 1]
        total += 0.5 * (empuxos[i] + empuxos[i - 1]) * dt
    return total


# ============================================================
#  Saída
# ============================================================

@dataclass(frozen=True)
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

    # ---------- Geometria dos grãos ----------
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

    # ---------- Inércia ----------
    dry_inertia: tuple[float, float, float]

    # ---------- Agregados ----------
    mass_loaded: float          # kg — dry_mass + propellant_mass

    def to_dict(self) -> dict:
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
            # curva_empuxo é grande — omitida de propósito
        }


# ============================================================
#  Derivações
# ============================================================

def _derivar_do_motor(spec: MotorSpec) -> dict:
    """Retorna tudo que vem da fonte de verdade (.ric > .eng)."""
    if spec.ric_path is not None:
        r = simular_ric(spec.ric_path)
        return {
            "fonte": "ric",
            "burn_time": (r.tempo[0], r.tempo[-1]),
            "total_impulse": r.impulso_total,
            "max_thrust": r.empuxo_max,
            "eng_propellant_mass": r.massa_propelente_inicial,
            "curva_empuxo": tuple(r.curva_empuxo),
            "p0_pico": r.p0_pico,
            "kn_pico": r.kn_pico,
            "mass_flux_pico": r.mass_flux_pico,
            "isp_entregue": r.isp_entregue,
        }
    if spec.thrust_curve_path is not None:
        burn, imp, mx, ep = _derivar_do_eng(spec)
        return {
            "fonte": "eng",
            "burn_time": burn,
            "total_impulse": imp,
            "max_thrust": mx,
            "eng_propellant_mass": ep,
            "curva_empuxo": None,
            "p0_pico": None,
            "kn_pico": None,
            "mass_flux_pico": None,
            "isp_entregue": None,
        }
    raise ValueError(
        f"MotorSpec '{spec.nome}' precisa de ric_path ou thrust_curve_path."
    )

def _derivar_do_eng(spec: MotorSpec) -> tuple:
    tempos, empuxos, header = _ler_eng(spec.thrust_curve_path)

    burn_time = (tempos[0], tempos[-1])
    total_impulse = _integrar_trapezio(tempos, empuxos)
    max_thrust = max(empuxos)
    return burn_time, total_impulse, max_thrust, header["propellant_mass"]


def _derivar_dos_graos(spec: MotorSpec) -> tuple:
    """Retorna (massa, comprimento_prop, stack_length, cg_local, inner_eff)."""
    massa_total = 0.0
    momento = 0.0
    volume_total = 0.0
    x = spec.margin_forward_side          # começa após a margem forward
    comprimento_prop = 0.0

    for i, g in enumerate(spec.grains):
        V = math.pi * (g.outer_radius**2 - g.inner_radius**2) * g.length
        m = V * spec.propellant_density

        x_centro = x + g.length / 2.0
        massa_total += m
        momento += m * x_centro
        volume_total += V
        comprimento_prop += g.length

        # Próximo grão: avança o comprimento + separação (exceto no último)
        x += g.length
        if i < len(spec.grains) - 1:
            x += spec.grain_separation

    stack_length = comprimento_prop + (len(spec.grains) - 1) * spec.grain_separation
    cg_local = momento / massa_total if massa_total > 0 else 0.0

    # Raio interno efetivo — preserva o volume total de propelente
    # assumindo raio externo constante e comprimento total do propelente.
    r_o = spec.grains[0].outer_radius
    r_i_eff_sq = r_o**2 - volume_total / (math.pi * comprimento_prop)
    inner_eff = math.sqrt(max(0.0, r_i_eff_sq))

    return massa_total, comprimento_prop, stack_length, cg_local, inner_eff


def _derivar_carcaca(spec: MotorSpec, stack_length: float) -> tuple:
    """Retorna (case_length, case_outer_radius, dry_mass)."""
    # Comprimento
    if spec.case_length is not None:
        case_length = spec.case_length
    else:
        case_length = (
            spec.margin_forward_side + stack_length + spec.margin_nozzle_side
        )

    # Raio externo
    r_o = spec.case_inner_radius + spec.case_wall_thickness

    # Massa seca
    if spec.dry_mass is not None:
        dry_mass = spec.dry_mass
    else:
        V_casca = math.pi * (r_o**2 - spec.case_inner_radius**2) * case_length
        massa_casca = V_casca * spec.case_density
        dry_mass = massa_casca + spec.nozzle_mass + spec.dry_mass_extra

    return case_length, r_o, dry_mass


def _derivar_inercia_seca(
    dry_mass: float, r_o: float, r_i: float, L: float,
) -> tuple[float, float]:
    """Inércia de casca cilíndrica oca (aproximação da carcaça real).

    Assume que toda a dry_mass está distribuída na casca cilíndrica — o que
    superestima ligeiramente o roll (a tubeira é mais concentrada no eixo)
    e o pitch (a tubeira está no meio, não nas extremidades). Aceitável
    enquanto não há detalhamento da tubeira/bulkhead.

    Estimativa: 7.5 kg nesse tamanho, I_xx ~40% acima do valor real
    (tubeira ocupa raio menor). Refinar quando CAD/medição existir.
    """
    I_xx = 0.5 * dry_mass * (r_o**2 + r_i**2)
    I_yy = (dry_mass / 12.0) * (3.0 * (r_o**2 + r_i**2) + L**2)
    return I_xx, I_yy


# ============================================================
#  Agregador
# ============================================================

def derivar_motor(spec: MotorSpec) -> MotorDerivado:
    # --- Da fonte de verdade ---
    info = _derivar_do_motor(spec)

    # --- Dos grãos ---
    prop_mass, prop_len, stack_len, cg_prop, inner_eff = _derivar_dos_graos(spec)

    # --- Da carcaça ---
    case_len, case_r_o, dry_mass = _derivar_carcaca(spec, stack_len)
    cg_dry = case_len / 2.0

    # --- Inércias da carcaça ---
    if spec.dry_inertia_override is not None:
        dry_inertia = spec.dry_inertia_override
    else:
        I_xx_dry, I_yy_dry = _derivar_inercia_seca(
            dry_mass, case_r_o, spec.case_inner_radius, case_len,
        )
        dry_inertia = (I_yy_dry, I_yy_dry, I_xx_dry)

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
    )


# ============================================================
#  Inspeção rápida
# ============================================================

def main() -> None:
    from configs.motor.medusa import MOTOR_IREC

    d = derivar_motor(MOTOR_IREC)

    print(f"--- {d.nome} ---")
    print()
    print("Do .eng:")
    print(f"  burn_time:              {d.burn_time}")
    print(f"  total_impulse:          {d.total_impulse:.2f} N·s")
    print(f"  max_thrust:             {d.max_thrust:.1f} N")
    print(f"  eng_propellant_mass:    {d.eng_propellant_mass:.4f} kg (header)")
    print()
    print("Geometria dos grãos:")
    print(f"  propellant_mass:        {d.propellant_mass:.4f} kg")
    print(f"  propellant_length:      {d.propellant_length:.4f} m")
    print(f"  stack_length:           {d.stack_length:.4f} m")
    print(f"  cg_propellant (local):  {d.cg_propellant:.4f} m")
    print(f"  inner_radius_efetivo:   {d.grain_inner_radius_effective:.5f} m")
    print()
    print("Carcaça:")
    print(f"  case_length:            {d.case_length:.4f} m")
    print(f"  case_outer_radius:      {d.case_outer_radius:.5f} m")
    print(f"  dry_mass:               {d.dry_mass:.4f} kg")
    print(f"  cg_dry (local):         {d.cg_dry:.4f} m")
    print()
    print("Inércia seca (aproximação cilíndrica):")
    print(f"  I_xx (roll):            {d.dry_inertia[0]:.6f} kg·m²")
    print(f"  I_yy (pitch/yaw):       {d.dry_inertia[1]:.6f} kg·m²")
    print()
    print(f"  mass_loaded:            {d.mass_loaded:.4f} kg")
    print(f"Fonte:                  {d.fonte}")
    if d.p0_pico is not None:
        print(f"P0_pico:                {d.p0_pico / 1e6:.3f} MPa")
        print(f"Kn_pico:                {d.kn_pico:.1f}")
        print(f"Mass flux pico:         {d.mass_flux_pico:.3f} kg/(m²·s)")
        print(f"ISP entregue:           {d.isp_entregue:.2f} s")


if __name__ == "__main__":
    main()