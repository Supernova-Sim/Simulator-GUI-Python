"""NiceGUI fail-closed non-blocking safety criteria and service alert components."""

from __future__ import annotations

from dataclasses import dataclass

from nicegui import ui

from hefesto.domain import SafetyCheck, SafetyCriterion, SafetyLimits, SafetyReport
from hefesto.services import ServiceAlert

_PA_PER_MPA = 1_000_000.0

_CRITERION_ORDER: tuple[SafetyCriterion, ...] = (
    SafetyCriterion.CASE_SAFETY_FACTOR,
    SafetyCriterion.PEAK_CHAMBER_PRESSURE,
    SafetyCriterion.PEAK_KN,
    SafetyCriterion.PEAK_MASS_FLUX,
    SafetyCriterion.PORT_TO_THROAT_RATIO,
)

_CRITERION_LABELS_PT: dict[SafetyCriterion, str] = {
    SafetyCriterion.CASE_SAFETY_FACTOR: "Fator de Segurança da Carcaça",
    SafetyCriterion.PEAK_CHAMBER_PRESSURE: "Pressão Máxima de Câmara",
    SafetyCriterion.PEAK_KN: "Razão de Área Kn de Pico",
    SafetyCriterion.PEAK_MASS_FLUX: "Fluxo Mássico Máximo",
    SafetyCriterion.PORT_TO_THROAT_RATIO: "Razão Porta / Garganta (Aft)",
}

_STAGE_LABELS_PT: dict[str, str] = {
    "geometry": "Bloqueio Geométrico (Pré-RocketPy)",
    "ballistics": "Balística Interna (OpenMotor)",
    "flight": "Simulação de Voo 6-DOF (RocketPy / Atmosfera)",
    "validation": "Validação de Configuração",
    "storage": "Armazenamento de Snapshots",
    "initialization": "Inicialização do Catálogo",
}


@dataclass(frozen=True)
class SafetyRowView:
    """Typed view model for a single fail-closed safety criterion row."""

    criterion: SafetyCriterion
    label: str
    formatted_value: str
    formatted_limit: str
    status_label: str
    passed: bool
    detail: str
    below_target: bool = False


def _format_check_value(check: SafetyCheck) -> str:
    if check.value is None:
        return "N/D (fail-closed)"
    if check.criterion == SafetyCriterion.PEAK_CHAMBER_PRESSURE:
        return f"{check.value / _PA_PER_MPA:.3f} MPa"
    if check.criterion == SafetyCriterion.PEAK_MASS_FLUX:
        return f"{check.value:,.1f} kg/(m²·s)"
    if check.criterion == SafetyCriterion.PEAK_KN:
        return f"{check.value:.1f}"
    return f"{check.value:.3f}"


def _format_check_limit(check: SafetyCheck, limits: SafetyLimits) -> str:
    if check.criterion == SafetyCriterion.CASE_SAFETY_FACTOR:
        min_val = check.min_limit if check.min_limit is not None else limits.min_case_safety_factor
        return f"≥ {min_val:.2f} (meta ≥ {limits.target_case_safety_factor:.2f})"
    if check.criterion == SafetyCriterion.PEAK_CHAMBER_PRESSURE:
        max_val = check.max_limit if check.max_limit is not None else limits.max_chamber_pressure_pa
        return f"≤ {max_val / _PA_PER_MPA:.2f} MPa"
    if check.criterion == SafetyCriterion.PEAK_KN:
        max_val = check.max_limit if check.max_limit is not None else limits.max_kn
        return f"≤ {max_val:.1f}"
    if check.criterion == SafetyCriterion.PEAK_MASS_FLUX:
        max_val = check.max_limit if check.max_limit is not None else limits.max_mass_flux_kg_m2_s
        return f"≤ {max_val:,.1f} kg/(m²·s)"
    min_val = check.min_limit if check.min_limit is not None else limits.min_port_to_throat_ratio
    return f"≥ {min_val:.2f}"


def build_safety_rows(report: SafetyReport) -> tuple[SafetyRowView, ...]:
    """Convert SafetyReport into five deterministically ordered Portuguese rows."""
    by_criterion = {check.criterion: check for check in report.checks}
    rows: list[SafetyRowView] = []
    for criterion in _CRITERION_ORDER:
        check = by_criterion[criterion]
        below_target = (
            criterion == SafetyCriterion.CASE_SAFETY_FACTOR
            and check.passed
            and check.value is not None
            and check.value < report.limits.target_case_safety_factor
        )
        if check.value is None:
            status_label = "Reprovado (sem telemetria)"
        elif not check.passed:
            status_label = "Reprovado"
        elif below_target:
            status_label = "Aprovado (abaixo da meta)"
        else:
            status_label = "Aprovado"

        rows.append(
            SafetyRowView(
                criterion=criterion,
                label=_CRITERION_LABELS_PT[criterion],
                formatted_value=_format_check_value(check),
                formatted_limit=_format_check_limit(check, report.limits),
                status_label=status_label,
                passed=check.passed,
                detail=check.detail,
                below_target=below_target,
            )
        )
    return tuple(rows)


