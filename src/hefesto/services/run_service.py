"""On-demand simulation snapshot CRUD services delegating to RunStore."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from hefesto.domain import (
    AppliedOverrideAudit,
    ExecutionAuditReport,
    GrainSpec,
    MotorOverride,
    MotorPhysicalSummary,
    MotorPreset,
    MotorSpec,
    RocketSpec,
    RunSummary,
    SimulationConfig,
    SimulationResult,
)
from hefesto.physics import derive_component_properties
from hefesto.services.asset_service import resolve_paths
from hefesto.services.catalog_service import (
    list_motors,
    list_rockets,
    load_motor_preset,
)
from hefesto.services.motor_service import (
    build_motor_spec,
    inspect_saved_motor,
    list_available_motor_overrides,
    summarize_motor_physical_metrics,
)
from hefesto.services.rocket_service import load_rocket_spec
from hefesto.storage import RunStore, resolve_safe_relative_path, validate_safe_slug


def _normalize_run_id(run_id: str) -> str:
    stripped = run_id.strip()
    stem = stripped.removesuffix(".json") if stripped.endswith(".json") else stripped
    return validate_safe_slug(stem, "run_id")


def save_run_snapshot(
    result: SimulationResult,
    repo_root: Path | str | None = None,
) -> RunSummary:
    """Persist a SimulationResult snapshot on demand and return its RunSummary."""
    return RunStore(resolve_paths(repo_root)).save_run(result)


def list_run_snapshots(repo_root: Path | str | None = None) -> tuple[RunSummary, ...]:
    """List saved run snapshots newest-first without creating data/runs/."""
    return RunStore(resolve_paths(repo_root)).list_runs()


def load_run_snapshot(
    run_id: str,
    repo_root: Path | str | None = None,
) -> SimulationResult:
    """Load a saved SimulationResult snapshot by run_id without creating data/runs/."""
    return RunStore(resolve_paths(repo_root)).load_run(run_id)


def delete_run_snapshot(
    run_id: str,
    repo_root: Path | str | None = None,
) -> None:
    """Delete a saved run snapshot by run_id without creating data/runs/."""
    slug = _normalize_run_id(run_id)
    store = RunStore(resolve_paths(repo_root))
    if not store.runs_dir.is_dir():
        raise FileNotFoundError(f"Run snapshot not found: {slug!r}")
    target = resolve_safe_relative_path(store.runs_dir, f"{slug}.json")
    if not target.is_file():
        raise FileNotFoundError(f"Run snapshot not found: {slug!r}")
    target.unlink()


def _values_differ(base_value: float | int | str | None, applied_value: float | int | str) -> bool:
    if base_value is None:
        return True
    if isinstance(base_value, (int, float)) and isinstance(applied_value, (int, float)):
        return abs(float(base_value) - float(applied_value)) > 1e-12
    return str(base_value).strip() != str(applied_value).strip()


def _detect_rocket_modifications(
    executed_rocket: RocketSpec,
    base_rocket: RocketSpec,
    *,
    mass_mode: Literal["calculated", "measured"],
) -> tuple[bool, tuple[str, ...]]:
    notes: list[str] = []
    if len(executed_rocket.components) != len(base_rocket.components):
        notes.append(
            f"Quantidade de componentes: {len(executed_rocket.components)} "
            f"(preset: {len(base_rocket.components)})"
        )
    elif executed_rocket.components != base_rocket.components:
        notes.append("Dimensões, massas ou posições dos componentes alteradas")
    if executed_rocket.fins != base_rocket.fins:
        notes.append("Geometria ou posição das aletas alterada")
    if executed_rocket.nose_cone != base_rocket.nose_cone:
        notes.append("Ogiva alterada")
    if executed_rocket.parachutes != base_rocket.parachutes:
        notes.append("Configuração de paraquedas alterada")
    if (
        mass_mode == "measured"
        and executed_rocket.dry_mass_override_kg != base_rocket.dry_mass_override_kg
    ):
        notes.append(
            f"Massa seca medida sobrescrita para {executed_rocket.dry_mass_override_kg} kg"
        )
    return (bool(notes), tuple(notes))


def build_execution_audit_report(
    result: SimulationResult,
    config: SimulationConfig | None = None,
    *,
    repo_root: Path | str | None = None,
) -> ExecutionAuditReport:
    """Build a typed 'Saved Preset vs. Executed Snapshot' audit report."""
    effective_config = config if config is not None else result.executed_config
    motor_id = result.motor_name
    available_motors = list_motors(repo_root=repo_root)
    base_motor_preset: MotorPreset | None = (
        load_motor_preset(motor_id, repo_root=repo_root) if motor_id in available_motors else None
    )

    if base_motor_preset is not None:
        has_ric = base_motor_preset.motor_asset is not None
        has_eng = base_motor_preset.thrust_curve_asset is not None
        if has_ric and has_eng:
            source_kind: Literal["ric_and_eng", "ric_only", "eng_only"] = "ric_and_eng"
        elif has_ric:
            source_kind = "ric_only"
        else:
            source_kind = "eng_only"
        motor_asset = base_motor_preset.motor_asset
        thrust_curve_asset = base_motor_preset.thrust_curve_asset
    else:
        exec_motor = (
            effective_config.mission.rocket.motor if effective_config is not None else None
        )
        motor_asset = exec_motor.motor_asset if exec_motor is not None else None
        thrust_curve_asset = exec_motor.thrust_curve_asset if exec_motor is not None else None
        if motor_asset is not None and thrust_curve_asset is not None:
            source_kind = "ric_and_eng"
        elif motor_asset is not None:
            source_kind = "ric_only"
        else:
            source_kind = "eng_only"

    base_options_by_path = (
        {
            opt.path: opt
            for opt in list_available_motor_overrides(
                base_motor_preset.model_copy(update={"overrides": ()}),
                repo_root=repo_root,
            )
        }
        if base_motor_preset is not None and base_motor_preset.motor_asset is not None
        else {}
    )

    override_entries: list[tuple[Literal["preset", "runtime"], MotorOverride]] = []
    if base_motor_preset is not None:
        for ov in base_motor_preset.overrides:
            override_entries.append(("preset", ov))
    if effective_config is not None:
        for ov in effective_config.motor_overrides:
            override_entries.append(("runtime", ov))

    applied_overrides: list[AppliedOverrideAudit] = []
    for source, ov in override_entries:
        opt = base_options_by_path.get(ov.path)
        base_value = opt.current_value if opt is not None else None
        applied_overrides.append(
            AppliedOverrideAudit(
                path=ov.path,
                label=opt.label if opt is not None else ov.path,
                unit=opt.unit if opt is not None else "-",
                source=source,
                base_value=base_value,
                applied_value=ov.value,
                changed=_values_differ(base_value, ov.value),
            )
        )

    effective_grains: tuple[GrainSpec, ...] = ()
    motor_summary: MotorPhysicalSummary | None = None
    if result.ballistics is not None:
        effective_grains = result.ballistics.grains
    elif effective_config is not None:
        effective_grains = effective_config.mission.rocket.motor.grains
    elif base_motor_preset is not None:
        effective_grains = inspect_saved_motor(motor_id, repo_root=repo_root).grains

    motor_for_summary: MotorSpec | None = (
        effective_config.mission.rocket.motor if effective_config is not None else None
    )
    if motor_for_summary is None and base_motor_preset is not None:
        motor_for_summary = build_motor_spec(
            base_motor_preset,
            overrides=effective_config.motor_overrides if effective_config is not None else (),
            repo_root=repo_root,
        )
    if motor_for_summary is not None:
        motor_summary = summarize_motor_physical_metrics(motor_for_summary, result.ballistics)

    available_rockets = list_rockets(repo_root=repo_root)
    if effective_config is not None:
        exec_rocket = effective_config.mission.rocket
        rocket_name = exec_rocket.name
        rocket_preset_id = effective_config.mission.rocket_preset_id
        if rocket_preset_id is not None and rocket_preset_id in available_rockets:
            base_rocket = load_rocket_spec(
                rocket_preset_id,
                motor=exec_rocket.motor,
                repo_root=repo_root,
            )
            rocket_modified, mod_notes = _detect_rocket_modifications(
                exec_rocket,
                base_rocket,
                mass_mode=effective_config.mass_mode,
            )
        else:
            rocket_modified = False
            if rocket_preset_id is not None:
                mod_notes = (
                    f"Preset de origem '{rocket_preset_id}' não encontrado no catálogo; "
                    "comparação por ID indisponível",
                )
            else:
                mod_notes = (
                    "Preset de origem não registrado na configuração executada; "
                    "comparação por ID indisponível",
                )

        nose = exec_rocket.nose_cone
        nose_summary = (
            f"{nose.name} (nose_cone @ {nose.position_m:.3f} m"
            f" · {nose.kind.value} · L={nose.length_m:.3f} m)",
        )
        components_summary = nose_summary + tuple(
            f"{comp.name} ({comp.kind} @ {comp.position_m:.3f} m) — "
            f"{derive_component_properties(comp, exec_rocket.radius_m).mass_kg:.3f} kg"
            for comp in exec_rocket.components
        )
        fins = exec_rocket.fins
        fins_summary = (
            f"{fins.count} aletas · pos={fins.position_m:.3f} m · cant={fins.cant_angle_deg:.1f}°"
        )
        mass_mode = effective_config.mass_mode
        dry_mass_override_kg = exec_rocket.dry_mass_override_kg
        fin_geometry_mode = effective_config.fin_geometry_mode
        drag_factor = effective_config.drag_factor
        thrust_factor = effective_config.thrust_factor
        environment_name = effective_config.mission.environment.name
        atmosphere_asset = effective_config.mission.environment.atmosphere_asset
    else:
        rocket_name = result.mission_name
        rocket_preset_id = None
        rocket_modified = False
        mod_notes = (
            "Configuração executada não disponível no snapshot; identidade do preset "
            "não verificável",
        )
        components_summary = ()
        fins_summary = ""
        mass_mode = "calculated"
        dry_mass_override_kg = None
        fin_geometry_mode = "freeform"
        drag_factor = 1.0
        thrust_factor = 1.0
        environment_name = ""
        atmosphere_asset = ""

    return ExecutionAuditReport(
        run_id=result.run_id,
        mission_name=result.mission_name,
        motor_preset_id=motor_id,
        motor_source_kind=source_kind,
        motor_asset=motor_asset,
        thrust_curve_asset=thrust_curve_asset,
        applied_overrides=tuple(applied_overrides),
        effective_grains=effective_grains,
        motor_summary=motor_summary,
        rocket_name=rocket_name,
        rocket_preset_id=rocket_preset_id,
        rocket_modified_in_session=rocket_modified,
        rocket_modification_notes=mod_notes,
        mass_mode=mass_mode,
        effective_dry_mass_kg=result.flight.dry_mass_kg,
        dry_mass_override_kg=dry_mass_override_kg,
        fin_geometry_mode=fin_geometry_mode,
        drag_factor=drag_factor,
        thrust_factor=thrust_factor,
        environment_name=environment_name,
        atmosphere_asset=atmosphere_asset,
        components_summary=components_summary,
        fins_summary=fins_summary,
    )


__all__ = [
    "build_execution_audit_report",
    "delete_run_snapshot",
    "list_run_snapshots",
    "load_run_snapshot",
    "save_run_snapshot",
]
