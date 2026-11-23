"""Simulation configuration, cpu_bound 6-DOF execution, and telemetry page."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Literal

from nicegui import context, run, ui
from pydantic import ValidationError

from frontend.components import (
    BALLISTICS_METRIC_CATALOG,
    parse_override_value,
    render_alerts_banner,
    render_ballistics_metrics_cards,
    render_execution_audit_panel,
    render_flight_metrics_cards,
    render_metric_selector,
    render_motor_import_dialog,
    render_motor_overrides_editor,
    render_safety_panel,
    render_simulation_metrics_summary,
    render_telemetry_tabs,
)
from frontend.state import AppState
from hefesto.domain import (
    BallisticsResult,
    FinGeometryMode,
    GeometryValidationError,
    MassMode,
    OutputSelection,
    SafetyReport,
    SimulationResult,
)
from hefesto.services import (
    DEFAULT_MOTOR_ID,
    ServiceAlert,
    SimulationServiceError,
    list_limits,
    run_ballistics_check,
    run_deterministic,
)

_MASS_MODE_OPTIONS: dict[MassMode, str] = {
    "calculated": "Calculada (componentes)",
    "measured": "Medida (override manual)",
}

_FIN_MODE_OPTIONS: dict[FinGeometryMode, str] = {
    "freeform": "Freeform (tabela geométrica)",
    "trapezoidal": "Trapezoidal (root/tip/sweep)",
}

_ODE_SOLVER_OPTIONS: tuple[Literal["LSODA", "RK45", "DOP853"], ...] = (
    "LSODA",
    "RK45",
    "DOP853",
)

_OUTPUT_FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("x", "X Leste (m)"),
    ("y", "Y Norte (m)"),
    ("altitude_agl", "Altitude AGL (m)"),
    ("speed", "Velocidade Total (m/s)"),
    ("vertical_velocity", "Velocidade Vertical (m/s)"),
    ("acceleration", "Aceleração (m/s²)"),
    ("mach", "Mach (-)"),
    ("cg", "Centro de Gravidade (m)"),
    ("cp", "Centro de Pressão (m)"),
    ("static_margin", "Margem Estática (cal)"),
    ("drag", "Arrasto (N)"),
    ("thrust", "Empuxo (N)"),
)


def build_simulation_error_state(
    exc: Exception,
) -> tuple[str, str, tuple[ServiceAlert, ...]]:
    """Classify domain/service/atmosphere/subprocess exceptions into UI stage, message, alerts."""
    if isinstance(exc, run.SubprocessException):
        orig_type = str(exc.original_type)
        orig_msg = str(exc.original_message)
        orig_tb = str(exc.original_traceback)
        if orig_type == "GeometryValidationError":
            return ("geometry", orig_msg, ())
        if orig_type == "FileNotFoundError":
            lowered = orig_msg.lower()
            if "atmosphere" in lowered or ".nc" in lowered:
                return (
                    "flight",
                    f"Arquivo atmosférico NetCDF (.nc) ausente — simulação bloqueada "
                    f"(sem fallback ISA): {orig_msg}",
                    (),
                )
            return ("validation", f"Asset obrigatório ausente: {orig_msg}", ())
        if orig_type == "SimulationServiceError":
            stage = (
                "ballistics"
                if "run_openmotor" in orig_tb or "ballistics" in orig_tb
                else "flight"
            )
            return (stage, orig_msg, ())
        if orig_type in {"ValidationError", "ValueError"}:
            return ("validation", orig_msg, ())
        return ("simulation", f"{orig_type}: {orig_msg}", ())

    if isinstance(exc, GeometryValidationError):
        return ("geometry", str(exc), ())

    if isinstance(exc, SimulationServiceError):
        return (exc.stage, exc.message, exc.alerts)

    if isinstance(exc, FileNotFoundError):
        text = str(exc)
        lowered = text.lower()
        if "atmosphere" in lowered or ".nc" in lowered:
            return (
                "flight",
                f"Arquivo atmosférico NetCDF (.nc) ausente — simulação bloqueada "
                f"(sem fallback ISA): {text}",
                (),
            )
        return ("validation", f"Asset obrigatório ausente: {text}", ())

    return ("validation", str(exc), ())


async def execute_simulation_async(state: AppState) -> SimulationResult | None:
    """Compose SimulationConfig and execute run_deterministic via nicegui.run.cpu_bound."""
    state.is_running = True
    state.clear_error()
    state.status_message = "Executando simulação 6-DOF em processo isolado..."
    state.notify()

    try:
        target_config = state.compose_config()
        result = await run.cpu_bound(run_deterministic, target_config, state.repo_root)
        state.simulation_config = target_config
        state.apply_simulation_result(result)
        if state.auto_save_runs:
            state.save_current_run()
        return result
    except (
        GeometryValidationError,
        SimulationServiceError,
        FileNotFoundError,
        ValidationError,
        ValueError,
        run.SubprocessException,
    ) as exc:
        stage, message, alerts = build_simulation_error_state(exc)
        state.last_error_stage = stage
        state.last_error = message
        state.last_alerts = alerts
        state.status_message = f"Erro ({stage}): {message}"
        return None
    finally:
        state.is_running = False
        state.notify()


async def execute_motor_check_async(
    state: AppState,
) -> tuple[BallisticsResult, SafetyReport] | None:
    """Execute OpenMotor ballistics and 5-criteria safety check via nicegui.run.cpu_bound."""
    state.is_running = True
    state.clear_error()
    state.status_message = "Executando balística interna do motor..."
    state.notify()

    rocket = state.ensure_working_rocket()
    motor_id = rocket.motor.name or state.selected_motor_id or DEFAULT_MOTOR_ID
    try:
        ballistics, safety = await run.cpu_bound(
            run_ballistics_check,
            motor_id,
            state.motor_overrides,
            limits_id=state.selected_limits_id,
            casing=rocket.motor.casing,
            repo_root=state.repo_root,
        )
        state.ballistics_preview = ballistics
        state.safety_preview = safety
        state.status_message = (
            f"Balística concluída para '{ballistics.motor_name}': "
            f"empuxo máx. {ballistics.max_thrust_n:.1f} N"
        )
        return ballistics, safety
    except (
        GeometryValidationError,
        SimulationServiceError,
        FileNotFoundError,
        ValidationError,
        ValueError,
        run.SubprocessException,
    ) as exc:
        stage, message, alerts = build_simulation_error_state(exc)
        state.last_error_stage = stage
        state.last_error = message
        state.last_alerts = alerts
        state.status_message = f"Erro ({stage}): {message}"
        return None
    finally:
        state.is_running = False
        state.notify()


def _attach_client_cleanup(unsubscribe: Callable[[], None]) -> None:
    try:
        context.client.on_delete(unsubscribe)
    except RuntimeError:
        return


def render_simulation_page(state: AppState) -> ui.column:
    """Render the main 6-DOF simulation configuration, execution, and telemetry page."""
    if state.catalog is None:
        state.initialize()

    catalog = state.catalog
    rocket_options = list(catalog.rocket_presets) if catalog else [state.selected_rocket_id]

    site_options = list(catalog.environment_presets) if catalog else [state.selected_site_id]
    limits_options = list(list_limits(repo_root=state.repo_root)) or [state.selected_limits_id]
    mission_options: dict[str, str] = {"": "Seleção Manual"}
    if catalog is not None:
        for mission_id in catalog.mission_presets:
            mission_options[mission_id] = mission_id

    root = ui.column().classes("w-full gap-4")

    @ui.refreshable
    def render_output_toggles() -> None:
        with ui.grid(columns=4).classes("w-full gap-2 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4"):
            for field_name, label_pt in _OUTPUT_FIELD_LABELS:
                current_val = bool(getattr(state.output_selection, field_name))

                def _on_toggle(checked: bool, key: str = field_name) -> None:
                    state.output_selection = state.output_selection.model_copy(
                        update={key: checked}
                    )

                ui.checkbox(
                    label_pt,
                    value=current_val,
                    on_change=lambda e, fn=_on_toggle: fn(bool(e.value)),
                ).classes("text-xs")

    @ui.refreshable
    def render_results_section() -> None:
        if state.last_error or state.last_alerts:
            render_alerts_banner(
                state.last_error,
                error_stage=state.last_error_stage,
                alerts=state.last_alerts,
            )

        if state.safety_preview is not None and not state.safety_preview.all_passed:
            with ui.card().classes("w-full p-3 border-l-4 border-amber-500 bg-amber-50"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("warning_amber").classes("text-amber-700")
                    ui.label(
                        "Aviso Não-Bloqueante de Segurança: um ou mais critérios do motor "
                        "falharam (fail-closed). A simulação 6-DOF não foi bloqueada."
                    ).classes("text-sm font-medium text-amber-900")

        render_safety_panel(state.safety_preview)

        def _on_flight_metrics_change(keys: tuple[str, ...]) -> None:
            state.selected_flight_metrics = keys
            render_results_section.refresh()

        def _on_ballistics_metrics_change(keys: tuple[str, ...]) -> None:
            state.selected_ballistics_metrics = keys
            render_results_section.refresh()

        active_motor = (
            state.simulation_config.mission.rocket.motor
            if state.simulation_config is not None
            else (
                state.working_rocket_spec.motor
                if state.working_rocket_spec is not None
                else None
            )
        )

        if state.current_result is not None:
            render_simulation_metrics_summary(
                state.current_result,
                motor=active_motor,
                selected_flight_keys=state.selected_flight_metrics,
                selected_ballistics_keys=state.selected_ballistics_metrics,
                on_flight_keys_change=_on_flight_metrics_change,
                on_ballistics_keys_change=_on_ballistics_metrics_change,
            )
        elif state.ballistics_preview is not None:
            with ui.card().classes("w-full p-4 shadow-sm"):
                with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 mb-2"):
                    ui.label("Prévia de Balística Interna (.ric)").classes(
                        "text-sm font-semibold text-slate-700"
                    )
                    render_metric_selector(
                        label="Escolher métricas do Motor",
                        catalog=BALLISTICS_METRIC_CATALOG,
                        selected_keys=state.selected_ballistics_metrics,
                        on_change=_on_ballistics_metrics_change,
                    )
                render_ballistics_metrics_cards(
                    state.ballistics_preview,
                    motor=active_motor,
                    selected_keys=state.selected_ballistics_metrics,
                )
        else:
            render_flight_metrics_cards(None)

        render_telemetry_tabs(state.current_result, ballistics=state.ballistics_preview)

        if state.current_result is not None:
            with ui.expansion(
                "Auditoria da Execução (Preset Salvo vs. Snapshot Executado)",
                icon="fact_check",
                value=True,
            ).classes("w-full border border-slate-200 rounded bg-white"):
                with ui.column().classes("w-full p-2"):
                    render_execution_audit_panel(state.current_audit_report)

    @ui.refreshable
    def render_motor_picker() -> None:
        def _on_motor_change(value: object) -> None:
            try:
                state.load_motor_into_session(str(value) if value else "")
            except (FileNotFoundError, SimulationServiceError, ValueError) as exc:
                ui.notify(f"Falha ao carregar motor: {exc}", type="negative")

        with ui.column().classes("w-full gap-1"):
            ui.select(
                options=state.selectable_motor_options(),
                value=state.selected_motor_id or "",
                label="Motor",
                on_change=lambda e: _on_motor_change(e.value),
            ).classes("w-full")
            ui.button(
                "Importar motor (.ric)",
                icon="upload_file",
                on_click=motor_import_dialog.open,
            ).props("flat dense color=primary no-caps")

    with root:
        async def _on_motor_imported() -> None:
            render_motor_picker.refresh()
            await execute_motor_check_async(state)

        motor_import_dialog = render_motor_import_dialog(state, on_imported=_on_motor_imported)

        if state.working_rocket_spec is not None:
            with ui.card().classes("w-full p-3 border-l-4 border-sky-500 bg-sky-50"):
                with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("tune").classes("text-sky-700")
                        label_text = (
                            f"Foguete customizado ativo na sessão: {state.working_rocket_spec.name}"
                            + (
                                " (alterações não salvas)"
                                if state.has_unsaved_rocket_changes
                                else ""
                            )
                        )
                        ui.label(label_text).classes("text-sm font-medium text-sky-900")
                    with ui.row().classes("items-center gap-2"):
                        ui.button(
                            "Abrir Configuração",
                            icon="settings",
                            on_click=lambda: ui.navigate.to("/config"),
                        ).props("flat dense color=primary")
                        ui.button(
                            "Restaurar Preset",
                            icon="restart_alt",
                            on_click=lambda: (
                                state.reset_working_rocket(),
                                ui.notify("Foguete restaurado para o preset.", type="info"),
                            ),
                        ).props("flat dense color=grey")

        with ui.card().classes("w-full p-4 shadow-sm"):
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 mb-2"):
                ui.label("Configuração da Missão e Física 6-DOF").classes(
                    "text-lg font-semibold text-slate-800"
                )
                status_label = ui.label(state.status_message).classes(
                    "text-xs font-medium text-slate-600"
                )

            with ui.grid(columns=5).classes("w-full gap-3 grid-cols-1 md:grid-cols-5"):
                ui.select(
                    options=mission_options,
                    value=state.selected_mission_id or "",
                    label="Missão (Preset)",
                    on_change=lambda e: setattr(
                        state, "selected_mission_id", str(e.value) if e.value else None
                    ),
                ).classes("w-full")
                ui.select(
                    options=rocket_options,
                    value=state.selected_rocket_id,
                    label="Foguete",
                    on_change=lambda e: setattr(state, "selected_rocket_id", str(e.value)),
                ).classes("w-full")
                render_motor_picker()
                ui.select(
                    options=site_options,
                    value=state.selected_site_id,
                    label="Sítio / Atmosfera (.nc)",
                    on_change=lambda e: setattr(state, "selected_site_id", str(e.value)),
                ).classes("w-full")
                ui.select(
                    options=limits_options,
                    value=state.selected_limits_id,
                    label="Limites de Segurança",
                    on_change=lambda e: setattr(state, "selected_limits_id", str(e.value)),
                ).classes("w-full")

            ui.separator().classes("my-3")

            with ui.grid(columns=4).classes(
                "w-full gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
            ):
                ui.number(
                    label="Inclinação da Rampa (°)",
                    value=state.launch_config.inclination_deg,
                    min=1.0,
                    max=90.0,
                    step=0.5,
                    on_change=lambda e: _update_launch(state, inclination_deg=e.value),
                ).classes("w-full")
                ui.number(
                    label="Azimute / Heading (°)",
                    value=state.launch_config.heading_deg,
                    min=0.0,
                    max=359.9,
                    step=5.0,
                    on_change=lambda e: _update_launch(state, heading_deg=e.value),
                ).classes("w-full")
                ui.number(
                    label="Comprimento do Trilho (m)",
                    value=state.launch_config.rail_length_m,
                    min=0.5,
                    step=0.5,
                    on_change=lambda e: _update_launch(state, rail_length_m=e.value),
                ).classes("w-full")
                ui.number(
                    label="Tempo Máx. Simulação (s)",
                    value=state.launch_config.max_time_s,
                    min=1.0,
                    step=30.0,
                    on_change=lambda e: _update_launch(state, max_time_s=e.value),
                ).classes("w-full")

            with ui.grid(columns=5).classes(
                "w-full gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 mt-2 items-center"
            ):
                mass_override_input = ui.number(
                    label="Massa Seca Medida (kg)",
                    value=state.dry_mass_override_kg,
                    min=0.1,
                    step=0.1,
                    on_change=lambda e: setattr(
                        state,
                        "dry_mass_override_kg",
                        float(e.value) if e.value is not None else None,
                    ),
                ).classes("w-full")
                mass_override_input.set_visibility(state.mass_mode == "measured")

                def _on_mass_mode_change(val: object) -> None:
                    mode: MassMode = "measured" if val == "measured" else "calculated"
                    state.mass_mode = mode
                    mass_override_input.set_visibility(mode == "measured")

                ui.select(
                    options=_MASS_MODE_OPTIONS,
                    value=state.mass_mode,
                    label="Modo de Massa (MassMode)",
                    on_change=lambda e: _on_mass_mode_change(e.value),
                ).classes("w-full")

                def _on_fin_mode_change(val: object) -> None:
                    mode: FinGeometryMode = "trapezoidal" if val == "trapezoidal" else "freeform"
                    state.fin_geometry_mode = mode

                ui.select(
                    options=_FIN_MODE_OPTIONS,
                    value=state.fin_geometry_mode,
                    label="Geometria das Aletas (FinGeometryMode)",
                    on_change=lambda e: _on_fin_mode_change(e.value),
                ).classes("w-full")
                ui.number(
                    label="Fator de Arrasto (drag_factor)",
                    value=state.drag_factor,
                    min=0.05,
                    step=0.05,
                    on_change=lambda e: _set_positive_factor(state, "drag_factor", e.value),
                ).classes("w-full")
                ui.number(
                    label="Fator de Empuxo (thrust_factor)",
                    value=state.thrust_factor,
                    min=0.05,
                    step=0.05,
                    on_change=lambda e: _set_positive_factor(state, "thrust_factor", e.value),
                ).classes("w-full")

            with ui.row().classes("w-full items-center gap-6 mt-2 flex-wrap"):
                ui.select(
                    options=list(_ODE_SOLVER_OPTIONS),
                    value=state.launch_config.ode_solver,
                    label="Integrador ODE",
                    on_change=lambda e: _update_launch(state, ode_solver=str(e.value)),
                ).classes("w-40")
                ui.switch(
                    "Encerrar no Apogeu (terminate_on_apogee)",
                    value=state.launch_config.terminate_on_apogee,
                    on_change=lambda e: _update_launch(
                        state, terminate_on_apogee=bool(e.value)
                    ),
                )

            with ui.expansion("Overrides de Motor (.ric) — MotorOverride", icon="tune").classes(
                "w-full mt-2 border border-slate-200 rounded"
            ):
                with ui.column().classes("w-full gap-2 p-2"):
                    render_motor_overrides_editor(state)

            with ui.expansion("Seleção de Curvas (OutputSelection)", icon="checklist").classes(
                "w-full mt-2 border border-slate-200 rounded"
            ):
                with ui.column().classes("w-full gap-2 p-2"):
                    with ui.row().classes("gap-2"):
                        def _select_all_outputs() -> None:
                            state.output_selection = OutputSelection.all()
                            render_output_toggles.refresh()

                        def _clear_outputs() -> None:
                            state.output_selection = OutputSelection.none()
                            render_output_toggles.refresh()

                        ui.button("Marcar Todas", on_click=_select_all_outputs).props(
                            "flat dense color=primary"
                        )
                        ui.button("Nenhuma (apenas escalares)", on_click=_clear_outputs).props(
                            "flat dense color=grey"
                        )
                    render_output_toggles()

            with ui.row().classes("w-full items-center gap-3 mt-4 flex-wrap"):
                run_sim_btn = ui.button(
                    "Executar Simulação 6-DOF",
                    icon="play_arrow",
                ).props("color=primary")
                check_motor_btn = ui.button(
                    "Verificar Motor (.ric)",
                    icon="local_fire_department",
                ).props("outline color=secondary")
                save_snapshot_btn = ui.button(
                    "Salvar Snapshot (data/runs/)",
                    icon="save",
                ).props("outline color=positive")
                ui.switch(
                    "Salvar execução automaticamente no histórico (data/runs/)",
                    value=state.auto_save_runs,
                    on_change=lambda e: setattr(state, "auto_save_runs", bool(e.value)),
                )
                spinner = ui.spinner(size="sm").classes("text-primary")
                spinner.set_visibility(state.is_running)

        render_results_section()

    def _sync_buttons() -> None:
        status_label.text = state.status_message
        spinner.set_visibility(state.is_running)
        if state.is_running:
            run_sim_btn.disable()
            check_motor_btn.disable()
        else:
            run_sim_btn.enable()
            check_motor_btn.enable()
        if state.current_result is not None and not state.is_running:
            save_snapshot_btn.enable()
        else:
            save_snapshot_btn.disable()

    def _sync_controls() -> None:
        _sync_buttons()
        render_results_section.refresh()

    async def _on_run_simulation() -> None:
        await execute_simulation_async(state)
        if state.last_error:
            ui.notify(state.last_error, type="negative")
        elif state.current_result is not None:
            ui.notify(
                f"Simulação concluída: apogeu {state.current_result.flight.apogee_agl_m:.1f} m AGL",
                type="positive",
            )

    async def _on_check_motor() -> None:
        await execute_motor_check_async(state)
        if state.last_error:
            ui.notify(state.last_error, type="negative")
        elif state.ballistics_preview is not None:
            ui.notify(
                f"Balística concluída: empuxo máx. {state.ballistics_preview.max_thrust_n:.1f} N",
                type="positive",
            )

    def _on_save_snapshot() -> None:
        summary = state.save_current_run()
        if summary is not None:
            ui.notify(f"Snapshot salvo em data/runs/: {summary.run_id}", type="positive")
        elif state.last_error:
            ui.notify(state.last_error, type="negative")

    run_sim_btn.on_click(_on_run_simulation)
    check_motor_btn.on_click(_on_check_motor)
    save_snapshot_btn.on_click(_on_save_snapshot)
    _sync_buttons()

    unsub = state.subscribe(_sync_controls)
    _attach_client_cleanup(unsub)
    return root


def _update_launch(
    state: AppState,
    *,
    inclination_deg: float | int | None = None,
    heading_deg: float | int | None = None,
    rail_length_m: float | int | None = None,
    max_time_s: float | int | None = None,
    terminate_on_apogee: bool | None = None,
    ode_solver: str | None = None,
) -> None:
    updates: dict[str, float | bool | str] = {}
    if inclination_deg is not None:
        updates["inclination_deg"] = float(inclination_deg)
    if heading_deg is not None:
        updates["heading_deg"] = float(heading_deg)
    if rail_length_m is not None:
        updates["rail_length_m"] = float(rail_length_m)
    if max_time_s is not None:
        updates["max_time_s"] = float(max_time_s)
    if terminate_on_apogee is not None:
        updates["terminate_on_apogee"] = terminate_on_apogee
    if ode_solver is not None and ode_solver in _ODE_SOLVER_OPTIONS:
        updates["ode_solver"] = ode_solver
    if not updates:
        return
    try:
        state.launch_config = state.launch_config.model_copy(update=updates)
        state.launch_config = type(state.launch_config).model_validate(
            state.launch_config.model_dump()
        )
    except ValidationError:
        return


def _set_positive_factor(
    state: AppState,
    attr_name: Literal["drag_factor", "thrust_factor"],
    raw_value: float | int | None,
) -> None:
    if raw_value is None:
        return
    numeric = float(raw_value)
    if math.isfinite(numeric) and numeric > 0.0:
        setattr(state, attr_name, numeric)


__all__ = [
    "build_simulation_error_state",
    "execute_motor_check_async",
    "execute_simulation_async",
    "parse_override_value",
    "render_simulation_page",
]
