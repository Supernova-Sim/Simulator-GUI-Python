"""External simulation and aerodynamics adapter layer exports for Hefesto."""

from __future__ import annotations

from hefesto.adapters.aerodynamics import DatabaseDragModel, DragModelProtocol
from hefesto.adapters.openmotor import (
    OpenMotorAlert,
    OpenMotorSimulationError,
    OpenMotorSimulationResult,
    apply_overrides_to_props,
    extract_grains_from_props,
    load_ric_props,
    run_openmotor_ric,
    simulate_ric_detailed,
    validate_override,
    validate_ric_dict,
)
from hefesto.adapters.rocketpy import (
    OutputSelection,
    build_environment,
    build_netcdf_dictionary,
    build_rocket,
    build_solid_motor,
    compute_rocket_dry_mass_kg,
    execute_flight,
    extract_flight_result,
    run_flight,
    validate_motor_geometry_fit,
)

__all__ = [
    "DatabaseDragModel",
    "DragModelProtocol",
    "OpenMotorAlert",
    "OpenMotorSimulationError",
    "OpenMotorSimulationResult",
    "OutputSelection",
    "apply_overrides_to_props",
    "build_environment",
    "build_netcdf_dictionary",
    "build_rocket",
    "build_solid_motor",
    "compute_rocket_dry_mass_kg",
    "execute_flight",
    "extract_flight_result",
    "extract_grains_from_props",
    "load_ric_props",
    "run_flight",
    "run_openmotor_ric",
    "simulate_ric_detailed",
    "validate_motor_geometry_fit",
    "validate_override",
    "validate_ric_dict",
]
