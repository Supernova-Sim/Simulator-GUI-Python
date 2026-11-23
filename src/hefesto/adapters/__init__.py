"""External integration layer: OpenMotor, RocketPy, OpenRocket, and RASAero adapters.

All third-party simulator calls are isolated and translated into domain models, so
no other layer imports rocketpy/openmotor/motorlib/uilib. Only services consume it;
adapters import only hefesto.domain and hefesto.adapters.
"""

from __future__ import annotations

from hefesto.adapters.aerodynamics import (
    DatabaseDragModel,
    DragModelProtocol,
    parse_rasaero_csv_file,
    parse_rasaero_csv_text,
)
from hefesto.adapters.openmotor import (
    CONFIG_PROPERTY_CONSTRAINTS,
    GRAIN_PROPERTY_CONSTRAINTS,
    NOZZLE_PROPERTY_CONSTRAINTS,
    PROPELLANT_PROPERTY_CONSTRAINTS,
    PROPELLANT_TAB_PROPERTY_CONSTRAINTS,
    OpenMotorAlert,
    OpenMotorSimulationError,
    OpenMotorSimulationResult,
    PropertyConstraint,
    PropertyKind,
    apply_overrides_to_props,
    extract_grains_from_props,
    load_ric_props,
    run_openmotor_ric,
    simulate_ric_detailed,
    validate_override,
    validate_ric_dict,
)
from hefesto.adapters.openrocket import (
    OrkParseError,
    parse_ork_bytes,
    parse_ork_file,
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
    "CONFIG_PROPERTY_CONSTRAINTS",
    "DatabaseDragModel",
    "DragModelProtocol",
    "GRAIN_PROPERTY_CONSTRAINTS",
    "NOZZLE_PROPERTY_CONSTRAINTS",
    "OpenMotorAlert",
    "OpenMotorSimulationError",
    "OpenMotorSimulationResult",
    "OrkParseError",
    "OutputSelection",
    "PROPELLANT_PROPERTY_CONSTRAINTS",
    "PROPELLANT_TAB_PROPERTY_CONSTRAINTS",
    "PropertyConstraint",
    "PropertyKind",
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
    "parse_ork_bytes",
    "parse_ork_file",
    "parse_rasaero_csv_file",
    "parse_rasaero_csv_text",
    "run_flight",
    "run_openmotor_ric",
    "simulate_ric_detailed",
    "validate_motor_geometry_fit",
    "validate_override",
    "validate_ric_dict",
]
