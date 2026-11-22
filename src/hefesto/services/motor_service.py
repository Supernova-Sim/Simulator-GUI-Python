"""Motor ballistics, override validation, casing recalculation, and safety services."""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from hefesto.adapters import (
    CONFIG_PROPERTY_CONSTRAINTS,
    GRAIN_PROPERTY_CONSTRAINTS,
    NOZZLE_PROPERTY_CONSTRAINTS,
    PROPELLANT_PROPERTY_CONSTRAINTS,
    PROPELLANT_TAB_PROPERTY_CONSTRAINTS,
    OpenMotorAlert,
    OpenMotorSimulationError,
    PropertyConstraint,
    PropertyKind,
    extract_grains_from_props,
    load_ric_props,
    run_openmotor_ric,
    validate_override,
)
from hefesto.domain import (
    AssetCategory,
    BallisticsResult,
    MotorCasingSpec,
    MotorOverride,
    MotorOverrideOption,
    MotorOverrideValueType,
    MotorPhysicalSummary,
    MotorPreset,
    MotorSpec,
    NozzleSpec,
    SafetyLimits,
    SafetyReport,
    SavedMotorInspection,
)
from hefesto.physics import (
    evaluate_motor_safety,
    prepare_solid_motor,
    recalculate_casing_dry_properties,
    summarize_thrust_curve,
    validate_grain_casing_fit,
)
from hefesto.services.asset_service import (
    DEFAULT_MOTOR_ID,
    load_thrust_curve_asset,
    resolve_asset_path,
    resolve_paths,
)
from hefesto.storage import CatalogStore