def render_safety_panel(
    report: SafetyReport | None,
    *,
    title: str = "Segurança Estrutural e Balística (Não-Bloqueante)",
) -> ui.card:
    """Render the five fail-closed, non-blocking SafetyLimits criteria."""
    card = ui.card().classes("w-full p-4 shadow-sm")
    with card:
        if report is None:
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(title).classes("text-base font-semibold text-slate-800")
                ui.badge("Aguardando", color="grey")
            ui.label(
                "Execute a balística do motor ou a simulação 6-DOF para avaliar os 5 critérios."
            ).classes("text-sm text-slate-500 mt-1")
            return card

        rows = build_safety_rows(report)
        passed_count = sum(1 for row in rows if row.passed)
        total_count = len(rows)

        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
            with ui.row().classes("items-center gap-2"):
                ui.icon(
                    "verified_user" if report.all_passed else "warning_amber"
                ).classes(
                    "text-xl "
                    + ("text-emerald-600" if report.all_passed else "text-amber-600")
                )
                ui.label(title).classes("text-base font-semibold text-slate-800")

            with ui.row().classes("items-center gap-2"):
                hoop_text = (
                    f"Hoop stress: {report.hoop_stress_pa / _PA_PER_MPA:.2f} MPa"
                    if report.hoop_stress_pa is not None
                    else "Hoop stress: N/D"
                )
                ui.badge(hoop_text, color="blue-grey", outline=True)
                if report.all_passed:
                    ui.badge(f"Aprovado ({passed_count}/{total_count})", color="positive")
                else:
                    ui.badge(
                        f"Falha Não-Bloqueante ({passed_count}/{total_count})",
                        color="negative",
                    )

        ui.label(
            "Critérios fail-closed: valores ausentes ou inválidos reprovam o critério, "
            "sem bloquear a simulação de voo."
        ).classes("text-xs text-slate-500 mt-1 mb-2")

        with ui.column().classes("w-full gap-2"):
            for row in rows:
                if not row.passed:
                    row_bg = "bg-rose-50 border-rose-200"
                    badge_color = "negative"
                elif row.below_target:
                    row_bg = "bg-amber-50 border-amber-200"
                    badge_color = "warning"
                else:
                    row_bg = "bg-emerald-50 border-emerald-200"
                    badge_color = "positive"

                with ui.card().classes(f"w-full p-2.5 border shadow-none {row_bg}"):
                    with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
                        with ui.column().classes("gap-0"):
                            ui.label(row.label).classes("text-sm font-semibold text-slate-800")
                            ui.label(f"Limite: {row.formatted_limit}").classes(
                                "text-xs text-slate-600"
                            )
                        with ui.row().classes("items-center gap-3"):
                            ui.label(row.formatted_value).classes(
                                "text-sm font-bold text-slate-900"
                            )
                            ui.badge(row.status_label, color=badge_color)
                    if row.detail:
                        ui.label(row.detail).classes("text-xs text-slate-500 mt-1")
    return card


def render_alerts_banner(
    error_message: str | None = None,
    *,
    error_stage: str | None = None,
    alerts: tuple[ServiceAlert, ...] = (),
) -> ui.column:
    """Render blocking GeometryValidationError and structured ServiceAlert notices."""
    container = ui.column().classes("w-full gap-2")
    with container:
        if error_message:
            stage_label = _STAGE_LABELS_PT.get(error_stage or "", "Erro de Execução")
            is_geometry = error_stage == "geometry"
            banner_cls = (
                "w-full p-3 border-l-4 border-rose-600 bg-rose-50"
                if is_geometry
                else "w-full p-3 border-l-4 border-red-500 bg-red-50"
            )
            with ui.card().classes(banner_cls):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("gpp_bad" if is_geometry else "error").classes("text-rose-700")
                    ui.label(stage_label).classes("text-sm font-bold text-rose-900")
                ui.label(error_message).classes("text-sm text-rose-800 mt-1")

        for alert in alerts:
            if alert.level == "error":
                cls = "w-full p-2.5 border border-rose-200 bg-rose-50 shadow-none"
                badge_color = "negative"
            elif alert.level == "warning":
                cls = "w-full p-2.5 border border-amber-200 bg-amber-50 shadow-none"
                badge_color = "warning"
            else:
                cls = "w-full p-2.5 border border-sky-200 bg-sky-50 shadow-none"
                badge_color = "info"

            with ui.card().classes(cls):
                with ui.row().classes("items-center justify-between gap-2 flex-wrap"):
                    with ui.row().classes("items-center gap-2"):
                        ui.badge(alert.level.upper(), color=badge_color)
                        ui.label(alert.category).classes("text-xs font-semibold text-slate-700")
                    if alert.location:
                        ui.label(f"Origem: {alert.location}").classes("text-xs text-slate-500")
                ui.label(alert.description).classes("text-sm text-slate-800 mt-1")
    return container


__all__ = [
    "SafetyRowView",
    "build_safety_rows",
    "render_alerts_banner",
    "render_safety_panel",
]
