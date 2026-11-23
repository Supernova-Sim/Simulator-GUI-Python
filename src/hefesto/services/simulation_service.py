"""Mission composition and picklable deterministic simulation orchestration services."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hefesto.adapters import run_flight
from hefesto.domain import (
    AssetCategory,
    BallisticsResult,
    FinGeometryMode,
    GeometryValidationError,
    LaunchConfig,
    MassMode,
    MissionSpec,
    MotorCasingSpec,
    MotorOverride,
    OutputSelection,
    RocketSpec,
    SafetyReport,
    SimulationConfig,
    SimulationResult,
)
from hefesto.services.asset_service import resolve_asset_path
from hefesto.services.catalog_service import (
    DEFAULT_LIMITS_ID,
    DEFAULT_MOTOR_ID,
    DEFAULT_ROCKET_ID,
    DEFAULT_SITE_ID,
    load_limits_preset,
    load_mission_preset,
    load_rocket_preset,
    load_site_preset,
)
from hefesto.services.motor_service import (
    SimulationServiceError,
    evaluate_safety,
    load_motor_spec,
    resolve_motor_for_simulation,
    run_motor_ballistics_for_preset,
)
from hefesto.services.rocket_service import build_rocket_spec


def build_mission_from_selection(
    rocket_id: str = DEFAULT_ROCKET_ID,
    motor_id: str | None = DEFAULT_MOTOR_ID,
    site_id: str = DEFAULT_SITE_ID,
    limits_id: str = DEFAULT_LIMITS_ID,
    *,
    launch: LaunchConfig | None = None,
    mission_name: str | None = None,
    rocket_spec: RocketSpec | None = None,
    repo_root: Path | str | None = None,
) -> MissionSpec:
    """Compose a MissionSpec from explicit catalog preset IDs or an in-memory RocketSpec."""
    if rocket_spec is not None:
        if motor_id is not None and motor_id != rocket_spec.motor.name:
            resolved_motor = load_motor_spec(motor_id, repo_root=repo_root)
            resolved_rocket = rocket_spec.model_copy(update={"motor": resolved_motor})
        else:
            resolved_rocket = rocket_spec
        resolved_motor_id = resolved_rocket.motor.name
    else:
        rocket_preset = load_rocket_preset(rocket_id, repo_root=repo_root)
        resolved_motor_id = rocket_preset.motor_preset_name if motor_id is None else motor_id
        motor_spec = load_motor_spec(resolved_motor_id, repo_root=repo_root)
        resolved_rocket = build_rocket_spec(rocket_preset, motor=motor_spec, repo_root=repo_root)

    environment = load_site_preset(site_id, repo_root=repo_root)
    safety_limits = load_limits_preset(limits_id, repo_root=repo_root)
    resolved_name = (
        f"{resolved_rocket.name}_{resolved_motor_id}_{site_id}"
        if mission_name is None
        else mission_name
    )

    return MissionSpec(
        name=resolved_name,
        rocket=resolved_rocket,
        environment=environment,
        launch=LaunchConfig() if launch is None else launch,
        safety_limits=safety_limits,
    )


def build_mission_from_preset(
    mission_id: str,
    *,
    motor_id: str | None = None,
    limits_id: str | None = None,
    repo_root: Path | str | None = None,
) -> MissionSpec:
    """Compose a MissionSpec from a persisted MissionPreset in data/catalog/missions/."""
    mission_preset = load_mission_preset(mission_id, repo_root=repo_root)
    rocket_preset = load_rocket_preset(mission_preset.rocket_preset_name, repo_root=repo_root)
    resolved_motor_id = rocket_preset.motor_preset_name if motor_id is None else motor_id
    motor_spec = load_motor_spec(resolved_motor_id, repo_root=repo_root)
    rocket_spec = build_rocket_spec(rocket_preset, motor=motor_spec, repo_root=repo_root)
    environment = load_site_preset(mission_preset.environment_preset_name, repo_root=repo_root)
    safety_limits = (
        mission_preset.safety_limits
        if limits_id is None
        else load_limits_preset(limits_id, repo_root=repo_root)
    )

    return MissionSpec(
        name=mission_preset.name,
        rocket=rocket_spec,
        environment=environment,
        launch=mission_preset.launch,
        safety_limits=safety_limits,
        atmosphere=mission_preset.atmosphere,
    )


def compose_simulation_config(
    *,
    mission_id: str | None = None,
    rocket_id: str = DEFAULT_ROCKET_ID,
    motor_id: str | None = None,
    site_id: str = DEFAULT_SITE_ID,
    limits_id: str = DEFAULT_LIMITS_ID,
    launch: LaunchConfig | None = None,
    mass_mode: MassMode = "calculated",
    fin_geometry_mode: FinGeometryMode = "freeform",
    drag_factor: float = 1.0,
    thrust_factor: float = 1.0,
    motor_overrides: tuple[MotorOverride, ...] = (),
    output_selection: OutputSelection | None = None,
    rocket_spec: RocketSpec | None = None,
    repo_root: Path | str | None = None,
) -> SimulationConfig:
    """Build a picklable SimulationConfig from either MissionPreset or explicit selection."""
    if mission_id is not None and rocket_spec is None:
        mission = build_mission_from_preset(
            mission_id,
            motor_id=motor_id,
            repo_root=repo_root,
        )
        if launch is not None:
            mission = mission.model_copy(update={"launch": launch})
    else:
        mission = build_mission_from_selection(
            rocket_id=rocket_id,
            motor_id=motor_id,
            site_id=site_id,
            limits_id=limits_id,
            launch=launch,
            rocket_spec=rocket_spec,
            repo_root=repo_root,
        )

    return SimulationConfig(
        mission=mission,
        mass_mode=mass_mode,
        fin_geometry_mode=fin_geometry_mode,
        drag_factor=drag_factor,
        thrust_factor=thrust_factor,
        motor_overrides=motor_overrides,
        output_selection=OutputSelection.all() if output_selection is None else output_selection,
    )


def run_deterministic(
    config: SimulationConfig,
    repo_root: Path | str | None = None,
) -> SimulationResult:
    """Execute ballistics, blocking fit guards, non-blocking safety, and 6-DOF flight."""
    if config.mass_mode == "measured" and config.mission.rocket.dry_mass_override_kg is None:
        raise ValueError(
            "SimulationConfig with mass_mode='measured' requires "
            "mission.rocket.dry_mass_override_kg to be set"
        )

    mission = config.mission
    resolved_motor, ballistics = resolve_motor_for_simulation(
        mission.rocket.motor,
        runtime_overrides=config.motor_overrides,
        repo_root=repo_root,
    )
    safety_report = evaluate_safety(
        ballistics,
        resolved_motor.casing,
        limits=mission.safety_limits,
        motor=resolved_motor,
    )

    # ISA missions never touch the site's NetCDF file; ERA5 stays the default path.
    atmosphere_path = (
        None
        if mission.atmosphere is not None
        else resolve_asset_path(
            AssetCategory.ATMOSPHERE,
            mission.environment.atmosphere_asset,
            repo_root=repo_root,
        )
    )
    resolved_rocket = mission.rocket.model_copy(update={"motor": resolved_motor})
    resolved_mission = mission.model_copy(update={"rocket": resolved_rocket})

    try:
        flight_result = run_flight(
            resolved_mission,
            atmosphere_path,
            output_selection=config.output_selection,
            drag_factor=config.drag_factor,
            thrust_factor=config.thrust_factor,
            mass_mode=config.mass_mode,
            fin_geometry_mode=config.fin_geometry_mode,
        )
    except GeometryValidationError:
        raise
    except Exception as exc:
        raise SimulationServiceError(
            f"Flight simulation failed for '{mission.name}': {exc}",
            stage="flight",
        ) from exc

    created_at_utc = datetime.now(UTC)
    run_id = f"run_{created_at_utc:%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}"
    return SimulationResult(
        run_id=run_id,
        created_at_utc=created_at_utc,
        mission_name=mission.name,
        motor_name=resolved_motor.name,
        flight=flight_result,
        ballistics=ballistics,
        safety=safety_report,
        executed_config=config,
    )


def run_ballistics_check(
    motor_id: str = DEFAULT_MOTOR_ID,
    overrides: tuple[MotorOverride, ...] = (),
    *,
    limits_id: str = DEFAULT_LIMITS_ID,
    casing: MotorCasingSpec | None = None,
    repo_root: Path | str | None = None,
) -> tuple[BallisticsResult, SafetyReport]:
    """Run OpenMotor .ric ballistics and evaluate SafetyReport on the active casing.

    casing carries the session's edited casing (GUI); None falls back to the catalog preset.
    """
    ballistics = run_motor_ballistics_for_preset(motor_id, overrides, repo_root=repo_root)
    resolved_casing = casing
    if resolved_casing is None:
        motor_spec = load_motor_spec(
            motor_id, overrides=overrides, simulate_ric=True, repo_root=repo_root
        )
        resolved_casing = motor_spec.casing
    limits = load_limits_preset(limits_id, repo_root=repo_root)
    safety = evaluate_safety(ballistics, resolved_casing, limits=limits)
    return ballistics, safety


__all__ = [
    "build_mission_from_preset",
    "build_mission_from_selection",
    "compose_simulation_config",
    "run_ballistics_check",
    "run_deterministic",
]
