"""On-demand run snapshot history page (data/runs/)."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import context, ui

from frontend.components import (
    render_alerts_banner,
    render_execution_audit_panel,
    render_safety_panel,
    render_simulation_metrics_summary,
)
from frontend.state import AppState
from hefesto.domain import RunSummary


def _attach_client_cleanup(unsubscribe: Callable[[], None]) -> None:
    try:
        context.client.on_delete(unsubscribe)
    except RuntimeError:
        return


def _safety_badge(summary: RunSummary) -> tuple[str, str]:
    if summary.safety_passed is True:
        return ("Segurança OK", "positive")
    if summary.safety_passed is False:
        return ("Falha Não-Bloqueante", "warning")
    return ("Sem Balística", "grey")


def render_history_page(state: AppState) -> ui.column:
    """Render manual on-demand SimulationResult snapshot save, list, load, and delete."""
    state.refresh_runs()

    root = ui.column().classes("w-full gap-4")

    @ui.refreshable
    def render_current_action_card() -> None:
        with ui.card().classes("w-full p-4 shadow-sm"):
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-3"):
                with ui.column().classes("gap-1"):
                    ui.label("Snapshots Sob Demanda (data/runs/)").classes(
                        "text-lg font-semibold text-slate-800"
                    )
                    if state.current_result is None:
                        ui.label(
                            "Nenhuma simulação ativa em memória para salvar."
                        ).classes("text-xs text-slate-500")
                    else:
                        res = state.current_result
                        ui.label(
                            f"Execução ativa: {res.run_id} · {res.mission_name} "
                            f"({res.flight.apogee_agl_m:.1f} m AGL)"
                        ).classes("text-xs text-slate-700")

                with ui.row().classes("items-center gap-2"):
                    save_btn = ui.button(
                        "Salvar Snapshot Atual",
                        icon="save",
                        on_click=_on_save_current,
                    ).props("color=primary")
                    if state.current_result is None:
                        save_btn.disable()
                    ui.button(
                        "Atualizar Lista",
                        icon="refresh",
                        on_click=lambda: (state.refresh_runs(), render_snapshots_list.refresh()),
                    ).props("outline color=primary")

    @ui.refreshable
    def render_snapshots_list() -> None:
        if state.last_error:
            render_alerts_banner(
                state.last_error,
                error_stage=state.last_error_stage,
                alerts=state.last_alerts,
            )

        summaries = state.run_summaries
        if not summaries:
            with ui.card().classes("w-full p-4 bg-slate-50 border border-slate-200 shadow-none"):
                ui.label(
                    "Nenhum snapshot salvo em data/runs/. Execute uma simulação e clique em "
                    "'Salvar Snapshot Atual' quando desejar persistir."
                ).classes("text-sm text-slate-600")
            return

        with ui.column().classes("w-full gap-2"):
            for summary in summaries:
                badge_label, badge_color = _safety_badge(summary)
                with ui.card().classes("w-full p-3 shadow-sm border border-slate-200"):
                    with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
                        with ui.column().classes("gap-0.5"):
                            with ui.row().classes("items-center gap-2 flex-wrap"):
                                ui.label(summary.run_id).classes(
                                    "text-sm font-mono font-bold text-slate-800"
                                )
                                ui.badge(badge_label, color=badge_color)
                            ui.label(
                                f"{summary.mission_name} · motor {summary.motor_name} · "
                                f"{summary.created_at_utc:%Y-%m-%d %H:%M:%S} UTC"
                            ).classes("text-xs text-slate-600")
                            ui.label(
                                f"Apogeu: {summary.apogee_agl_m:,.1f} m AGL · "
                                f"Mach máx.: {summary.max_mach:.3f} · "
                                f"Margem estática mín.: "
                                f"{summary.min_static_margin_calibers:.2f} cal"
                            ).classes("text-xs text-slate-700")

                        with ui.row().classes("items-center gap-2"):
                            def _load(run_id: str = summary.run_id) -> None:
                                loaded = state.load_saved_run(run_id)
                                if loaded is not None:
                                    ui.notify(f"Snapshot carregado: {run_id}", type="positive")
                                    render_preview.refresh()
                                    render_current_action_card.refresh()
                                elif state.last_error:
                                    ui.notify(state.last_error, type="negative")

                            def _load_and_open(run_id: str = summary.run_id) -> None:
                                loaded = state.load_saved_run(run_id)
                                if loaded is not None:
                                    ui.navigate.to("/")
                                elif state.last_error:
                                    ui.notify(state.last_error, type="negative")

                            def _delete(run_id: str = summary.run_id) -> None:
                                if state.delete_saved_run(run_id):
                                    ui.notify(f"Snapshot removido: {run_id}", type="info")
                                    render_snapshots_list.refresh()
                                elif state.last_error:
                                    ui.notify(state.last_error, type="negative")

                            ui.button("Carregar", icon="download", on_click=_load).props(
                                "outline color=primary size=sm"
                            )
                            ui.button(
                                "Abrir na Simulação",
                                icon="open_in_new",
                                on_click=_load_and_open,
                            ).props("flat color=primary size=sm")
                            ui.button("Excluir", icon="delete", on_click=_delete).props(
                                "flat color=negative size=sm"
                            )

    @ui.refreshable
    def render_preview() -> None:
        if state.current_result is None:
            return
        with ui.card().classes("w-full p-4 shadow-sm"):
            ui.label("Prévia do Snapshot Selecionado").classes(
                "text-base font-semibold text-slate-800 mb-2"
            )
            render_simulation_metrics_summary(state.current_result)
            render_safety_panel(state.safety_preview)
            with ui.expansion(
                "Auditoria da Execução (Motor, Overrides e Foguete Executados)",
                icon="fact_check",
                value=True,
            ).classes("w-full mt-3 border border-slate-200 rounded"):
                with ui.column().classes("w-full p-2"):
                    render_execution_audit_panel(state.current_audit_report)

    def _on_save_current() -> None:
        summary = state.save_current_run()
        if summary is not None:
            ui.notify(f"Snapshot salvo: {summary.run_id}", type="positive")
            render_snapshots_list.refresh()
            render_current_action_card.refresh()
        elif state.last_error:
            ui.notify(state.last_error, type="negative")
            render_snapshots_list.refresh()

    with root:
        render_current_action_card()
        render_snapshots_list()
        render_preview()

    def _sync_history() -> None:
        render_current_action_card.refresh()
        render_snapshots_list.refresh()
        render_preview.refresh()

    unsub = state.subscribe(_sync_history)
    _attach_client_cleanup(unsub)
    return root


__all__ = [
    "render_history_page",
]
