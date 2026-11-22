"""Isolated OpenMotor (.ric) validation and internal ballistics execution adapter."""

from __future__ import annotations

from hefesto.adapters.openmotor.runner import (
    AlertLevelLiteral,
    OpenMotorAlert,
    OpenMotorSimulationError,
    OpenMotorSimulationResult,
    extract_sim_alerts,
    isolated_uilib_guard,
    load_ric_props,
    run_openmotor_ric,
    simulate_ric_detailed,
)
from hefesto.adapters.openmotor.validator import (
    CONFIG_PROPERTY_CONSTRAINTS,
    GRAIN_PROPERTY_CONSTRAINTS,
    NOZZLE_PROPERTY_CONSTRAINTS,
    PROPELLANT_PROPERTY_CONSTRAINTS,
    PROPELLANT_TAB_PROPERTY_CONSTRAINTS,
    OverrideInput,
    OverrideValue,
    PropertyConstraint,
    PropertyKind,
    apply_overrides_to_props,
    extract_grains_from_props,
    normalize_overrides,
    validate_override,
    validate_ric_dict,
)

__all__ = [
    "CONFIG_PROPERTY_CONSTRAINTS",
    "GRAIN_PROPERTY_CONSTRAINTS",
    "NOZZLE_PROPERTY_CONSTRAINTS",
    "PROPELLANT_PROPERTY_CONSTRAINTS",
    "PROPELLANT_TAB_PROPERTY_CONSTRAINTS",
    "AlertLevelLiteral",
    "OpenMotorAlert",
    "OpenMotorSimulationError",
    "OpenMotorSimulationResult",
    "OverrideInput",
    "OverrideValue",
    "PropertyConstraint",
    "PropertyKind",
    "apply_overrides_to_props",
    "extract_grains_from_props",
    "extract_sim_alerts",
    "isolated_uilib_guard",
    "load_ric_props",
    "normalize_overrides",
    "run_openmotor_ric",
    "simulate_ric_detailed",
    "validate_override",
    "validate_ric_dict",
]
