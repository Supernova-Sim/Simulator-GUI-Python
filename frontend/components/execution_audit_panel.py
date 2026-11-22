"""Reusable NiceGUI panel rendering 'Saved Preset vs. Executed Snapshot' audit details."""

from __future__ import annotations

from nicegui import ui

from hefesto.domain import ExecutionAuditReport

_SOURCE_BADGES: dict[str, tuple[str, str]] = {
    "ric_and_eng": (".ric + .eng", "primary"),
    "ric_only": (".ric OpenMotor", "secondary"),
    "eng_only": (".eng Curva Fixa", "grey"),
}


def _format_audit_value(value: float | int | str | None, unit: str) -> str:
    if value is None:
        return "N/D"
    if isinstance(value, float):
        text = f"{value:.6g}"
    elif isinstance(value, str):
        text = value
    else:
        text = str(value)
    return text if unit == "-" else f"{text} {unit}"


def render_execution_audit_panel(report: ExecutionAuditReport | None) -> None:
    """Render detailed motor, overrides, rocket, and environment audit for a simulation run."""
    if report is None:
        with ui.card().classes("w-full p-4 bg-slate-50 border border-slate-200 shadow-none"):
            ui.label(
                "Nenhuma execução selecionada para auditoria (Preset Salvo vs. Executado)."
            ).classes("text-sm text-slate-500")
        return

    src_label, src_color = _SOURCE_BADGES.get(report.motor_source_kind, ("Desconhecido", "grey"))
    ov_count = len(report.applied_overrides)

    with ui.grid(columns=2).classes("w-full gap-4 grid-cols-1 lg:grid-cols-2"):
        with ui.card().classes("w-full p-4 bg-slate-50 border border-slate-200 shadow-none"):
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 mb-2"):
                ui.label("Motor Efetivamente Executado").classes(
                    "text-sm font-semibold text-slate-800"
                )
                with ui.row().classes("items-center gap-1.5"):
                    ui.badge(src_label, color=src_color)
                    if ov_count > 0:
                        ui.badge(f"{ov_count} override(s) aplicado(s)", color="warning")
                    else:
                        ui.badge("Sem overrides (preset puro)", color="positive")

            ui.label(f"Preset Base: {report.motor_preset_id}").classes(
                "text-xs font-mono text-slate-700"
            )
            if report.motor_asset:
                ui.label(f"Arquivo OpenMotor: {report.motor_asset}").classes(
                    "text-xs font-mono text-slate-600"
                )
            if report.thrust_curve_asset:
                ui.label(f"Curva .eng: {report.thrust_curve_asset}").classes(
                    "text-xs font-mono text-slate-600"
                )

            if report.applied_overrides:
                ui.separator().classes("my-2")
                ui.label("Parâmetros Alterados por MotorOverride:").classes(
                    "text-xs font-semibold text-slate-700 mb-1"
                )
                with ui.column().classes("w-full gap-1.5"):
                    for item in report.applied_overrides:
                        with ui.row().classes(
                            "w-full items-center justify-between bg-white border border-slate-200 "
                            "rounded px-2.5 py-1.5 flex-wrap gap-1"
                        ):
                            with ui.column().classes("gap-0"):
                                with ui.row().classes("items-center gap-1.5"):
                                    ui.badge(
                                        "Alterado" if item.changed else "Igual",
                                        color="warning" if item.changed else "grey",
                                    )
                                    ui.badge(
                                        "Preset" if item.source == "preset" else "Sessão",
                                        color="info" if item.source == "preset" else "primary",
                                    )
                                    ui.label(f"{item.label} ({item.path})").classes(
                                        "text-xs font-medium text-slate-800"
                                    )
                                base_txt = _format_audit_value(item.base_value, item.unit)
                                applied_txt = _format_audit_value(item.applied_value, item.unit)
                                ui.label(
                                    f"Base no .ric: {base_txt} → Aplicado: {applied_txt}"
                                ).classes("text-xs font-mono text-slate-600")

            if report.motor_summary is not None:
                ms = report.motor_summary
                ui.separator().classes("my-2")
                ui.label("Resumo Físico Efetivo do Motor:").classes(
                    "text-xs font-semibold text-slate-700 mb-1"
                )
                with ui.grid(columns=2).classes("w-full gap-1 text-xs text-slate-700"):
                    ui.label(f"Massa Seca (carcaça): {ms.dry_mass_kg:.3f} kg")
                    ui.label(f"Massa Propelente: {ms.propellant_mass_kg:.3f} kg")
                    ui.label(f"Massa Total Carregada: {ms.total_loaded_mass_kg:.3f} kg")
                    ui.label(f"Fração Mássica: {ms.propellant_mass_fraction * 100.0:.1f} %")
                    outer_d_mm = ms.outer_diameter_m * 1000.0
                    ui.label(
                        f"Carcaça: L={ms.casing_length_m:.3f} m · Øext={outer_d_mm:.1f} mm"
                    )
                    ui.label(
                        f"Tubeira: Øg={ms.throat_diameter_mm:.2f} mm · "
                        f"Øs={ms.exit_diameter_mm:.2f} mm"
                    )
                    ui.label(f"Impulso Total: {ms.total_impulse_ns:,.1f} N·s")
                    if ms.peak_chamber_pressure_pa is not None:
                        ui.label(f"Pressão Pico: {ms.peak_chamber_pressure_pa / 1e6:.2f} MPa")

            if report.effective_grains:
                ui.separator().classes("my-2")
                ui.label(f"Grãos Efetivos ({len(report.effective_grains)}):").classes(
                    "text-xs font-semibold text-slate-700 mb-1"
                )
                with ui.column().classes("w-full gap-0.5"):
                    for idx, grain in enumerate(report.effective_grains):
                        ui.label(
                            f"Grão {idx + 1}: L={grain.length_m * 1000.0:.1f} mm · "
                            f"Øext={grain.outer_radius_m * 2000.0:.1f} mm · "
                            f"Øfuro={grain.inner_radius_m * 2000.0:.1f} mm · "
                            f"inibição={grain.inhibited_ends.value}"
                        ).classes("text-xs font-mono text-slate-600")

        with ui.card().classes("w-full p-4 bg-slate-50 border border-slate-200 shadow-none"):
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 mb-2"):
                ui.label("Foguete, Física e Ambiente Executados").classes(
                    "text-sm font-semibold text-slate-800"
                )
                if report.rocket_modified_in_session:
                    ui.badge("Modificado na Sessão (working_rocket_spec)", color="warning")
                else:
                    ui.badge("Preset Puro do Catálogo", color="positive")

            ui.label(
                f"Foguete: {report.rocket_name} (preset base: {report.rocket_preset_id})"
            ).classes("text-xs font-mono text-slate-700")
            ui.label(f"Run ID: {report.run_id} · Missão: {report.mission_name}").classes(
                "text-xs font-mono text-slate-600"
            )

            if report.rocket_modification_notes:
                ui.separator().classes("my-2")
                ui.label("Diferenças detectadas em relação ao preset:").classes(
                    "text-xs font-semibold text-amber-800 mb-1"
                )
                for note in report.rocket_modification_notes:
                    ui.label(f"• {note}").classes("text-xs text-amber-900")

            ui.separator().classes("my-2")
            with ui.grid(columns=2).classes("w-full gap-1 text-xs text-slate-700"):
                ui.label(f"Modo de Massa: {report.mass_mode}")
                ui.label(f"Massa Seca Efetiva: {report.effective_dry_mass_kg:.3f} kg")
                ui.label(f"Modo das Aletas: {report.fin_geometry_mode}")
                ui.label(
                    f"Fatores: drag={report.drag_factor:.3f} · thrust={report.thrust_factor:.3f}"
                )
                if report.environment_name:
                    ui.label(f"Sítio: {report.environment_name}")
                if report.atmosphere_asset:
                    ui.label(f"Atmosfera: {report.atmosphere_asset}")

            if report.fins_summary:
                ui.label(f"Aletas: {report.fins_summary}").classes(
                    "text-xs font-mono text-slate-600 mt-2"
                )

            if report.components_summary:
                ui.separator().classes("my-2")
                ui.label(f"Componentes Executados ({len(report.components_summary)}):").classes(
                    "text-xs font-semibold text-slate-700 mb-1"
                )
                with ui.column().classes("w-full gap-0.5"):
                    for line in report.components_summary:
                        ui.label(f"• {line}").classes("text-xs font-mono text-slate-600")


__all__ = ["render_execution_audit_panel"]
