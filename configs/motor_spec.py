"""Especificações do motor — lista de grãos + carcaça + tubeira."""
from dataclasses import dataclass

from hefesto.paths import MOTORES


@dataclass(frozen=True)
class GrainSpec:
    """Grão BATES individual (cilindro oco inibido nas faces)."""
    length: float             # m
    outer_radius: float       # m
    inner_radius: float       # m


@dataclass(frozen=True)
class MotorSpec:
    # ---------- Obrigatórios ----------
    nome: str
    thrust_curve_path: str

    case_inner_radius: float
    case_wall_thickness: float
    case_density: float

    grains: tuple[GrainSpec, ...]
    grain_separation: float
    propellant_density: float

    nozzle_position: float
    nozzle_exit_radius: float
    throat_radius: float

    # ---------- Opcionais ----------
    case_length: float | None = None
    margin_nozzle_side: float = 0.075
    margin_forward_side: float = 0.075

    dry_mass: float | None = None
    dry_mass_extra: float = 0.0
    nozzle_mass: float = 0.0

    # ---------- Opcionais ----------
    case_length: float | None = None
    margin_nozzle_side: float = 0.075
    margin_forward_side: float = 0.075

    dry_mass: float | None = None
    dry_mass_extra: float = 0.0
    nozzle_mass: float = 0.0

    # Override de inércia seca (kg·m²). None → casca cilíndrica derivada.
    dry_inertia_override: tuple[float, float, float] | None = None


# ============================================================
#  Configuração do Medusa (IREC)
# ============================================================

_GRAIN_FWD = GrainSpec(length=0.150, outer_radius=0.049345, inner_radius=0.0205)
_GRAIN_AFT = GrainSpec(length=0.150, outer_radius=0.049345, inner_radius=0.0270)

MOTOR_IREC = MotorSpec(
    nome="Medusa KNSB",
    thrust_curve_path=str(MOTORES / "jul1semMedidas.eng"),

    case_inner_radius=0.05395,
    case_wall_thickness=0.003175,
    case_density=2700.0,

    grains=(_GRAIN_FWD, _GRAIN_FWD, _GRAIN_FWD, _GRAIN_FWD,
            _GRAIN_AFT, _GRAIN_AFT),
    grain_separation=0.010,
    propellant_density=1841.0,

    nozzle_position=0.016,
    nozzle_exit_radius=0.039,
    throat_radius=0.017,

    # Fixos por ora (medições reais)
    case_length=1.100,
    dry_mass=7.5,

    # Margens — usadas se case_length=None (fallback)
    margin_nozzle_side=0.075,
    margin_forward_side=0.075,
)