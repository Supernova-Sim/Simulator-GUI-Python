# configs/motor_spec.py
"""Especificações do motor — dataclasses apenas.

Valores concretos do Medusa ficam em `configs/motor_medusa.py`.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class GrainSpec:
    """Grão BATES individual (cilindro oco inibido nas faces)."""
    length: float             # m
    outer_radius: float       # m
    inner_radius: float       # m

    def to_dict(self) -> dict:
        return {
            "length": self.length,
            "outer_radius": self.outer_radius,
            "inner_radius": self.inner_radius,
        }


@dataclass(frozen=True)
class MotorSpec:
    # ---------- Obrigatórios ----------
    nome: str

    # ---------- Carcaça ----------
    case_inner_radius: float
    case_wall_thickness: float
    case_density: float

    # ---------- Propelente ----------
    grains: tuple[GrainSpec, ...]
    grain_separation: float
    propellant_density: float

    # ---------- Tubeira ----------
    nozzle_position: float
    nozzle_exit_radius: float
    throat_radius: float

    # ---------- Fontes de dados (pelo menos uma) ----------
    ric_path: str | None = None          # .ric — fonte de verdade
    thrust_curve_path: str | None = None # .eng — fallback / cross-check

    # ---------- Opcionais ----------
    case_length: float | None = None
    margin_nozzle_side: float = 0.075
    margin_forward_side: float = 0.075

    dry_mass: float | None = None
    dry_mass_extra: float = 0.0
    nozzle_mass: float = 0.0

    dry_inertia_override: tuple[float, float, float] | None = None



    # ---------- Inspeção ----------
    def resumo(self) -> str:
        linhas = [
            f"Motor: {self.nome}",
            f"  .eng: {self.thrust_curve_path}",
            f"  Grãos: {len(self.grains)}",
            f"  Propelente: ρ={self.propellant_density:.1f} kg/m³",
            f"  Carcaça: r_i={self.case_inner_radius:.5f} m, "
            f"t={self.case_wall_thickness:.4f} m",
            f"  Tubeira: garganta r={self.throat_radius:.4f} m, "
            f"saída r={self.nozzle_exit_radius:.4f} m, "
            f"pos={self.nozzle_position:.4f} m",
        ]
        return "\n".join(linhas)

    def to_dict(self) -> dict:
        """Dict serializável (JSON-friendly) com todos os campos."""
        return {
            "nome": self.nome,
            "thrust_curve_path": self.thrust_curve_path,
            "case_inner_radius": self.case_inner_radius,
            "case_wall_thickness": self.case_wall_thickness,
            "case_density": self.case_density,
            "grains": [
                {
                    "length": g.length,
                    "outer_radius": g.outer_radius,
                    "inner_radius": g.inner_radius,
                }
                for g in self.grains
            ],
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
        }