class ServiceAlert(BaseModel):
    """Structured simulation alert exposed by services without adapter coupling."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    level: Literal["error", "warning", "message"]
    category: str
    description: str
    location: str | None = None


class SimulationServiceError(RuntimeError):
    """Picklable service-layer error isolating OpenMotor/RocketPy/NetCDF failures."""

    def __init__(
        self,
        message: str,
        alerts: tuple[ServiceAlert, ...] = (),
        stage: str = "simulation",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.alerts = tuple(alerts)
        self.stage = stage

    def __reduce__(
        self,
    ) -> tuple[
        type[SimulationServiceError],
        tuple[str, tuple[ServiceAlert, ...], str],
    ]:
        return (type(self), (self.message, self.alerts, self.stage))


def _convert_alerts(alerts: tuple[OpenMotorAlert, ...]) -> tuple[ServiceAlert, ...]:
    return tuple(
        ServiceAlert(
            level=alert.level,
            category=alert.category,
            description=alert.description,
            location=alert.location,
        )
        for alert in alerts
    )


def combine_motor_overrides(
    preset_overrides: tuple[MotorOverride, ...] = (),
    runtime_overrides: tuple[MotorOverride, ...] = (),
) -> tuple[MotorOverride, ...]:
    """Combine preset overrides with runtime SimulationConfig overrides."""
    return (*preset_overrides, *runtime_overrides)


def validate_motor_overrides(
    overrides: tuple[MotorOverride, ...],
    *,
    has_motor_asset: bool,
    motor_name: str = "",
) -> None:
    """Validate OpenMotor overrides and reject overrides when motor_asset is None."""
    if overrides and not has_motor_asset:
        label = motor_name or "unknown"
        raise ValueError(
            f"Motor '{label}' has no .ric motor_asset; motor_overrides cannot be applied"
        )
    for override in overrides:
        validate_override(override)


def recalculate_casing(
    casing: MotorCasingSpec,
    *,
    base_casing: MotorCasingSpec | None = None,
) -> MotorCasingSpec:
    """Recalculate dry mass and inertia when casing shell geometry or mass changes."""
    if base_casing is None:
        return casing
    # Preserve pre-computed dry_mass_kg from resize_motor_casing or manual edits.
    if casing.dry_mass_kg != base_casing.dry_mass_kg or casing.material_density_kg_m3 is not None:
        return recalculate_casing_dry_properties(casing, base_casing=None)
    dims_changed = (
        casing.inner_radius_m != base_casing.inner_radius_m
        or casing.wall_thickness_m != base_casing.wall_thickness_m
        or casing.length_m != base_casing.length_m
    )
    if dims_changed:
        return recalculate_casing_dry_properties(casing, base_casing=base_casing)
    return recalculate_casing_dry_properties(casing, base_casing=base_casing)


def run_motor_ballistics(
    motor_asset: str,
    overrides: tuple[MotorOverride, ...] = (),
    *,
    motor_name: str | None = None,
    repo_root: Path | str | None = None,
) -> BallisticsResult:
    """Execute OpenMotor .ric internal ballistics and isolate adapter exceptions."""
    validate_motor_overrides(overrides, has_motor_asset=True, motor_name=motor_name or motor_asset)
    ric_path = resolve_asset_path(AssetCategory.MOTORS, motor_asset, repo_root=repo_root)
    try:
        return run_openmotor_ric(ric_path, overrides, motor_name=motor_name)
    except OpenMotorSimulationError as exc:
        raise SimulationServiceError(
            str(exc),
            alerts=_convert_alerts(exc.alerts),
            stage="ballistics",
        ) from exc


def run_motor_ballistics_for_preset(
    motor_id: str = DEFAULT_MOTOR_ID,
    overrides: tuple[MotorOverride, ...] = (),
    *,
    repo_root: Path | str | None = None,
) -> BallisticsResult:
    """Load a MotorPreset and execute OpenMotor .ric ballistics with combined overrides."""
    preset = CatalogStore(resolve_paths(repo_root)).load_motor(motor_id)
    combined = combine_motor_overrides(preset.overrides, overrides)
    validate_motor_overrides(
        combined,
        has_motor_asset=preset.motor_asset is not None,
        motor_name=preset.name,
    )
    if preset.motor_asset is None:
        raise ValueError(f"Motor preset '{motor_id}' has no .ric motor_asset")
    return run_motor_ballistics(
        preset.motor_asset,
        combined,
        motor_name=preset.name,
        repo_root=repo_root,
    )


def _nozzle_from_ballistics(
    preset_nozzle: NozzleSpec | None,
    ballistics: BallisticsResult,
    nozzle_position_m: float,
) -> NozzleSpec:
    if preset_nozzle is not None:
        return preset_nozzle.model_copy(
            update={
                "throat_radius_m": ballistics.throat_radius_m,
                "exit_radius_m": ballistics.nozzle_exit_radius_m,
            }
        )
    return NozzleSpec(
        throat_radius_m=ballistics.throat_radius_m,
        exit_radius_m=ballistics.nozzle_exit_radius_m,
        position_m=nozzle_position_m,
    )


def build_motor_spec(
    preset: MotorPreset,
    *,
    overrides: tuple[MotorOverride, ...] = (),
    casing: MotorCasingSpec | None = None,
    simulate_ric: bool = False,
    repo_root: Path | str | None = None,
) -> MotorSpec:
    """Assemble an in-memory MotorSpec from a MotorPreset and optional overrides/casing."""
    combined = combine_motor_overrides(preset.overrides, overrides)
    validate_motor_overrides(
        combined,
        has_motor_asset=preset.motor_asset is not None,
        motor_name=preset.name,
    )
    target_casing = (
        preset.casing if casing is None else recalculate_casing(casing, base_casing=preset.casing)
    )

    if (simulate_ric or preset.thrust_curve_asset is None or combined) and (
        preset.motor_asset is not None
    ):
        ballistics = run_motor_ballistics(
            preset.motor_asset,
            combined,
            motor_name=preset.name,
            repo_root=repo_root,
        )
        return MotorSpec(
            name=preset.name,
            grains=ballistics.grains,
            grain_separation_m=preset.grain_separation_m,
            grains_center_of_mass_m=preset.grains_center_of_mass_m,
            propellant_name=preset.propellant_name,
            propellant_density_kg_m3=ballistics.propellant_density_kg_m3,
            nozzle=_nozzle_from_ballistics(preset.nozzle, ballistics, preset.nozzle_position_m),
            casing=target_casing,
            burn_time_s=ballistics.burn_time_s,
            thrust_curve=ballistics.thrust_curve,
            motor_asset=preset.motor_asset,
            thrust_curve_asset=preset.thrust_curve_asset,
        )

    if preset.thrust_curve_asset is None:
        raise ValueError(f"MotorPreset '{preset.name}' has neither thrust_curve_asset nor .ric")
    if preset.nozzle is None:
        raise ValueError(f"MotorPreset '{preset.name}' requires nozzle when .ric is not simulated")
    if preset.propellant_density_kg_m3 is None:
        raise ValueError(
            f"MotorPreset '{preset.name}' requires propellant_density_kg_m3 when .ric is not run"
        )
    if not preset.fallback_grains:
        raise ValueError(
            f"MotorPreset '{preset.name}' requires fallback_grains when .ric is not run"
        )

    thrust_curve = load_thrust_curve_asset(preset.thrust_curve_asset, repo_root=repo_root)
    burn_time_s = (
        preset.burn_time_s
        if preset.burn_time_s is not None
        else (thrust_curve[0][0], thrust_curve[-1][0])
    )
    return MotorSpec(
        name=preset.name,
        grains=preset.fallback_grains,
        grain_separation_m=preset.grain_separation_m,
        grains_center_of_mass_m=preset.grains_center_of_mass_m,
        propellant_name=preset.propellant_name,
        propellant_density_kg_m3=preset.propellant_density_kg_m3,
        nozzle=preset.nozzle,
        casing=target_casing,
        burn_time_s=burn_time_s,
        thrust_curve=thrust_curve,
        motor_asset=preset.motor_asset,
        thrust_curve_asset=preset.thrust_curve_asset,
    )


def load_motor_spec(
    motor_id: str = DEFAULT_MOTOR_ID,
    *,
    overrides: tuple[MotorOverride, ...] = (),
    casing: MotorCasingSpec | None = None,
    simulate_ric: bool = False,
    repo_root: Path | str | None = None,
) -> MotorSpec:
    """Load a MotorPreset by ID and build its in-memory MotorSpec."""
    preset = CatalogStore(resolve_paths(repo_root)).load_motor(motor_id)
    return build_motor_spec(
        preset,
        overrides=overrides,
        casing=casing,
        simulate_ric=simulate_ric,
        repo_root=repo_root,
    )


def _try_load_motor_preset(
    motor_name: str,
    *,
    repo_root: Path | str | None = None,
) -> MotorPreset | None:
    store = CatalogStore(resolve_paths(repo_root))
    if motor_name in store.list_motors():
        return store.load_motor(motor_name)
    return None


def resolve_motor_for_simulation(
    motor: MotorSpec,
    *,
    runtime_overrides: tuple[MotorOverride, ...] = (),
    base_preset: MotorPreset | None = None,
    repo_root: Path | str | None = None,
) -> tuple[MotorSpec, BallisticsResult | None]:
    """Resolve OpenMotor ballistics, casing dry properties, and blocking grain-fit checks."""
    preset = (
        base_preset
        if base_preset is not None
        else _try_load_motor_preset(motor.name, repo_root=repo_root)
    )
    preset_overrides = preset.overrides if preset is not None else ()
    combined = combine_motor_overrides(preset_overrides, runtime_overrides)
    validate_motor_overrides(
        combined,
        has_motor_asset=motor.motor_asset is not None,
        motor_name=motor.name,
    )

    # Catch direct in-memory MotorSpec grain/casing overflows before running OpenMotor.
    if not combined:
        validate_grain_casing_fit(motor)

    if motor.motor_asset is not None:
        ballistics = run_motor_ballistics(
            motor.motor_asset,
            combined,
            motor_name=motor.name,
            repo_root=repo_root,
        )
        candidate_motor = motor.model_copy(
            update={
                "grains": ballistics.grains,
                "propellant_density_kg_m3": ballistics.propellant_density_kg_m3,
                "nozzle": _nozzle_from_ballistics(
                    motor.nozzle, ballistics, motor.nozzle.position_m
                ),
                "burn_time_s": ballistics.burn_time_s,
                "thrust_curve": ballistics.thrust_curve,
            }
        )
    else:
        ballistics = None
        candidate_motor = motor

    # Enforce grain-casing fit before recalculating shell mass so overflow raises directly.
    validate_grain_casing_fit(candidate_motor)

    base_casing = preset.casing if preset is not None else None
    resolved_casing = recalculate_casing(candidate_motor.casing, base_casing=base_casing)
    resolved_motor = candidate_motor.model_copy(update={"casing": resolved_casing})
    prepare_solid_motor(resolved_motor)
    return resolved_motor, ballistics


_NOZZLE_METADATA: dict[str, tuple[str, str]] = {
    "throat": ("Diâmetro da Garganta", "m"),
    "exit": ("Diâmetro de Saída da Tubeira", "m"),
    "throatLength": ("Comprimento da Garganta", "m"),
    "convAngle": ("Ângulo de Convergência", "deg"),
    "divAngle": ("Ângulo de Divergência", "deg"),
    "efficiency": ("Eficiência da Tubeira", "-"),
    "erosionCoeff": ("Coeficiente de Erosão", "m/s"),
    "slagCoeff": ("Coeficiente de Escória", "-"),
}

_GRAIN_METADATA: dict[str, tuple[str, str]] = {
    "diameter": ("Diâmetro Externo do Grão", "m"),
    "coreDiameter": ("Diâmetro do Furo (Core)", "m"),
    "length": ("Comprimento do Grão", "m"),
    "inhibitedEnds": ("Faces Inibidas", "-"),
    "numFins": ("Número de Aletas do Grão", "-"),
    "finWidth": ("Largura da Aleta do Grão", "m"),
    "finLength": ("Comprimento da Aleta do Grão", "m"),
    "invertedFins": ("Aletas Invertidas", "-"),
    "coreOffset": ("Deslocamento do Core", "m"),
    "numPoints": ("Número de Pontos da Estrela", "-"),
    "pointLength": ("Comprimento da Ponta", "m"),
    "pointWidth": ("Largura da Ponta", "m"),
    "slotWidth": ("Largura da Fenda", "m"),
    "slotLength": ("Comprimento da Fenda", "m"),
    "slotOffset": ("Deslocamento da Fenda", "m"),
    "rodDiameter": ("Diâmetro da Haste", "m"),
    "supportDiameter": ("Diâmetro do Suporte", "m"),
    "forwardCoreDiameter": ("Diâmetro Core Dianteiro", "m"),
    "aftCoreDiameter": ("Diâmetro Core Traseiro", "m"),
    "dxfUnit": ("Unidade DXF", "-"),
}

_PROPELLANT_METADATA: dict[str, tuple[str, str]] = {
    "name": ("Nome do Propelente", "-"),
    "density": ("Densidade do Propelente", "kg/m³"),
}

_PROPELLANT_TAB_METADATA: dict[str, tuple[str, str]] = {
    "minPressure": ("Pressão Mínima da Faixa", "Pa"),
    "maxPressure": ("Pressão Máxima da Faixa", "Pa"),
    "a": ("Coeficiente de Queima (a)", "m/(s·Pa^n)"),
    "n": ("Expoente de Queima (n)", "-"),
    "k": ("Razão de Calores Específicos (k)", "-"),
    "t": ("Temperatura de Combustão (T)", "K"),
    "m": ("Massa Molar dos Gases (M)", "g/mol"),
}

_CONFIG_METADATA: dict[str, tuple[str, str]] = {
    "maxPressure": ("Pressão Máxima Configurada", "Pa"),
    "maxMassFlux": ("Fluxo Mássico Máximo", "kg/(m²·s)"),
    "maxMachNumber": ("Mach Máximo no Pórtico", "-"),
    "minPortThroat": ("Razão Porta/Garganta Mín.", "-"),
    "flowSeparationWarnPercent": ("Alerta de Separação de Escoamento", "-"),
    "burnoutWebThres": ("Limiar de Web no Burnout", "m"),
    "burnoutThrustThres": ("Limiar de Empuxo no Burnout", "N"),
    "timestep": ("Passo de Integração", "s"),
    "ambPressure": ("Pressão Ambiente", "Pa"),
    "mapDim": ("Resolução do Mapa de Grão", "-"),
    "sepPressureRatio": ("Razão de Pressão de Separação", "-"),
}


def _to_override_value_type(kind: PropertyKind) -> MotorOverrideValueType | None:
    if kind == PropertyKind.FLOAT:
        return "float"
    if kind == PropertyKind.INT:
        return "int"
    if kind in {PropertyKind.ENUM, PropertyKind.STRING}:
        return "str"
    return None


def _coerce_current_value(
    raw: object,
    value_type: MotorOverrideValueType,
) -> float | int | str | None:
    if raw is None or isinstance(raw, bool):
        return None
    if value_type == "float" and isinstance(raw, (int, float)):
        val = float(raw)
        return val if math.isfinite(val) else None
    if value_type == "int" and isinstance(raw, int):
        return raw
    if value_type == "str" and isinstance(raw, str):
        return raw
    return None


def _build_section_options(
    *,
    prefix: str,
    group: Literal["nozzle", "grain", "propellant", "config"],
    constraints: Mapping[str, PropertyConstraint],
    metadata: Mapping[str, tuple[str, str]],
    values_map: Mapping[str, object] | None,
    label_prefix: str = "",
) -> list[MotorOverrideOption]:
    options: list[MotorOverrideOption] = []
    for prop_name, constraint in constraints.items():
        value_type = _to_override_value_type(constraint.kind)
        if value_type is None:
            continue
        label, unit = metadata.get(prop_name, (prop_name, "-"))
        full_label = f"{label_prefix}{label}" if label_prefix else label
        current_value = (
            _coerce_current_value(values_map.get(prop_name), value_type)
            if values_map is not None
            else None
        )
        options.append(
            MotorOverrideOption(
                path=f"{prefix}.{prop_name}",
                label=full_label,
                group=group,
                unit=unit,
                value_type=value_type,
                current_value=current_value,
            )
        )
    return options


def list_available_motor_overrides(
    motor_preset: MotorPreset,
    *,
    repo_root: Path | str | None = None,
) -> tuple[MotorOverrideOption, ...]:
    """Return guided OpenMotor override options from validator whitelist and .ric values."""
    if motor_preset.motor_asset is None:
        return ()

    props: dict[str, object] | None = None
    try:
        ric_path = resolve_asset_path(
            AssetCategory.MOTORS,
            motor_preset.motor_asset,
            repo_root=repo_root,
        )
        props = load_ric_props(ric_path, motor_preset.overrides)
    except (FileNotFoundError, ValueError):
        props = None

    nozzle_map = props.get("nozzle") if isinstance(props, dict) else None
    propellant_map = props.get("propellant") if isinstance(props, dict) else None
    config_map = props.get("config") if isinstance(props, dict) else None
    grains_raw = props.get("grains") if isinstance(props, dict) else None

    options: list[MotorOverrideOption] = []
    options.extend(
        _build_section_options(
            prefix="nozzle",
            group="nozzle",
            constraints=NOZZLE_PROPERTY_CONSTRAINTS,
            metadata=_NOZZLE_METADATA,
            values_map=nozzle_map if isinstance(nozzle_map, Mapping) else None,
        )
    )

    if isinstance(grains_raw, list) and grains_raw:
        first_grain = grains_raw[0] if isinstance(grains_raw[0], Mapping) else {}
        first_type = str(first_grain.get("type", "BATES"))
        first_props = first_grain.get("properties")
        wildcard_constraints = GRAIN_PROPERTY_CONSTRAINTS.get(
            first_type, GRAIN_PROPERTY_CONSTRAINTS["BATES"]
        )
        options.extend(
            _build_section_options(
                prefix="grains.*.properties",
                group="grain",
                constraints=wildcard_constraints,
                metadata=_GRAIN_METADATA,
                values_map=first_props if isinstance(first_props, Mapping) else None,
                label_prefix="Todos os Grãos · ",
            )
        )
        for idx, raw_grain in enumerate(grains_raw):
            if not isinstance(raw_grain, Mapping):
                continue
            grain_type = str(raw_grain.get("type", "BATES"))
            grain_constraints = GRAIN_PROPERTY_CONSTRAINTS.get(
                grain_type, GRAIN_PROPERTY_CONSTRAINTS["BATES"]
            )
            grain_props = raw_grain.get("properties")
            options.extend(
                _build_section_options(
                    prefix=f"grains.{idx}.properties",
                    group="grain",
                    constraints=grain_constraints,
                    metadata=_GRAIN_METADATA,
                    values_map=grain_props if isinstance(grain_props, Mapping) else None,
                    label_prefix=f"Grão {idx + 1} · ",
                )
            )
    else:
        options.extend(
            _build_section_options(
                prefix="grains.*.properties",
                group="grain",
                constraints=GRAIN_PROPERTY_CONSTRAINTS["BATES"],
                metadata=_GRAIN_METADATA,
                values_map=None,
                label_prefix="Todos os Grãos · ",
            )
        )

    options.extend(
        _build_section_options(
            prefix="propellant",
            group="propellant",
            constraints=PROPELLANT_PROPERTY_CONSTRAINTS,
            metadata=_PROPELLANT_METADATA,
            values_map=propellant_map if isinstance(propellant_map, Mapping) else None,
        )
    )

    tabs_raw = propellant_map.get("tabs") if isinstance(propellant_map, Mapping) else None
    if isinstance(tabs_raw, list) and tabs_raw and isinstance(tabs_raw[0], Mapping):
        options.extend(
            _build_section_options(
                prefix="propellant.tabs.*",
                group="propellant",
                constraints=PROPELLANT_TAB_PROPERTY_CONSTRAINTS,
                metadata=_PROPELLANT_TAB_METADATA,
                values_map=tabs_raw[0],
                label_prefix="Todas as Faixas · ",
            )
        )
        for tab_idx, raw_tab in enumerate(tabs_raw):
            if not isinstance(raw_tab, Mapping):
                continue
            options.extend(
                _build_section_options(
                    prefix=f"propellant.tabs.{tab_idx}",
                    group="propellant",
                    constraints=PROPELLANT_TAB_PROPERTY_CONSTRAINTS,
                    metadata=_PROPELLANT_TAB_METADATA,
                    values_map=raw_tab,
                    label_prefix=f"Faixa {tab_idx + 1} · ",
                )
            )

    options.extend(
        _build_section_options(
            prefix="config",
            group="config",
            constraints=CONFIG_PROPERTY_CONSTRAINTS,
            metadata=_CONFIG_METADATA,
            values_map=config_map if isinstance(config_map, Mapping) else None,
        )
    )
    return tuple(options)


def summarize_motor_physical_metrics(
    motor: MotorSpec,
    ballistics: BallisticsResult | None = None,
) -> MotorPhysicalSummary:
    """Compute combined physical casing, nozzle, and internal ballistics summary."""
    dry_mass_kg = motor.casing.dry_mass_kg
    if ballistics is not None:
        propellant_mass_kg = ballistics.propellant_mass_kg
        throat_radius_m = ballistics.throat_radius_m
        exit_radius_m = ballistics.nozzle_exit_radius_m
        burn_time_s = ballistics.burn_time_s
        total_impulse_ns = ballistics.total_impulse_ns
        max_thrust_n = ballistics.max_thrust_n
        grain_count = len(ballistics.grains)
        propellant_density_kg_m3 = ballistics.propellant_density_kg_m3
        peak_chamber_pressure_pa = ballistics.peak_chamber_pressure_pa
        peak_kn = ballistics.peak_kn
        peak_mass_flux_kg_m2_s = ballistics.peak_mass_flux_kg_m2_s
        delivered_isp_s = ballistics.delivered_isp_s
        aft_port_to_throat_ratio = ballistics.aft_port_to_throat_ratio
        min_port_to_throat_ratio = ballistics.min_port_to_throat_ratio
    else:
        propellant_volume_m3 = sum(
            math.pi * (g.outer_radius_m**2 - g.inner_radius_m**2) * g.length_m
            for g in motor.grains
        )
        propellant_mass_kg = propellant_volume_m3 * motor.propellant_density_kg_m3
        throat_radius_m = motor.nozzle.throat_radius_m
        exit_radius_m = motor.nozzle.exit_radius_m
        curve_summary = summarize_thrust_curve(motor.thrust_curve)
        burn_time_s = motor.burn_time_s
        total_impulse_ns = curve_summary.total_impulse_ns
        max_thrust_n = curve_summary.max_thrust_n
        grain_count = len(motor.grains)
        propellant_density_kg_m3 = motor.propellant_density_kg_m3
        peak_chamber_pressure_pa = None
        peak_kn = None
        peak_mass_flux_kg_m2_s = None
        delivered_isp_s = None
        aft_port_to_throat_ratio = None
        min_port_to_throat_ratio = None

    total_loaded_mass_kg = dry_mass_kg + propellant_mass_kg
    propellant_mass_fraction = propellant_mass_kg / total_loaded_mass_kg
    burn_duration_s = max(burn_time_s[1] - burn_time_s[0], 1e-9)
    average_thrust_n = total_impulse_ns / burn_duration_s
    expansion_ratio = (exit_radius_m / throat_radius_m) ** 2

    return MotorPhysicalSummary(
        motor_name=motor.name,
        dry_mass_kg=dry_mass_kg,
        propellant_mass_kg=propellant_mass_kg,
        total_loaded_mass_kg=total_loaded_mass_kg,
        propellant_mass_fraction=propellant_mass_fraction,
        casing_length_m=motor.casing.length_m,
        outer_diameter_m=2.0 * motor.casing.outer_radius_m,
        throat_diameter_mm=2.0 * throat_radius_m * 1000.0,
        exit_diameter_mm=2.0 * exit_radius_m * 1000.0,
        expansion_ratio=expansion_ratio,
        burn_time_s=burn_time_s,
        burn_duration_s=burn_duration_s,
        total_impulse_ns=total_impulse_ns,
        average_thrust_n=average_thrust_n,
        max_thrust_n=max_thrust_n,
        peak_chamber_pressure_pa=peak_chamber_pressure_pa,
        peak_kn=peak_kn,
        peak_mass_flux_kg_m2_s=peak_mass_flux_kg_m2_s,
        delivered_isp_s=delivered_isp_s,
        aft_port_to_throat_ratio=aft_port_to_throat_ratio,
        min_port_to_throat_ratio=min_port_to_throat_ratio,
        grain_count=grain_count,
        propellant_density_kg_m3=propellant_density_kg_m3,
    )


def evaluate_safety(
    ballistics: BallisticsResult | None,
    casing: MotorCasingSpec | None = None,
    limits: SafetyLimits | None = None,
    *,
    motor: MotorSpec | None = None,
) -> SafetyReport:
    """Evaluate the 5 fail-closed, non-blocking motor safety criteria."""
    return evaluate_motor_safety(ballistics, casing, limits=limits, motor=motor)


def _optional_positive_float(raw: object) -> float | None:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        val = float(raw)
        if math.isfinite(val) and val > 0.0:
            return val
    return None


def _optional_angle_deg(raw: object) -> float | None:
    val = _optional_positive_float(raw)
    if val is not None and val < 90.0:
        return val
    return None


def inspect_saved_motor(
    motor_id: str = DEFAULT_MOTOR_ID,
    *,
    repo_root: Path | str | None = None,
) -> SavedMotorInspection:
    """Inspect a saved MotorPreset including casing, nozzle, propellant, and grains."""
    preset = CatalogStore(resolve_paths(repo_root)).load_motor(motor_id)
    if preset.motor_asset is not None and preset.thrust_curve_asset is not None:
        source_kind: Literal["ric_and_eng", "ric_only", "eng_only"] = "ric_and_eng"
    elif preset.motor_asset is not None:
        source_kind = "ric_only"
    else:
        source_kind = "eng_only"

    if preset.motor_asset is not None:
        ric_path = resolve_asset_path(
            AssetCategory.MOTORS,
            preset.motor_asset,
            repo_root=repo_root,
        )
        props = load_ric_props(ric_path, preset.overrides)
        grains = extract_grains_from_props(props)
        nozzle_raw = props.get("nozzle")
        propellant_raw = props.get("propellant")
        assert isinstance(nozzle_raw, Mapping)
        assert isinstance(propellant_raw, Mapping)
        throat_diam = float(nozzle_raw["throat"])
        exit_diam = float(nozzle_raw["exit"])
        efficiency_raw = nozzle_raw.get("efficiency", 1.0)
        efficiency = (
            float(efficiency_raw)
            if isinstance(efficiency_raw, (int, float)) and not isinstance(efficiency_raw, bool)
            else 1.0
        )
        nozzle = NozzleSpec(
            throat_radius_m=throat_diam / 2.0,
            exit_radius_m=exit_diam / 2.0,
            position_m=preset.nozzle_position_m,
            throat_length_m=_optional_positive_float(nozzle_raw.get("throatLength")),
            converging_angle_deg=_optional_angle_deg(nozzle_raw.get("convAngle")),
            diverging_angle_deg=_optional_angle_deg(nozzle_raw.get("divAngle")),
            efficiency=min(max(efficiency, 1e-6), 1.0),
        )
        propellant_density_kg_m3 = float(propellant_raw["density"])
        raw_prop_name = propellant_raw.get("name")
        propellant_name = (
            raw_prop_name.strip()
            if isinstance(raw_prop_name, str) and raw_prop_name.strip()
            else preset.propellant_name
        )
    else:
        if preset.nozzle is None or preset.propellant_density_kg_m3 is None:
            raise ValueError(
                f"Motor preset '{motor_id}' requires nozzle and propellant_density_kg_m3"
            )
        if not preset.fallback_grains:
            raise ValueError(f"Motor preset '{motor_id}' requires fallback_grains")
        nozzle = preset.nozzle
        grains = preset.fallback_grains
        propellant_density_kg_m3 = preset.propellant_density_kg_m3
        propellant_name = preset.propellant_name

    return SavedMotorInspection(
        preset_id=motor_id,
        name=preset.name,
        source_kind=source_kind,
        motor_asset=preset.motor_asset,
        thrust_curve_asset=preset.thrust_curve_asset,
        casing=preset.casing,
        casing_outer_diameter_m=2.0 * preset.casing.outer_radius_m,
        propellant_name=propellant_name,
        propellant_density_kg_m3=propellant_density_kg_m3,
        nozzle=nozzle,
        grains=grains,
        grain_separation_m=preset.grain_separation_m,
        grains_center_of_mass_m=preset.grains_center_of_mass_m,
        preset_overrides=preset.overrides,
    )


__all__ = [
    "ServiceAlert",
    "SimulationServiceError",
    "build_motor_spec",
    "combine_motor_overrides",
    "evaluate_safety",
    "inspect_saved_motor",
    "list_available_motor_overrides",
    "load_motor_spec",
    "recalculate_casing",
    "resolve_motor_for_simulation",
    "run_motor_ballistics",
    "run_motor_ballistics_for_preset",
    "summarize_motor_physical_metrics",
    "validate_motor_overrides",
]
