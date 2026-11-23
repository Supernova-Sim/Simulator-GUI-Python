"""Aerodynamics section: drag_source/finish controls, RASAero II CSV import, live Cd(Mach)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import plotly.graph_objects as go
from nicegui import ui
from nicegui.events import UploadEventArguments

from hefesto.domain import DragCurveTable, DragSource, RocketSpec, SurfaceFinish
from hefesto.services import interpolate_drag_curve

DRAG_SOURCE_OPTIONS: dict[str, str] = {
    "analytical": "Analítico Geométrico (Barrowman/Hoerner)",
    "ork_sim": "Simulação .ork Importada",
    "rasaero_csv": "Tabela CSV RASAero II",
    "legacy_csv": "CSV Legado (Baseline v1)",
}

_DRAG_SOURCES: tuple[DragSource, ...] = ("analytical", "ork_sim", "rasaero_csv", "legacy_csv")

SURFACE_FINISH_OPTIONS: dict[str, str] = {
    "smooth": "Smooth (polido)",
    "regular": "Regular",
    "rough": "Rough (rugoso)",
    "unfinished": "Unfinished (bruto)",
}

DRAG_SUMMARY_MACHES: tuple[float, ...] = (0.3, 0.8, 0.95)
DEFAULT_CHART_MAX_MACH: float = 1.5
EXTENDED_CHART_MAX_MACH: float = 3.0


@dataclass(frozen=True)
class AerodynamicsView:
    """Typed snapshot the aerodynamics section renders from (no AppState dependency)."""

    rocket: RocketSpec
    table: DragCurveTable
    ork_table_available: bool
    rasaero_alpha_options: tuple[float, ...] = ()
    rasaero_alpha_deg: float = 0.0
    rasaero_filename: str | None = None
    rasaero_mach_range: tuple[float, float] | None = None
    chart_max_mach: float = DEFAULT_CHART_MAX_MACH


@dataclass(frozen=True)
class DragSummaryRow:
    """Cd power-off/power-on pair interpolated at one reference Mach number."""

    mach: float
    cd_power_off: float
    cd_power_on: float


def _as_drag_source(value: object) -> DragSource:
    text = str(value)
    for source in _DRAG_SOURCES:
        if source == text:
            return source
    raise ValueError(f"Fonte de arrasto inválida: {text!r}")


def build_drag_summary_rows(table: DragCurveTable) -> tuple[DragSummaryRow, ...]:
    """Interpolate the Cd pair at the M=0.3/0.8/0.95 reference points shown as badges."""
    return tuple(
        DragSummaryRow(
            mach=mach,
            cd_power_off=interpolate_drag_curve(table.mach, table.cd_power_off, mach),
            cd_power_on=interpolate_drag_curve(table.mach, table.cd_power_on, mach),
        )
        for mach in DRAG_SUMMARY_MACHES
    )


def _slice_curve(
    table: DragCurveTable, max_mach: float
) -> tuple[list[float], list[float], list[float]]:
    mach: list[float] = []
    power_off: list[float] = []
    power_on: list[float] = []
    for index, value in enumerate(table.mach):
        if value > max_mach:
            continue
        mach.append(value)
        power_off.append(table.cd_power_off[index])
        power_on.append(table.cd_power_on[index])
    return mach, power_off, power_on


def build_drag_curve_figure(
    table: DragCurveTable,
    *,
    max_mach: float = DEFAULT_CHART_MAX_MACH,
    title: str = "Curvas de Arrasto Cd × Mach",
) -> go.Figure:
    """Plot the power-off/power-on Cd(Mach) pair clipped to max_mach."""
    mach, power_off, power_on = _slice_curve(table, max_mach)
    fig = go.Figure()
    if mach:
        fig.add_trace(
            go.Scatter(
                x=mach,
                y=power_off,
                mode="lines",
                name="CD Power-Off",
                line={"color": "#0284c7", "width": 2.4},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=mach,
                y=power_on,
                mode="lines",
                name="CD Power-On",
                line={"color": "#f97316", "width": 2.4, "dash": "dash"},
            )
        )
        if mach[0] <= 1.0 <= mach[-1]:
            fig.add_vline(
                x=1.0,
                line_dash="dash",
                line_color="#ef4444",
                annotation_text="Mach 1.0",
                annotation_position="top left",
            )
    else:
        fig.add_annotation(
            text=f"Sem pontos de Cd até Mach {max_mach:g}.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 13, "color": "#64748b"},
        )
    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"},
        template="plotly_white",
        height=430,
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1.0,
        },
        margin={"l": 60, "r": 30, "t": 85, "b": 50},
        xaxis={"title": "Número de Mach (-)", "zeroline": False},
        yaxis={"title": "Cd (-)", "rangemode": "tozero"},
    )
    return fig


def render_aerodynamics_panel(
    view: AerodynamicsView,
    *,
    on_source_change: Callable[[DragSource], None],
    on_finish_change: Callable[[SurfaceFinish], None],
    on_csv_import: Callable[[str, str], None],
    on_alpha_change: Callable[[float], None],
    on_chart_range_change: Callable[[float], None],
) -> None:
    """Render the multi-source aerodynamics controls, Cd badges, and live chart."""
    rocket = view.rocket
    with ui.card().classes("w-full p-4 shadow-sm"):
        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 mb-3"):
            ui.label("Seção D — Aerodinâmica Multi-Fonte (Cd × Mach)").classes(
                "text-base font-semibold text-slate-800"
            )
            with ui.row().classes("items-center gap-2"):
                ui.badge(f"drag_source: {rocket.drag_source}", color="primary")
                ui.badge(f"finish: {rocket.surface_finish.value}", color="secondary")

        with ui.grid(columns=2).classes("w-full gap-3 grid-cols-1 md:grid-cols-2"):
            source_select = ui.select(
                options=DRAG_SOURCE_OPTIONS,
                value=rocket.drag_source,
                label="Fonte de Arrasto (drag_source)",
                on_change=lambda e: on_source_change(_as_drag_source(e.value)),
            ).classes("w-full")
            ui.select(
                options=SURFACE_FINISH_OPTIONS,
                value=rocket.surface_finish.value,
                label="Acabamento Superficial (finish)",
                on_change=lambda e: on_finish_change(SurfaceFinish(str(e.value))),
            ).classes("w-full")

        if not view.ork_table_available:
            source_select.tooltip(
                "A opção 'Simulação .ork Importada' fica indisponível porque este foguete não "
                "tem curva Cd extraída de <flightdata>."
            )
            with ui.row().classes("w-full items-center gap-2 text-xs text-amber-900"):
                ui.icon("info").classes("text-sm text-amber-700").tooltip(
                    "Importe um .ork com dados de voo para habilitar drag_source='ork_sim'."
                )
                ui.label(
                    "Simulação .ork Importada indisponível: nenhuma curva <flightdata> neste "
                    "foguete."
                ).classes("text-xs text-amber-900")

        ui.separator().classes("my-3")
        with ui.expansion(
            "Importar CSV do RASAero II",
            icon="upload_file",
            value=rocket.drag_source == "rasaero_csv",
        ).classes("w-full border border-slate-200 rounded"):
            with ui.column().classes("w-full gap-2 p-2"):

                async def _handle_upload(event: UploadEventArguments) -> None:
                    raw = await event.file.read()
                    on_csv_import(
                        raw.decode("utf-8-sig", errors="replace"), event.file.name
                    )

                ui.upload(
                    label="Arquivo CSV exportado do RASAero II (.csv)",
                    auto_upload=True,
                    on_upload=_handle_upload,
                ).props('accept=".csv"').classes("w-full")
                if view.rasaero_filename is not None:
                    ui.label(f"Arquivo carregado: {view.rasaero_filename}").classes(
                        "text-xs text-slate-700"
                    )
                else:
                    ui.label("Nenhum CSV do RASAero II importado nesta sessão.").classes(
                        "text-xs text-slate-500"
                    )
                if view.rasaero_mach_range is not None:
                    mach_min, mach_max = view.rasaero_mach_range
                    ui.label(
                        f"Faixa de Mach importada: {mach_min:g} – {mach_max:g}"
                    ).classes("text-xs text-slate-600")
                if len(view.rasaero_alpha_options) > 1:
                    ui.select(
                        options={
                            alpha: f"{alpha:g}°" for alpha in view.rasaero_alpha_options
                        },
                        value=view.rasaero_alpha_deg,
                        label="Ângulo de Ataque (alpha_deg) do CSV",
                        on_change=lambda e: on_alpha_change(float(e.value)),
                    ).classes("w-full")

        ui.separator().classes("my-3")
        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 mb-1"):
            ui.label("Resumo Numérico de Cd (-)").classes(
                "text-sm font-semibold text-slate-700"
            )
            ui.label(f"Fonte ativa: {view.table.source}").classes("text-xs text-slate-500")
        with ui.grid(columns=3).classes("w-full gap-2 grid-cols-1 sm:grid-cols-3"):
            for row in build_drag_summary_rows(view.table):
                with ui.card().classes("p-3 bg-slate-50 border border-slate-200 gap-1"):
                    ui.label(f"Mach {row.mach:g}").classes("text-xs text-slate-500")
                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        ui.badge(f"Power-Off {row.cd_power_off:.4f}", color="primary")
                        ui.badge(f"Power-On {row.cd_power_on:.4f}", color="warning")

        ui.separator().classes("my-3")
        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
            ui.label("Curvas Cd(Mach) ao Vivo").classes(
                "text-sm font-semibold text-slate-700"
            )
            if view.table.mach[-1] > DEFAULT_CHART_MAX_MACH:
                ui.switch(
                    "Ver até Mach 3.0 (dados supersônicos)",
                    value=view.chart_max_mach > DEFAULT_CHART_MAX_MACH,
                    on_change=lambda e: on_chart_range_change(
                        EXTENDED_CHART_MAX_MACH if e.value else DEFAULT_CHART_MAX_MACH
                    ),
                )
        ui.plotly(
            build_drag_curve_figure(view.table, max_mach=view.chart_max_mach)
        ).classes("w-full")
