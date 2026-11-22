"""Physical, material, geometric, and default safety constants (SI units)."""

from __future__ import annotations

from typing import Final, Literal

# Unit conversions and numerical tolerances
INCHES_PER_METER: Final[float] = 1.0 / 0.0254
METERS_PER_INCH: Final[float] = 0.0254
PA_PER_MPA: Final[float] = 1_000_000.0
STANDARD_GRAVITY_M_S2: Final[float] = 9.80665
DEFAULT_NOSE_CONE_SLICES: Final[int] = 200
DEFAULT_DERIVATIVE_STEP_M: Final[float] = 1e-7
GEOMETRY_TOLERANCE_M: Final[float] = 1e-12

# Reference material densities and manufacturing defaults
COMPOSITE_DENSITY_KG_M3: Final[float] = 1850.0
ALUMINUM_DENSITY_KG_M3: Final[float] = 2700.0
KNSB_PROPELLANT_DENSITY_KG_M3: Final[float] = 1841.0
DEFAULT_WALL_THICKNESS_M: Final[float] = 0.002
DEFAULT_FIN_THICKNESS_M: Final[float] = 0.004
DEFAULT_CASE_YIELD_STRENGTH_PA: Final[float] = 145_000_000.0

# Default motor safety thresholds (matching domain.safety.SafetyLimits)
DEFAULT_MIN_CASE_SAFETY_FACTOR: Final[float] = 2.0
DEFAULT_TARGET_CASE_SAFETY_FACTOR: Final[float] = 3.0
DEFAULT_MAX_CHAMBER_PRESSURE_PA: Final[float] = 8_000_000.0
DEFAULT_MAX_KN: Final[float] = 250.0
DEFAULT_MAX_MASS_FLUX_KG_M2_S: Final[float] = 1406.0
DEFAULT_MIN_PORT_TO_THROAT_RATIO: Final[float] = 2.0

# Coordinate system orientation literals enforced by RocketPy adapters
ROCKET_COORDINATE_SYSTEM: Final[Literal["nose_to_tail"]] = "nose_to_tail"
MOTOR_COORDINATE_SYSTEM: Final[Literal["nozzle_to_combustion_chamber"]] = (
    "nozzle_to_combustion_chamber"
)

__all__ = [
    "ALUMINUM_DENSITY_KG_M3",
    "COMPOSITE_DENSITY_KG_M3",
    "DEFAULT_CASE_YIELD_STRENGTH_PA",
    "DEFAULT_DERIVATIVE_STEP_M",
    "DEFAULT_FIN_THICKNESS_M",
    "DEFAULT_MAX_CHAMBER_PRESSURE_PA",
    "DEFAULT_MAX_KN",
    "DEFAULT_MAX_MASS_FLUX_KG_M2_S",
    "DEFAULT_MIN_CASE_SAFETY_FACTOR",
    "DEFAULT_MIN_PORT_TO_THROAT_RATIO",
    "DEFAULT_NOSE_CONE_SLICES",
    "DEFAULT_TARGET_CASE_SAFETY_FACTOR",
    "DEFAULT_WALL_THICKNESS_M",
    "GEOMETRY_TOLERANCE_M",
    "INCHES_PER_METER",
    "KNSB_PROPELLANT_DENSITY_KG_M3",
    "METERS_PER_INCH",
    "MOTOR_COORDINATE_SYSTEM",
    "PA_PER_MPA",
    "ROCKET_COORDINATE_SYSTEM",
    "STANDARD_GRAVITY_M_S2",
]
