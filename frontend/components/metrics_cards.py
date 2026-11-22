"""NiceGUI KPI metric cards for FlightResult, BallisticsResult, and SimulationResult."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from nicegui import ui

from hefesto.domain import (
    BallisticsResult,
    FlightResult,
    MotorPhysicalSummary,
    MotorSpec,
    SafetyReport,
    SimulationResult,
)
from hefesto.services import summarize_motor_physical_metrics

MetricTone = Literal["neutral", "positive", "warning", "negative", "info"]

_PA_PER_MPA = 1_000_000.0

_TONE_BORDER_CLASSES: dict[MetricTone, str] = {
    "neutral": "border-l-4 border-slate-400",
    "positive": "border-l-4 border-emerald-500",
    "warning": "border-l-4 border-amber-500",
    "negative": "border-l-4 border-rose-500",
    "info": "border-l-4 border-sky-500",
}

_TONE_ICON_COLORS: dict[MetricTone, str] = {
    "neutral": "text-slate-500",
    "positive": "text-emerald-600",
    "warning": "text-amber-600",
    "negative": "text-rose-600",
    "info": "text-sky-600",
}


@dataclass(frozen=True)
class MetricCatalogEntry:
    """Selectable metric catalog descriptor for UI metric pickers."""

    key: str
    label: str
    unit: str
    default_enabled: bool = True


FLIGHT_METRIC_CATALOG: tuple[MetricCatalogEntry, ...] = (
    MetricCatalogEntry("apogee_agl", "Apogeu AGL", "m", True),
    MetricCatalogEntry("max_speed", "Velocidade Máxima", "m/s", True),
    MetricCatalogEntry("rail_exit", "Saída do Trilho", "m/s", True),
    MetricCatalogEntry("static_margin", "Margem Estática Mín.", "cal", True),
    MetricCatalogEntry("total_impulse", "Impulso Total", "N·s", True),
    MetricCatalogEntry("dry_mass", "Massa Seca (sem motor)", "kg", True),
    MetricCatalogEntry("flight_time", "Duração do Voo", "s", True),
    MetricCatalogEntry("impact_distance", "Distância de Impacto", "m", True),
    MetricCatalogEntry("apogee_msl", "Apogeu MSL", "m", False),
    MetricCatalogEntry("apogee_time", "Tempo até o Apogeu", "s", False),
    MetricCatalogEntry("max_mach", "Mach Máximo", "-", False),
    MetricCatalogEntry("max_static_margin", "Margem Estática Máx.", "cal", False),
    MetricCatalogEntry("landing_velocity", "Velocidade de Pouso", "m/s", False),
)

BALLISTICS_METRIC_CATALOG: tuple[MetricCatalogEntry, ...] = (
    MetricCatalogEntry("max_thrust", "Empuxo Máximo", "N", True),
    MetricCatalogEntry("motor_impulse", "Impulso Balístico", "N·s", True),
    MetricCatalogEntry("peak_pressure", "Pressão de Câmara Máx.", "MPa", True),
    MetricCatalogEntry("peak_kn", "Kn de Pico", "-", True),
    MetricCatalogEntry("propellant_mass", "Massa de Propelente", "kg", True),
    MetricCatalogEntry("port_throat", "Porta / Garganta (Aft)", "-", True),
    MetricCatalogEntry("total_loaded_mass", "Massa Total Carregada", "kg", False),
    MetricCatalogEntry("motor_dry_mass", "Massa Seca / Carcaça", "kg", False),
    MetricCatalogEntry("propellant_mass_fraction", "Fração Mássica de Propelente", "%", False),
    MetricCatalogEntry("casing_length", "Comprimento do Motor", "m", False),
    MetricCatalogEntry("outer_diameter", "Diâmetro Externo do Motor", "m", False),
    MetricCatalogEntry("throat_exit_diameter", "Garganta / Saída", "mm", False),
    MetricCatalogEntry("expansion_ratio", "Razão de Expansão", "-", False),
    MetricCatalogEntry("average_thrust", "Empuxo Médio", "N", False),
    MetricCatalogEntry("burn_duration", "Tempo de Queima", "s", False),
)

DEFAULT_FLIGHT_METRIC_KEYS: tuple[str, ...] = tuple(
    entry.key for entry in FLIGHT_METRIC_CATALOG if entry.default_enabled
)
DEFAULT_BALLISTICS_METRIC_KEYS: tuple[str, ...] = tuple(
    entry.key for entry in BALLISTICS_METRIC_CATALOG if entry.default_enabled
)


@dataclass(frozen=True)
class MetricCardItem:
    """Typed view model for a single KPI metric card."""

    key: str
    title: str
    value: str
    unit: str
    subtitle: str = ""
    icon: str = "analytics"
    tone: MetricTone = "neutral"


def _stability_tone(min_margin_calibers: float) -> MetricTone:
    if min_margin_calibers < 1.0:
        return "negative"
    if min_margin_calibers < 1.5:
        return "warning"
    return "positive"


def build_flight_metric_items(
    flight: FlightResult,
    *,
    safety: SafetyReport | None = None,
    selected_keys: Sequence[str] | None = None,
) -> tuple[MetricCardItem, ...]:
    """Build ordered Portuguese KPI items with SI units from a FlightResult."""
    max_margin_text = (
        f"Máx.: {flight.max_static_margin_calibers:.2f} cal"
        if flight.max_static_margin_calibers is not None
        else "Máx.: N/D"
    )
    landing_text = (
        f"Pouso: {flight.landing_velocity_ms:.2f} m/s"
        if flight.landing_velocity_ms is not None
        else "Sem impacto registrado"
    )
    impact_value = (
        f"{flight.impact_distance_m:,.1f}" if flight.impact_distance_m is not None else "N/D"
    )
    impact_unit = "m" if flight.impact_distance_m is not None else ""

    if safety is None:
        impact_subtitle = "Distância horizontal até o ponto de impacto"
        impact_tone: MetricTone = "neutral"
    else:
        passed_count = sum(1 for check in safety.checks if check.passed)
        impact_subtitle = f"Segurança: {passed_count}/{len(safety.checks)} critérios"
        impact_tone = "positive" if safety.all_passed else "warning"

    all_items: dict[str, MetricCardItem] = {
        "apogee_agl": MetricCardItem(
            key="apogee_agl",
            title="Apogeu AGL",
            value=f"{flight.apogee_agl_m:,.1f}",
            unit="m",
            subtitle=f"MSL: {flight.apogee_msl_m:,.1f} m · t = {flight.apogee_time_s:.2f} s",
            icon="flight_takeoff",
            tone="info",
        ),
        "max_speed": MetricCardItem(
            key="max_speed",
            title="Velocidade Máxima",
            value=f"{flight.max_speed_ms:.1f}",
            unit="m/s",
            subtitle=f"Mach máximo: {flight.max_mach:.3f}",
            icon="speed",
            tone="info",
        ),
        "rail_exit": MetricCardItem(
            key="rail_exit",
            title="Saída do Trilho",
            value=f"{flight.rail_exit_velocity_ms:.2f}",
            unit="m/s",
            subtitle="Velocidade ao deixar a guia",
            icon="trending_up",
            tone="positive" if flight.rail_exit_velocity_ms >= 15.0 else "warning",
        ),
        "static_margin": MetricCardItem(
            key="static_margin",
            title="Margem Estática Mín.",
            value=f"{flight.min_static_margin_calibers:.2f}",
            unit="cal",
            subtitle=max_margin_text,
            icon="straighten",
            tone=_stability_tone(flight.min_static_margin_calibers),
        ),
        "total_impulse": MetricCardItem(
            key="total_impulse",
            title="Impulso Total",
            value=f"{flight.total_impulse_ns:,.1f}",
            unit="N·s",
            subtitle=f"Tempo de voo: {flight.flight_time_s:.2f} s",
            icon="local_fire_department",
            tone="neutral",
        ),
        "dry_mass": MetricCardItem(
            key="dry_mass",
            title="Massa Seca (sem motor)",
            value=f"{flight.dry_mass_kg:.3f}",
            unit="kg",
            subtitle=landing_text,
            icon="scale",
            tone="neutral",
        ),
        "flight_time": MetricCardItem(
            key="flight_time",
            title="Duração do Voo",
            value=f"{flight.flight_time_s:.2f}",
            unit="s",
            subtitle=landing_text,
            icon="schedule",
            tone="neutral",
        ),
        "impact_distance": MetricCardItem(
            key="impact_distance",
            title="Distância de Impacto",
            value=impact_value,
            unit=impact_unit,
            subtitle=impact_subtitle,
            icon="place",
            tone=impact_tone,
        ),
        "apogee_msl": MetricCardItem(
            key="apogee_msl",
            title="Apogeu MSL",
            value=f"{flight.apogee_msl_m:,.1f}",
            unit="m",
            subtitle=f"AGL: {flight.apogee_agl_m:,.1f} m",
            icon="terrain",
            tone="info",
        ),
        "apogee_time": MetricCardItem(
            key="apogee_time",
            title="Tempo até o Apogeu",
            value=f"{flight.apogee_time_s:.2f}",
            unit="s",
            subtitle=f"Duração total: {flight.flight_time_s:.2f} s",
            icon="timer",
            tone="neutral",
        ),
        "max_mach": MetricCardItem(
            key="max_mach",
            title="Mach Máximo",
            value=f"{flight.max_mach:.3f}",
            unit="-",
            subtitle=f"Vel. máx.: {flight.max_speed_ms:.1f} m/s",
            icon="air",
            tone="info",
        ),
        "max_static_margin": MetricCardItem(
            key="max_static_margin",
            title="Margem Estática Máx.",
            value=(
                f"{flight.max_static_margin_calibers:.2f}"
                if flight.max_static_margin_calibers is not None
                else "N/D"
            ),
            unit="cal" if flight.max_static_margin_calibers is not None else "",
            subtitle=f"Mín.: {flight.min_static_margin_calibers:.2f} cal",
            icon="straighten",
            tone="neutral",
        ),
        "landing_velocity": MetricCardItem(
            key="landing_velocity",
            title="Velocidade de Pouso",
            value=(
                f"{flight.landing_velocity_ms:.2f}"
                if flight.landing_velocity_ms is not None
                else "N/D"
            ),
            unit="m/s" if flight.landing_velocity_ms is not None else "",
            subtitle="Velocidade vertical no impacto",
            icon="paragliding",
            tone="neutral",
        ),
    }

    target_keys = DEFAULT_FLIGHT_METRIC_KEYS if selected_keys is None else selected_keys
    return tuple(all_items[key] for key in target_keys if key in all_items)


def build_ballistics_metric_items(
    ballistics: BallisticsResult,
    *,
    motor: MotorSpec | None = None,
    summary: MotorPhysicalSummary | None = None,
    selected_keys: Sequence[str] | None = None,
) -> tuple[MetricCardItem, ...]:
    """Build ordered Portuguese KPI items with SI units from a BallisticsResult."""
    burn_start, burn_end = ballistics.burn_time_s
    burn_duration = max(burn_end - burn_start, 1e-9)
    isp_text = (
        f"Isp entregue: {ballistics.delivered_isp_s:.1f} s"
        if ballistics.delivered_isp_s is not None
        else "Isp entregue: N/D"
    )
    aft_ratio_text = (
        f"{ballistics.aft_port_to_throat_ratio:.3f}"
        if ballistics.aft_port_to_throat_ratio is not None
        else "N/D"
    )
    min_ratio_text = (
        f"Mín. stack: {ballistics.min_port_to_throat_ratio:.3f}"
        if ballistics.min_port_to_throat_ratio is not None
        else "Mín. stack: N/D"
    )

    resolved_summary = (
        summary
        if summary is not None
        else (summarize_motor_physical_metrics(motor, ballistics) if motor is not None else None)
    )
    throat_mm = 2.0 * ballistics.throat_radius_m * 1000.0
    exit_mm = 2.0 * ballistics.nozzle_exit_radius_m * 1000.0
    expansion = (ballistics.nozzle_exit_radius_m / ballistics.throat_radius_m) ** 2
    avg_thrust = ballistics.total_impulse_ns / burn_duration

    all_items: dict[str, MetricCardItem] = {
        "max_thrust": MetricCardItem(
            key="max_thrust",
            title="Empuxo Máximo",
            value=f"{ballistics.max_thrust_n:,.1f}",
            unit="N",
            subtitle=f"Queima: {burn_start:.2f}–{burn_end:.2f} s",
            icon="rocket_launch",
            tone="info",
        ),
        "motor_impulse": MetricCardItem(
            key="motor_impulse",
            title="Impulso Balístico",
            value=f"{ballistics.total_impulse_ns:,.1f}",
            unit="N·s",
            subtitle=isp_text,
            icon="bolt",
            tone="info",
        ),
        "peak_pressure": MetricCardItem(
            key="peak_pressure",
            title="Pressão de Câmara Máx.",
            value=f"{ballistics.peak_chamber_pressure_pa / _PA_PER_MPA:.3f}",
            unit="MPa",
            subtitle=f"{ballistics.peak_chamber_pressure_pa:,.0f} Pa",
            icon="compress",
            tone="neutral",
        ),
        "peak_kn": MetricCardItem(
            key="peak_kn",
            title="Kn de Pico",
            value=f"{ballistics.peak_kn:.1f}",
            unit="-",
            subtitle=f"Fluxo mássico: {ballistics.peak_mass_flux_kg_m2_s:,.1f} kg/(m²·s)",
            icon="analytics",
            tone="neutral",
        ),
        "propellant_mass": MetricCardItem(
            key="propellant_mass",
            title="Massa de Propelente",
            value=f"{ballistics.propellant_mass_kg:.3f}",
            unit="kg",
            subtitle=(
                f"{len(ballistics.grains)} grãos · "
                f"ρ = {ballistics.propellant_density_kg_m3:.0f} kg/m³"
            ),
            icon="grain",
            tone="neutral",
        ),
        "port_throat": MetricCardItem(
            key="port_throat",
            title="Porta / Garganta (Aft)",
            value=aft_ratio_text,
            unit="-",
            subtitle=min_ratio_text,
            icon="tune",
            tone="neutral",
        ),
        "total_loaded_mass": MetricCardItem(
            key="total_loaded_mass",
            title="Massa Total Carregada",
            value=(
                f"{resolved_summary.total_loaded_mass_kg:.3f}"
                if resolved_summary is not None
                else "N/D"
            ),
            unit="kg" if resolved_summary is not None else "",
            subtitle=(
                f"Seca: {resolved_summary.dry_mass_kg:.3f} kg + "
                f"Prop.: {resolved_summary.propellant_mass_kg:.3f} kg"
                if resolved_summary is not None
                else "Requer casing do motor"
            ),
            icon="scale",
            tone="neutral",
        ),
        "motor_dry_mass": MetricCardItem(
            key="motor_dry_mass",
            title="Massa Seca / Carcaça",
            value=(
                f"{resolved_summary.dry_mass_kg:.3f}"
                if resolved_summary is not None
                else "N/D"
            ),
            unit="kg" if resolved_summary is not None else "",
            subtitle="Carcaça + tubeira",
            icon="inventory_2",
            tone="neutral",
        ),
        "propellant_mass_fraction": MetricCardItem(
            key="propellant_mass_fraction",
            title="Fração Mássica de Propelente",
            value=(
                f"{resolved_summary.propellant_mass_fraction * 100.0:.1f}"
                if resolved_summary is not None
                else "N/D"
            ),
            unit="%" if resolved_summary is not None else "",
            subtitle="Propelente / Massa Total",
            icon="pie_chart",
            tone="neutral",
        ),
        "casing_length": MetricCardItem(
            key="casing_length",
            title="Comprimento do Motor",
            value=(
                f"{resolved_summary.casing_length_m:.3f}"
                if resolved_summary is not None
                else "N/D"
            ),
            unit="m" if resolved_summary is not None else "",
            subtitle="Comprimento total da carcaça",
            icon="straighten",
            tone="neutral",
        ),
        "outer_diameter": MetricCardItem(
            key="outer_diameter",
            title="Diâmetro Externo do Motor",
            value=(
                f"{resolved_summary.outer_diameter_m * 1000.0:.1f}"
                if resolved_summary is not None
                else "N/D"
            ),
            unit="mm" if resolved_summary is not None else "",
            subtitle=(
                f"{resolved_summary.outer_diameter_m:.4f} m"
                if resolved_summary is not None
                else "Requer casing do motor"
            ),
            icon="circle",
            tone="neutral",
        ),
        "throat_exit_diameter": MetricCardItem(
            key="throat_exit_diameter",
            title="Garganta / Saída",
            value=f"{throat_mm:.1f} / {exit_mm:.1f}",
            unit="mm",
            subtitle=f"Razão de expansão: {expansion:.2f}",
            icon="adjust",
            tone="neutral",
        ),
        "expansion_ratio": MetricCardItem(
            key="expansion_ratio",
            title="Razão de Expansão",
            value=f"{expansion:.2f}",
            unit="-",
            subtitle=f"D_t = {throat_mm:.1f} mm · D_e = {exit_mm:.1f} mm",
            icon="open_in_full",
            tone="neutral",
        ),
        "average_thrust": MetricCardItem(
            key="average_thrust",
            title="Empuxo Médio",
            value=f"{avg_thrust:,.1f}",
            unit="N",
            subtitle=f"Impulso / {burn_duration:.2f} s",
            icon="speed",
            tone="info",
        ),
        "burn_duration": MetricCardItem(
            key="burn_duration",
            title="Tempo de Queima",
            value=f"{burn_duration:.2f}",
            unit="s",
            subtitle=f"Janela: {burn_start:.2f}–{burn_end:.2f} s",
            icon="schedule",
            tone="neutral",
        ),
    }

    target_keys = DEFAULT_BALLISTICS_METRIC_KEYS if selected_keys is None else selected_keys
    return tuple(all_items[key] for key in target_keys if key in all_items)


def render_metric_card(item: MetricCardItem) -> ui.card:
    """Render a single KPI card using NiceGUI primitives."""
    border_cls = _TONE_BORDER_CLASSES[item.tone]
    icon_cls = _TONE_ICON_COLORS[item.tone]

    card = ui.card().classes(f"w-full p-3 shadow-sm {border_cls}")
    with card:
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            ui.label(item.title).classes(
                "text-xs font-medium uppercase tracking-wide text-slate-500"
            )
            ui.icon(item.icon).classes(f"text-lg {icon_cls}")
        with ui.row().classes("items-baseline gap-1 mt-1"):
            ui.label(item.value).classes("text-2xl font-bold text-slate-900")
            if item.unit:
                ui.label(item.unit).classes("text-sm font-medium text-slate-600")
        if item.subtitle:
            ui.label(item.subtitle).classes("text-xs text-slate-500 mt-1")
    return card


def render_flight_metrics_cards(
    flight: FlightResult | None,
    *,
    safety: SafetyReport | None = None,
    columns: int = 4,
    selected_keys: Sequence[str] | None = None,
) -> ui.element:
    """Render a responsive grid of 6-DOF flight KPI cards."""
    if flight is None:
        empty_card = ui.card().classes("w-full p-4 bg-slate-50 border border-slate-200")
        with empty_card:
            with ui.row().classes("items-center gap-2 text-slate-600"):
                ui.icon("info")
                ui.label("Nenhuma simulação de voo 6-DOF executada.")
        return empty_card

    items = build_flight_metric_items(flight, safety=safety, selected_keys=selected_keys)
    grid = ui.grid(columns=columns).classes(
        "w-full gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
    )
    with grid:
        for item in items:
            render_metric_card(item)
    return grid


def render_ballistics_metrics_cards(
    ballistics: BallisticsResult | None,
    *,
    columns: int = 3,
    motor: MotorSpec | None = None,
    summary: MotorPhysicalSummary | None = None,
    selected_keys: Sequence[str] | None = None,
) -> ui.element:
    """Render a responsive grid of internal ballistics KPI cards."""
    if ballistics is None:
        info_card = ui.card().classes("w-full p-4 bg-amber-50 border border-amber-200")
        with info_card:
            with ui.row().classes("items-center gap-2 text-amber-800"):
                ui.icon("info")
                ui.label(
                    "Sem telemetria de balística interna (motor configurado apenas com curva .eng)."
                )
        return info_card

    items = build_ballistics_metric_items(
        ballistics,
        motor=motor,
        summary=summary,
        selected_keys=selected_keys,
    )
    grid = ui.grid(columns=columns).classes(
        "w-full gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
    )
    with grid:
        for item in items:
            render_metric_card(item)
    return grid


def render_metric_selector(
    *,
    label: str,
    catalog: Sequence[MetricCatalogEntry],
    selected_keys: Sequence[str],
    on_change: Callable[[tuple[str, ...]], None],
) -> ui.select:
    """Render a compact multi-select control to choose visible KPI cards."""
    options = {
        entry.key: f"{entry.label} ({entry.unit})" if entry.unit != "-" else entry.label
        for entry in catalog
    }
    return ui.select(
        options=options,
        value=list(selected_keys),
        label=label,
        multiple=True,
        on_change=lambda e: on_change(tuple(str(v) for v in (e.value or ()))),
    ).props("dense outlined use-chips").classes("min-w-64 max-w-xl")


def render_simulation_metrics_summary(
    result: SimulationResult | None,
    *,
    motor: MotorSpec | None = None,
    selected_flight_keys: Sequence[str] | None = None,
    selected_ballistics_keys: Sequence[str] | None = None,
    on_flight_keys_change: Callable[[tuple[str, ...]], None] | None = None,
    on_ballistics_keys_change: Callable[[tuple[str, ...]], None] | None = None,
) -> ui.column:
    """Render the complete KPI summary for a SimulationResult."""
    container = ui.column().classes("w-full gap-4")
    with container:
        if result is None:
            render_flight_metrics_cards(None)
            return container

        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
            with ui.row().classes("items-center gap-2"):
                ui.label(f"Missão: {result.mission_name}").classes(
                    "text-base font-semibold text-slate-800"
                )
                ui.badge(result.motor_name, color="primary")
            ui.label(
                f"Execução {result.run_id} · {result.created_at_utc:%Y-%m-%d %H:%M:%S} UTC"
            ).classes("text-xs text-slate-500")

        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
            ui.label("Métricas de Voo 6-DOF").classes("text-sm font-semibold text-slate-700")
            if on_flight_keys_change is not None:
                render_metric_selector(
                    label="Escolher métricas 6-DOF",
                    catalog=FLIGHT_METRIC_CATALOG,
                    selected_keys=(
                        DEFAULT_FLIGHT_METRIC_KEYS
                        if selected_flight_keys is None
                        else selected_flight_keys
                    ),
                    on_change=on_flight_keys_change,
                )
        render_flight_metrics_cards(
            result.flight,
            safety=result.safety,
            selected_keys=selected_flight_keys,
        )

        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 mt-1"):
            ui.label("Balística Interna do Motor").classes("text-sm font-semibold text-slate-700")
            if on_ballistics_keys_change is not None:
                render_metric_selector(
                    label="Escolher métricas do Motor",
                    catalog=BALLISTICS_METRIC_CATALOG,
                    selected_keys=(
                        DEFAULT_BALLISTICS_METRIC_KEYS
                        if selected_ballistics_keys is None
                        else selected_ballistics_keys
                    ),
                    on_change=on_ballistics_keys_change,
                )
        render_ballistics_metrics_cards(
            result.ballistics,
            motor=motor,
            selected_keys=selected_ballistics_keys,
        )
    return container


__all__ = [
    "BALLISTICS_METRIC_CATALOG",
    "DEFAULT_BALLISTICS_METRIC_KEYS",
    "DEFAULT_FLIGHT_METRIC_KEYS",
    "FLIGHT_METRIC_CATALOG",
    "MetricCardItem",
    "MetricCatalogEntry",
    "MetricTone",
    "build_ballistics_metric_items",
    "build_flight_metric_items",
    "render_ballistics_metrics_cards",
    "render_flight_metrics_cards",
    "render_metric_card",
    "render_metric_selector",
    "render_simulation_metrics_summary",
]
