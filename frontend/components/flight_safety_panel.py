"""NiceGUI Flight Safety Envelope panel with traffic-light status badges."""

from __future__ import annotations

from dataclasses import dataclass

from nicegui import ui

from hefesto.domain import (
    FlightSafetyCheck,
    FlightSafetyReport,
    FlightSafetyStatus,
)

_STATUS_BADGE_MAP: dict[FlightSafetyStatus, tuple[str, str, str]] = {
    FlightSafetyStatus.PASS: ("APROVADO", "positive", "bg-emerald-50 border-emerald-200"),
    FlightSafetyStatus.WARN: ("ATENÇÃO", "warning", "bg-amber-50 border-amber-200"),
    FlightSafetyStatus.FAIL: ("REPROVADO", "negative", "bg-rose-50 border-rose-200"),
    FlightSafetyStatus.NOT_EVALUATED: ("NÃO AVALIADO", "grey", "bg-slate-50 border-slate-200"),
}


@dataclass(frozen=True)
class FlightSafetyRowView:
    """Typed view model for one Flight Safety Envelope check row."""

    key: str
    category: str
    label: str
    status: FlightSafetyStatus
    status_label: str
    badge_color: str
    card_classes: str
    formatted_value: str
    reference_limit: str
    detail: str
    recommendation: str


def _format_check_value(check: FlightSafetyCheck) -> str:
    if check.value is None:
        return "N/D"
    if check.unit == "x":
        return f"{check.value:.2f}x"
    if check.unit == ":1":
        return f"{check.value:.2f}:1"
    if check.unit == "°":
        return f"{check.value:.1f}°"
    return f"{check.value:.2f} {check.unit}".strip()


def build_flight_safety_rows(report: FlightSafetyReport) -> tuple[FlightSafetyRowView, ...]:
    """Convert FlightSafetyReport into UI-ready Portuguese rows."""
    rows: list[FlightSafetyRowView] = []
    for check in report.checks:
        status_label, badge_color, card_classes = _STATUS_BADGE_MAP[check.status]
        rows.append(
            FlightSafetyRowView(
                key=check.key,
                category=check.category,
                label=check.name,
                status=check.status,
                status_label=status_label,
                badge_color=badge_color,
                card_classes=card_classes,
                formatted_value=_format_check_value(check),
                reference_limit=check.reference_limit,
                detail=check.detail,
                recommendation=check.recommendation,
            )
        )
    return tuple(rows)


def render_flight_safety_panel(
    report: FlightSafetyReport | None,
    *,
    title: str = "Envelope de Segurança de Voo",
) -> ui.card:
    """Render the Flight Safety Envelope panel with traffic-light badges and alerts."""
    card = ui.card().classes("w-full p-4 shadow-sm")
    with card:
        if report is None:
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(title).classes("text-base font-semibold text-slate-800")
                ui.badge("NÃO AVALIADO", color="grey")
            ui.label(
                "Execute uma simulação 6-DOF para avaliar Fin Flutter, "
                "Weathercocking, Decolagem, Cargas Estruturais e Recuperação."
            ).classes("text-sm text-slate-500 mt-1")
            return card

        rows = build_flight_safety_rows(report)
        overall_label, overall_color, _ = _STATUS_BADGE_MAP[report.overall_status]
        pass_count = sum(1 for r in rows if r.status == FlightSafetyStatus.PASS)
        warn_count = sum(1 for r in rows if r.status == FlightSafetyStatus.WARN)
        fail_count = sum(1 for r in rows if r.status == FlightSafetyStatus.FAIL)

        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
            with ui.row().classes("items-center gap-2"):
                icon_name = (
                    "shield"
                    if report.overall_status == FlightSafetyStatus.PASS
                    else "warning_amber"
                    if report.overall_status == FlightSafetyStatus.WARN
                    else "gpp_bad"
                    if report.overall_status == FlightSafetyStatus.FAIL
                    else "help_outline"
                )
                ui.icon(icon_name).classes("text-xl text-slate-700")
                ui.label(title).classes("text-base font-semibold text-slate-800")

            with ui.row().classes("items-center gap-2 flex-wrap"):
                ui.badge(
                    f"OK: {pass_count} · Atenção: {warn_count} · Falha: {fail_count}",
                    color="blue-grey",
                    outline=True,
                )
                ui.badge(overall_label, color=overall_color)

        with ui.grid(columns=2).classes("w-full gap-2 mt-3 grid-cols-1 lg:grid-cols-2"):
            for row in rows:
                with ui.card().classes(f"w-full p-3 border shadow-none {row.card_classes}"):
                    with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap"):
                        with ui.column().classes("gap-0"):
                            ui.label(row.category).classes(
                                "text-[11px] font-medium uppercase tracking-wide text-slate-500"
                            )
                            ui.label(row.label).classes("text-sm font-semibold text-slate-800")
                        with ui.row().classes("items-center gap-2"):
                            ui.label(row.formatted_value).classes(
                                "text-sm font-bold text-slate-900"
                            )
                            ui.badge(row.status_label, color=row.badge_color)
                    if row.reference_limit:
                        ui.label(f"Limite: {row.reference_limit}").classes(
                            "text-xs text-slate-600 mt-1"
                        )
                    if row.detail:
                        ui.label(row.detail).classes("text-xs text-slate-600 mt-0.5")
                    if row.recommendation:
                        ui.label(row.recommendation).classes(
                            "text-xs font-medium text-slate-800 mt-1"
                        )
    return card


__all__ = [
    "FlightSafetyRowView",
    "build_flight_safety_rows",
    "render_flight_safety_panel",
]
