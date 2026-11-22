"""Reactive NiceGUI application state bridging hefesto.services and UI components."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from nicegui import context
from pydantic import ValidationError

from frontend.components.metrics_cards import (
    DEFAULT_BALLISTICS_METRIC_KEYS,
    DEFAULT_FLIGHT_METRIC_KEYS,
)
from hefesto.domain import (
    BallisticsResult,
    CasingResizeResult,
    CasingScalingMode,
    CatalogOverview,
    ExecutionAuditReport,
    FinGeometryMode,
    GeometryValidationError,
    LaunchConfig,
    MassMode,
    MotorOverride,
    MotorOverrideOption,
    OutputSelection,
    RocketSpec,
    RunSummary,
    SafetyReport,
    SimulationConfig,
    SimulationResult,
)
from hefesto.services import (
    DEFAULT_LIMITS_ID,
    DEFAULT_MOTOR_ID,
    DEFAULT_ROCKET_ID,
    DEFAULT_SITE_ID,
    ServiceAlert,
    SimulationServiceError,
    build_execution_audit_report,
    compose_simulation_config,
    delete_run_snapshot,
    get_catalog_overview,
    list_available_motor_overrides,
    list_limits,
    list_run_snapshots,
    load_motor_preset,
    load_motor_spec,
    load_rocket_preset,
    load_rocket_spec,
    load_run_snapshot,
    recalculate_rocket_structure,
    rocket_preset_from_spec,
    run_ballistics_check,
    run_deterministic,
    save_rocket_preset,
    save_run_snapshot,
    update_rocket_motor_casing_length,
)

_CLIENT_STATE_KEY = "hefesto_app_state"


@dataclass
class AppState:
    """In-memory UI state for mission configuration, execution, alerts, and run snapshots."""

    repo_root: str | None = None
    catalog: CatalogOverview | None = None
    selected_mission_id: str | None = None
    selected_rocket_id: str = DEFAULT_ROCKET_ID
    selected_motor_id: str | None = DEFAULT_MOTOR_ID
    selected_site_id: str = DEFAULT_SITE_ID
    selected_limits_id: str = DEFAULT_LIMITS_ID
    launch_config: LaunchConfig = field(default_factory=LaunchConfig)
    mass_mode: MassMode = "calculated"
    fin_geometry_mode: FinGeometryMode = "freeform"
    drag_factor: float = 1.0
    thrust_factor: float = 1.0
    dry_mass_override_kg: float | None = None
    motor_overrides: tuple[MotorOverride, ...] = ()
    output_selection: OutputSelection = field(default_factory=OutputSelection.all)
    working_rocket_spec: RocketSpec | None = None
    has_unsaved_rocket_changes: bool = False
    casing_scaling_mode: CasingScalingMode = "tubular_delta"
    casing_material_preset: str = "aluminum_6061_t6"
    casing_density_kg_m3: float = 2700.0
    last_casing_resize_result: CasingResizeResult | None = None
    selected_flight_metrics: tuple[str, ...] = DEFAULT_FLIGHT_METRIC_KEYS
    selected_ballistics_metrics: tuple[str, ...] = DEFAULT_BALLISTICS_METRIC_KEYS
    auto_save_runs: bool = False
    simulation_config: SimulationConfig | None = None
    current_result: SimulationResult | None = None
    current_audit_report: ExecutionAuditReport | None = None
    ballistics_preview: BallisticsResult | None = None
    safety_preview: SafetyReport | None = None
    run_summaries: tuple[RunSummary, ...] = ()
    is_running: bool = False
    last_error: str | None = None
    last_error_stage: str | None = None
    last_alerts: tuple[ServiceAlert, ...] = ()
    status_message: str = "Pronto para configurar e simular."
    _listeners: list[Callable[[], None]] = field(
        default_factory=list, repr=False, compare=False
    )

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a UI refresh callback and return an unsubscribe handle."""
        if callback not in self._listeners:
            self._listeners.append(callback)

        def _unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return _unsubscribe

    def notify(self) -> None:
        """Notify all registered UI listeners after state transitions."""
        for callback in tuple(self._listeners):
            callback()

    def clear_error(self) -> None:
        """Clear previous blocking error and structured service alerts."""
        self.last_error = None
        self.last_error_stage = None
        self.last_alerts = ()

    def set_error(
        self,
        message: str,
        *,
        stage: str = "simulation",
        alerts: tuple[ServiceAlert, ...] = (),
    ) -> None:
        """Record an error message and optional ServiceAlerts without crashing the UI."""
        self.last_error = message
        self.last_error_stage = stage
        self.last_alerts = tuple(alerts)
        self.status_message = f"Erro ({stage}): {message}"
        self.notify()

    def refresh_catalog(self) -> CatalogOverview:
        """Load CatalogOverview and keep default selections aligned with available presets."""
        overview = get_catalog_overview(repo_root=self.repo_root)
        self.catalog = overview

        if overview.rocket_presets and self.selected_rocket_id not in overview.rocket_presets:
            self.selected_rocket_id = overview.rocket_presets[0]
        if (
            self.selected_motor_id is not None
            and overview.motor_presets
            and self.selected_motor_id not in overview.motor_presets
        ):
            self.selected_motor_id = overview.motor_presets[0]
        if (
            overview.environment_presets
            and self.selected_site_id not in overview.environment_presets
        ):
            self.selected_site_id = overview.environment_presets[0]
        if self.selected_mission_id is not None and (
            self.selected_mission_id not in overview.mission_presets
        ):
            self.selected_mission_id = None

        available_limits = list_limits(repo_root=self.repo_root)
        if available_limits and self.selected_limits_id not in available_limits:
            self.selected_limits_id = available_limits[0]

        self.notify()
        return overview

    def refresh_runs(self) -> tuple[RunSummary, ...]:
        """Refresh saved run snapshot summaries without creating data/runs/."""
        self.run_summaries = list_run_snapshots(repo_root=self.repo_root)
        self.notify()
        return self.run_summaries

    def initialize(self, *, compose_default: bool = True) -> AppState:
        """Populate catalog metadata, run history, and initial SimulationConfig."""
        try:
            self.refresh_catalog()
            self.refresh_runs()
            if compose_default and self.simulation_config is None:
                self.compose_config()
                self.status_message = "Catálogo carregado. Pronto para simular."
                self.notify()
        except (GeometryValidationError, SimulationServiceError, ValueError) as exc:
            self.set_error(str(exc), stage="initialization")
        return self

    def ensure_working_rocket(self) -> RocketSpec:
        """Return the active in-memory RocketSpec, loading the selected preset if needed."""
        if self.working_rocket_spec is None:
            self.working_rocket_spec = load_rocket_spec(
                self.selected_rocket_id,
                motor_id=self.selected_motor_id,
                repo_root=self.repo_root,
            )
            self.has_unsaved_rocket_changes = False
        return self.working_rocket_spec

    def update_working_rocket(
        self,
        rocket: RocketSpec,
        *,
        mark_unsaved: bool = True,
    ) -> RocketSpec:
        """Store an edited RocketSpec for session use without mutating disk presets."""
        self.working_rocket_spec = rocket
        self.has_unsaved_rocket_changes = mark_unsaved
        self.dry_mass_override_kg = rocket.dry_mass_override_kg
        self.clear_error()
        self.notify()
        return rocket

    def reset_working_rocket(self) -> RocketSpec:
        """Discard session edits and reload the selected rocket preset from catalog."""
        reloaded = load_rocket_spec(
            self.selected_rocket_id,
            motor_id=self.selected_motor_id,
            repo_root=self.repo_root,
        )
        self.working_rocket_spec = reloaded
        self.has_unsaved_rocket_changes = False
        self.dry_mass_override_kg = reloaded.dry_mass_override_kg
        self.status_message = f"Foguete restaurado para o preset '{self.selected_rocket_id}'."
        self.clear_error()
        self.notify()
        return reloaded

    def save_working_rocket_preset(
        self,
        preset_id: str,
        *,
        preset_name: str | None = None,
    ) -> Path:
        """Persist working_rocket_spec as a new catalog preset without overwriting hefesto_v1."""
        cleaned_id = preset_id.strip()
        if not cleaned_id:
            raise ValueError("Informe um ID válido para o novo preset de foguete.")
        if cleaned_id == DEFAULT_ROCKET_ID:
            raise ValueError(
                f"Não é permitido sobrescrever o preset Golden Master '{DEFAULT_ROCKET_ID}'."
            )
        rocket = self.ensure_working_rocket()
        resolved_name = (
            preset_name.strip() if preset_name and preset_name.strip() else cleaned_id
        )
        updated_rocket = rocket.model_copy(update={"name": resolved_name})
        base_preset = (
            load_rocket_preset(self.selected_rocket_id, repo_root=self.repo_root)
            if self.catalog and self.selected_rocket_id in self.catalog.rocket_presets
            else None
        )
        preset = rocket_preset_from_spec(
            updated_rocket,
            motor_preset_name=self.selected_motor_id or (
                base_preset.motor_preset_name if base_preset else None
            ),
            power_off_drag_asset=base_preset.power_off_drag_asset if base_preset else None,
            power_on_drag_asset=base_preset.power_on_drag_asset if base_preset else None,
        )
        saved_path = save_rocket_preset(preset, preset_id=cleaned_id, repo_root=self.repo_root)
        self.working_rocket_spec = updated_rocket
        self.has_unsaved_rocket_changes = False
        self.selected_rocket_id = cleaned_id
        self.refresh_catalog()
        self.status_message = f"Preset de foguete salvo: {cleaned_id}"
        self.notify()
        return saved_path

    def available_motor_override_options(self) -> tuple[MotorOverrideOption, ...]:
        """List guided OpenMotor override options for the currently selected motor preset."""
        motor_id = self.selected_motor_id
        if not motor_id:
            rocket = self.working_rocket_spec
            motor_id = rocket.motor.name if rocket is not None else DEFAULT_MOTOR_ID
        try:
            preset = load_motor_preset(motor_id, repo_root=self.repo_root)
        except (FileNotFoundError, ValueError):
            return ()
        return list_available_motor_overrides(preset, repo_root=self.repo_root)

    def compose_config(self) -> SimulationConfig:
        """Compose and validate a picklable SimulationConfig from current UI selections."""
        # Compose in calculated mode first so UI dry_mass_override_kg can be applied
        # before SimulationConfig enforces mass_mode='measured' invariants.
        base_config = compose_simulation_config(
            mission_id=self.selected_mission_id,
            rocket_id=self.selected_rocket_id,
            motor_id=self.selected_motor_id,
            site_id=self.selected_site_id,
            limits_id=self.selected_limits_id,
            launch=self.launch_config,
            mass_mode="calculated",
            fin_geometry_mode=self.fin_geometry_mode,
            drag_factor=self.drag_factor,
            thrust_factor=self.thrust_factor,
            motor_overrides=self.motor_overrides,
            output_selection=self.output_selection,
            rocket_spec=self.working_rocket_spec,
            repo_root=self.repo_root,
        )
        mission = base_config.mission
        if self.dry_mass_override_kg is not None:
            updated_rocket = mission.rocket.model_copy(
                update={"dry_mass_override_kg": self.dry_mass_override_kg}
            )
            mission = mission.model_copy(update={"rocket": updated_rocket})

        resolved_config = SimulationConfig(
            mission=mission,
            mass_mode=self.mass_mode,
            fin_geometry_mode=self.fin_geometry_mode,
            drag_factor=self.drag_factor,
            thrust_factor=self.thrust_factor,
            motor_overrides=self.motor_overrides,
            output_selection=self.output_selection,
        )
        self.simulation_config = resolved_config
        self.clear_error()
        return resolved_config

    def set_simulation_config(self, config: SimulationConfig) -> None:
        """Store an externally edited SimulationConfig and sync scalar UI mirror fields."""
        self.simulation_config = config
        self.launch_config = config.mission.launch
        self.mass_mode = config.mass_mode
        self.fin_geometry_mode = config.fin_geometry_mode
        self.drag_factor = config.drag_factor
        self.thrust_factor = config.thrust_factor
        self.dry_mass_override_kg = config.mission.rocket.dry_mass_override_kg
        self.motor_overrides = config.motor_overrides
        self.output_selection = config.output_selection
        self.clear_error()
        self.notify()

    def apply_simulation_result(self, result: SimulationResult) -> None:
        """Apply a completed or loaded SimulationResult into active telemetry state."""
        self.current_result = result
        self.ballistics_preview = result.ballistics
        self.safety_preview = result.safety
        config_for_audit = (
            result.executed_config if result.executed_config is not None else self.simulation_config
        )
        self.current_audit_report = build_execution_audit_report(
            result,
            config_for_audit,
            repo_root=self.repo_root,
        )
        self.clear_error()
        self.status_message = (
            f"Simulação concluída: apogeu {result.flight.apogee_agl_m:.1f} m AGL"
        )
        self.notify()

    def load_motor_into_session(self, motor_id: str) -> None:
        """Select a catalog motor for simulation and reset active motor overrides."""
        self.selected_motor_id = motor_id
        self.motor_overrides = ()
        self.status_message = f"Motor selecionado para simulação: '{motor_id}'."
        self.clear_error()
        self.notify()

    def load_rocket_into_config(self, rocket_id: str) -> RocketSpec:
        """Select a catalog rocket preset and load it as the active working_rocket_spec."""
        self.selected_rocket_id = rocket_id
        self.last_casing_resize_result = None
        return self.reset_working_rocket()

    def apply_motor_casing_update(
        self,
        *,
        new_length_m: float | None = None,
        mode: CasingScalingMode | None = None,
        material_density_kg_m3: float | None = None,
        motor_position_m: float | None = None,
        grain_separation_m: float | None = None,
        internal_clearance_m: float | None = None,
    ) -> CasingResizeResult:
        """Resize motor casing and update mass/CG/inertia on working_rocket_spec."""
        rocket = self.ensure_working_rocket()
        resolved_mode = self.casing_scaling_mode if mode is None else mode
        resolved_density = (
            self.casing_density_kg_m3
            if material_density_kg_m3 is None
            else float(material_density_kg_m3)
        )
        resolved_length = (
            rocket.motor.casing.length_m if new_length_m is None else float(new_length_m)
        )
        updated_rocket, resize_result = update_rocket_motor_casing_length(
            rocket,
            resolved_length,
            mode=resolved_mode,
            material_density_kg_m3=resolved_density,
            motor_position_m=motor_position_m,
            grain_separation_m=grain_separation_m,
            internal_clearance_m=internal_clearance_m,
        )
        self.casing_scaling_mode = resolved_mode
        self.casing_density_kg_m3 = resolved_density
        self.last_casing_resize_result = resize_result
        self.working_rocket_spec = updated_rocket
        self.has_unsaved_rocket_changes = True
        self.clear_error()
        self.notify()
        return resize_result

    def restore_motor_casing_from_preset(self) -> RocketSpec:
        """Restore motor casing, grain separation, and motor position from catalog presets."""
        rocket = self.ensure_working_rocket()
        motor_id = self.selected_motor_id or rocket.motor.name
        preset_motor = load_motor_spec(motor_id, repo_root=self.repo_root)
        motor_pos_m = rocket.motor_position_m
        if self.catalog and self.selected_rocket_id in self.catalog.rocket_presets:
            rocket_preset = load_rocket_preset(
                self.selected_rocket_id, repo_root=self.repo_root
            )
            motor_pos_m = rocket_preset.motor_position_m
        restored_motor = rocket.motor.model_copy(
            update={
                "casing": preset_motor.casing,
                "grain_separation_m": preset_motor.grain_separation_m,
            }
        )
        updated_rocket = recalculate_rocket_structure(
            rocket.model_copy(
                update={
                    "motor": restored_motor,
                    "motor_position_m": motor_pos_m,
                }
            )
        )
        self.last_casing_resize_result = None
        self.working_rocket_spec = updated_rocket
        self.has_unsaved_rocket_changes = True
        self.clear_error()
        self.notify()
        return updated_rocket

    def run_simulation(
        self,
        config: SimulationConfig | None = None,
        *,
        reuse_active_config: bool = False,
    ) -> SimulationResult | None:
        """Execute 6-DOF deterministic simulation via services and capture domain/service errors."""
        self.is_running = True
        self.clear_error()
        self.status_message = "Executando simulação 6-DOF..."
        self.notify()

        try:
            if config is not None:
                target_config = config
            elif reuse_active_config and self.simulation_config is not None:
                target_config = self.simulation_config
            else:
                target_config = self.compose_config()

            result = run_deterministic(target_config, repo_root=self.repo_root)
            self.simulation_config = target_config
            self.apply_simulation_result(result)
            if self.auto_save_runs:
                self.save_current_run()
            return result
        except GeometryValidationError as exc:
            self.last_error = str(exc)
            self.last_error_stage = "geometry"
            self.last_alerts = ()
            self.status_message = f"Bloqueio geométrico: {exc}"
            return None
        except SimulationServiceError as exc:
            self.last_error = exc.message
            self.last_error_stage = exc.stage
            self.last_alerts = exc.alerts
            self.status_message = f"Falha na simulação ({exc.stage}): {exc.message}"
            return None
        except (ValidationError, ValueError, FileNotFoundError) as exc:
            self.last_error = str(exc)
            self.last_error_stage = "validation"
            self.last_alerts = ()
            self.status_message = f"Configuração inválida: {exc}"
            return None
        finally:
            self.is_running = False
            self.notify()

    def run_motor_check(self) -> tuple[BallisticsResult, SafetyReport] | None:
        """Execute standalone OpenMotor ballistics and non-blocking 5-criteria safety check."""
        self.is_running = True
        self.clear_error()
        self.status_message = "Executando balística interna do motor..."
        self.notify()

        motor_id = self.selected_motor_id or DEFAULT_MOTOR_ID
        try:
            ballistics, safety = run_ballistics_check(
                motor_id=motor_id,
                overrides=self.motor_overrides,
                limits_id=self.selected_limits_id,
                repo_root=self.repo_root,
            )
            self.ballistics_preview = ballistics
            self.safety_preview = safety
            self.status_message = (
                f"Balística concluída para '{ballistics.motor_name}': "
                f"empuxo máx. {ballistics.max_thrust_n:.1f} N"
            )
            return ballistics, safety
        except GeometryValidationError as exc:
            self.last_error = str(exc)
            self.last_error_stage = "geometry"
            self.last_alerts = ()
            self.status_message = f"Bloqueio geométrico: {exc}"
            return None
        except SimulationServiceError as exc:
            self.last_error = exc.message
            self.last_error_stage = exc.stage
            self.last_alerts = exc.alerts
            self.status_message = f"Falha na balística ({exc.stage}): {exc.message}"
            return None
        except (ValidationError, ValueError, FileNotFoundError) as exc:
            self.last_error = str(exc)
            self.last_error_stage = "validation"
            self.last_alerts = ()
            self.status_message = f"Configuração inválida: {exc}"
            return None
        finally:
            self.is_running = False
            self.notify()

    def save_current_run(self) -> RunSummary | None:
        """Persist current_result to data/runs/ on explicit user demand."""
        if self.current_result is None:
            self.set_error("Nenhuma simulação executada para salvar.", stage="storage")
            return None
        try:
            summary = save_run_snapshot(self.current_result, repo_root=self.repo_root)
            self.run_summaries = list_run_snapshots(repo_root=self.repo_root)
            self.clear_error()
            self.status_message = f"Snapshot salvo: {summary.run_id}"
            self.notify()
            return summary
        except (OSError, ValueError) as exc:
            self.set_error(str(exc), stage="storage")
            return None

    def load_saved_run(self, run_id: str) -> SimulationResult | None:
        """Load a previously saved run snapshot into current_result."""
        try:
            result = load_run_snapshot(run_id, repo_root=self.repo_root)
            self.apply_simulation_result(result)
            self.status_message = f"Snapshot carregado: {result.run_id}"
            self.notify()
            return result
        except (FileNotFoundError, ValueError) as exc:
            self.set_error(str(exc), stage="storage")
            return None

    def delete_saved_run(self, run_id: str) -> bool:
        """Delete a saved run snapshot and refresh the history list."""
        try:
            delete_run_snapshot(run_id, repo_root=self.repo_root)
            self.run_summaries = list_run_snapshots(repo_root=self.repo_root)
            self.clear_error()
            self.status_message = f"Snapshot removido: {run_id}"
            self.notify()
            return True
        except (FileNotFoundError, ValueError) as exc:
            self.set_error(str(exc), stage="storage")
            return False


def create_app_state(
    *,
    repo_root: str | None = None,
    initialize: bool = False,
) -> AppState:
    """Create a fresh AppState instance, optionally initializing catalog and defaults."""
    state = AppState(repo_root=repo_root)
    if initialize:
        state.initialize()
    return state


def get_client_state(repo_root: str | None = None) -> AppState:
    """Return per-client AppState when inside a NiceGUI client context, else a fresh AppState."""
    try:
        client_storage = context.client.storage
    except RuntimeError:
        return create_app_state(repo_root=repo_root, initialize=True)

    existing = client_storage.get(_CLIENT_STATE_KEY)
    if isinstance(existing, AppState):
        return existing

    state = create_app_state(repo_root=repo_root, initialize=True)
    client_storage[_CLIENT_STATE_KEY] = state
    return state


__all__ = [
    "AppState",
    "create_app_state",
    "get_client_state",
]
