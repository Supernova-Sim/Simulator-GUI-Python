"""Plotly telemetry figures and NiceGUI ui.plotly panels for FlightResult and BallisticsResult."""

from __future__ import annotations

import math
from bisect import bisect_right

import plotly.graph_objects as go
from nicegui import ui
from plotly.subplots import make_subplots

from hefesto.domain import BallisticsResult, FlightResult, SimulationResult

_PA_PER_MPA = 1_000_000.0


def _unpack_series(
    series: tuple[tuple[float, float], ...],
) -> tuple[list[float], list[float]]:
    if not series:
        return [], []
    xs = [pt[0] for pt in series]
    ys = [pt[1] for pt in series]
    return xs, ys


def _interpolate_series_at(
    series: tuple[tuple[float, float], ...],
    target_times: list[float],
) -> list[float]:
    times = [pt[0] for pt in series]
    values = [pt[1] for pt in series]
    if len(times) == 1:
        return [values[0]] * len(target_times)

    interpolated: list[float] = []
    for t_val in target_times:
        if t_val <= times[0]:
            interpolated.append(values[0])
            continue
        if t_val >= times[-1]:
            interpolated.append(values[-1])
            continue
        idx = bisect_right(times, t_val)
        t0, t1 = times[idx - 1], times[idx]
        v0, v1 = values[idx - 1], values[idx]
        if t1 <= t0:
            interpolated.append(v0)
        else:
            frac = (t_val - t0) / (t1 - t0)
            interpolated.append(v0 + frac * (v1 - v0))
    return interpolated


def _align_trajectory_3d(
    x_series: tuple[tuple[float, float], ...],
    y_series: tuple[tuple[float, float], ...],
    altitude_series: tuple[tuple[float, float], ...],
) -> tuple[list[float], list[float], list[float], list[float]]:
    if not (x_series and y_series and altitude_series):
        return [], [], [], []

    if len(x_series) == len(y_series) == len(altitude_series) and all(
        math.isclose(tx, tz, abs_tol=1e-9) and math.isclose(ty, tz, abs_tol=1e-9)
        for (tx, _), (ty, _), (tz, _) in zip(
            x_series, y_series, altitude_series, strict=True
        )
    ):
        times = [pt[0] for pt in altitude_series]
        xs = [pt[1] for pt in x_series]
        ys = [pt[1] for pt in y_series]
        zs = [pt[1] for pt in altitude_series]
        return times, xs, ys, zs

    times = [pt[0] for pt in altitude_series]
    zs = [pt[1] for pt in altitude_series]
    xs = _interpolate_series_at(x_series, times)
    ys = _interpolate_series_at(y_series, times)
    return times, xs, ys, zs


def _empty_figure(title: str, message: str, *, height: int = 440) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font={"size": 14, "color": "#64748b"},
    )
    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"},
        template="plotly_white",
        height=height,
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"l": 40, "r": 30, "t": 60, "b": 40},
    )
    return fig


def _apply_standard_layout(
    fig: go.Figure,
    *,
    title: str,
    height: int = 620,
    hovermode: str = "x unified",
) -> go.Figure:
    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"},
        template="plotly_white",
        height=height,
        hovermode=hovermode,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1.0,
        },
        margin={"l": 65, "r": 30, "t": 85, "b": 55},
    )
    return fig


def build_trajectory_3d_figure(flight: FlightResult | None) -> go.Figure:
    """Panel 1: 3D flight trajectory (x_series, y_series, altitude_agl_series)."""
    if flight is None:
        return _empty_figure(
            "Trajetória 3D (AGL)",
            "Nenhuma simulação de voo executada.",
            height=540,
        )

    times, xs, ys, zs = _align_trajectory_3d(
        flight.x_series,
        flight.y_series,
        flight.altitude_agl_series,
    )
    if not times:
        return _empty_figure(
            "Trajetória 3D (AGL)",
            "Séries 3D indisponíveis (habilite x, y e altitude_agl em OutputSelection).",
            height=540,
        )

    apogee_idx = max(range(len(zs)), key=lambda idx: zs[idx])
    fig = go.Figure()

    fig.add_trace(
        go.Scatter3d(
            x=xs,
            y=ys,
            z=[0.0] * len(xs),
            mode="lines",
            name="Projeção no Solo",
            line={"color": "#94a3b8", "width": 2, "dash": "dash"},
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter3d(
            x=xs,
            y=ys,
            z=zs,
            mode="lines",
            name="Trajetória 6-DOF",
            customdata=times,
            line={
                "color": zs,
                "colorscale": "Viridis",
                "width": 5,
                "colorbar": {"title": "Alt. AGL (m)", "len": 0.7},
            },
            hovertemplate=(
                "t = %{customdata:.2f} s<br>"
                "X = %{x:.1f} m<br>"
                "Y = %{y:.1f} m<br>"
                "Altitude AGL = %{z:.1f} m<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter3d(
            x=[xs[0]],
            y=[ys[0]],
            z=[zs[0]],
            mode="markers",
            name="Lançamento",
            marker={"size": 6, "color": "#10b981"},
        )
    )
    fig.add_trace(
        go.Scatter3d(
            x=[xs[apogee_idx]],
            y=[ys[apogee_idx]],
            z=[zs[apogee_idx]],
            mode="markers",
            name=f"Apogeu ({zs[apogee_idx]:.1f} m)",
            marker={"size": 7, "color": "#f59e0b", "symbol": "diamond"},
        )
    )
    fig.add_trace(
        go.Scatter3d(
            x=[xs[-1]],
            y=[ys[-1]],
            z=[zs[-1]],
            mode="markers",
            name="Fim da Simulação",
            marker={"size": 6, "color": "#ef4444"},
        )
    )

    fig.update_layout(
        title={"text": "Trajetória 3D do Voo (Referencial Local)", "x": 0.02, "xanchor": "left"},
        template="plotly_white",
        height=560,
        scene={
            "xaxis_title": "X Leste (m)",
            "yaxis_title": "Y Norte (m)",
            "zaxis_title": "Altitude AGL (m)",
            "aspectmode": "auto",
        },
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "left", "x": 0.02},
        margin={"l": 20, "r": 20, "t": 75, "b": 20},
    )
    return fig


def build_kinematics_figure(flight: FlightResult | None) -> go.Figure:
    """Panel 2: Kinematics (speed, vertical_velocity, acceleration, mach)."""
    if flight is None:
        return _empty_figure("Cinemática de Voo", "Nenhuma simulação de voo executada.", height=640)

    has_any = any(
        (
            flight.speed_series,
            flight.vertical_velocity_series,
            flight.mach_series,
            flight.acceleration_series,
        )
    )
    if not has_any:
        return _empty_figure(
            "Cinemática de Voo",
            "Séries cinemáticas indisponíveis (verifique OutputSelection).",
            height=640,
        )

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            "Velocidade Total e Vertical (m/s)",
            "Número de Mach (-)",
            "Aceleração Total (m/s²)",
        ),
    )

    if flight.speed_series:
        t_s, v_ms = _unpack_series(flight.speed_series)
        fig.add_trace(
            go.Scatter(
                x=t_s,
                y=v_ms,
                mode="lines",
                name="Velocidade Total (m/s)",
                line={"color": "#0284c7", "width": 2},
            ),
            row=1,
            col=1,
        )
    if flight.vertical_velocity_series:
        t_vz, vz_ms = _unpack_series(flight.vertical_velocity_series)
        fig.add_trace(
            go.Scatter(
                x=t_vz,
                y=vz_ms,
                mode="lines",
                name="Velocidade Vertical Vz (m/s)",
                line={"color": "#10b981", "width": 2},
            ),
            row=1,
            col=1,
        )
    if flight.mach_series:
        t_m, mach = _unpack_series(flight.mach_series)
        fig.add_trace(
            go.Scatter(
                x=t_m,
                y=mach,
                mode="lines",
                name="Mach (-)",
                line={"color": "#7c3aed", "width": 2},
            ),
            row=2,
            col=1,
        )
        if max(mach) >= 0.7:
            fig.add_hline(
                y=1.0,
                line_dash="dash",
                line_color="#ef4444",
                annotation_text="Mach 1.0",
                row=2,
                col=1,
            )
    if flight.acceleration_series:
        t_a, acc = _unpack_series(flight.acceleration_series)
        fig.add_trace(
            go.Scatter(
                x=t_a,
                y=acc,
                mode="lines",
                name="Aceleração (m/s²)",
                line={"color": "#ea580c", "width": 2},
            ),
            row=3,
            col=1,
        )

    fig.update_yaxes(title_text="Velocidade (m/s)", row=1, col=1)
    fig.update_yaxes(title_text="Mach (-)", row=2, col=1)
    fig.update_yaxes(title_text="Aceleração (m/s²)", row=3, col=1)
    fig.update_xaxes(title_text="Tempo (s)", row=3, col=1)
    return _apply_standard_layout(fig, title="Cinemática de Voo", height=660)


def build_stability_figure(flight: FlightResult | None) -> go.Figure:
    """Panel 3: Longitudinal stability (cg_series, cp_series, static_margin_series)."""
    if flight is None:
        return _empty_figure(
            "Estabilidade Longitudinal",
            "Nenhuma simulação de voo executada.",
            height=560,
        )

    if not (flight.cg_series or flight.cp_series or flight.static_margin_series):
        return _empty_figure(
            "Estabilidade Longitudinal",
            "Séries de estabilidade indisponíveis (verifique OutputSelection).",
            height=560,
        )

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10,
        subplot_titles=(
            "Posição Axial CG e CP (nose_to_tail, m)",
            "Margem Estática (calibres)",
        ),
    )

    if flight.cg_series:
        t_cg, cg_m = _unpack_series(flight.cg_series)
        fig.add_trace(
            go.Scatter(
                x=t_cg,
                y=cg_m,
                mode="lines",
                name="Centro de Gravidade CG (m)",
                line={"color": "#0284c7", "width": 2},
            ),
            row=1,
            col=1,
        )
    if flight.cp_series:
        t_cp, cp_m = _unpack_series(flight.cp_series)
        fig.add_trace(
            go.Scatter(
                x=t_cp,
                y=cp_m,
                mode="lines",
                name="Centro de Pressão CP (m)",
                line={"color": "#d97706", "width": 2},
            ),
            row=1,
            col=1,
        )
    if flight.static_margin_series:
        t_sm, sm_cal = _unpack_series(flight.static_margin_series)
        fig.add_trace(
            go.Scatter(
                x=t_sm,
                y=sm_cal,
                mode="lines",
                name="Margem Estática (cal)",
                line={"color": "#059669", "width": 2.2},
            ),
            row=2,
            col=1,
        )
        fig.add_hline(
            y=1.5,
            line_dash="dot",
            line_color="#f59e0b",
            annotation_text="Mín. 1.5 cal",
            row=2,
            col=1,
        )
        fig.add_hline(
            y=2.0,
            line_dash="dash",
            line_color="#10b981",
            annotation_text="Meta 2.0 cal",
            row=2,
            col=1,
        )

    fig.update_yaxes(title_text="Posição (m)", row=1, col=1)
    fig.update_yaxes(title_text="Margem (cal)", row=2, col=1)
    fig.update_xaxes(title_text="Tempo (s)", row=2, col=1)
    return _apply_standard_layout(
        fig,
        title="Estabilidade Longitudinal (CG, CP e Margem Estática)",
        height=580,
    )


def build_aerodynamics_figure(flight: FlightResult | None) -> go.Figure:
    """Panel 4: Aerodynamics (drag_series + power_off_drag_curve / power_on_drag_curve)."""
    if flight is None:
        return _empty_figure(
            "Aerodinâmica e Arrasto",
            "Nenhuma simulação de voo executada.",
            height=580,
        )

    if not (flight.drag_series or flight.power_off_drag_curve or flight.power_on_drag_curve):
        return _empty_figure(
            "Aerodinâmica e Arrasto",
            "Séries aerodinâmicas indisponíveis (verifique OutputSelection).",
            height=580,
        )

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.16,
        subplot_titles=(
            "Força de Arrasto Aerodinâmico no Voo (N)",
            "Coeficiente de Arrasto Cd × Número de Mach",
        ),
    )

    if flight.drag_series:
        t_drag, drag_n = _unpack_series(flight.drag_series)
        fig.add_trace(
            go.Scatter(
                x=t_drag,
                y=drag_n,
                mode="lines",
                name="Arrasto Aerodinâmico (N)",
                line={"color": "#dc2626", "width": 2},
            ),
            row=1,
            col=1,
        )

    if flight.power_off_drag_curve:
        m_off, cd_off = _unpack_series(flight.power_off_drag_curve)
        fig.add_trace(
            go.Scatter(
                x=m_off,
                y=cd_off,
                mode="lines",
                name="Cd Power-Off",
                line={"color": "#0284c7", "width": 2},
            ),
            row=2,
            col=1,
        )
    if flight.power_on_drag_curve:
        m_on, cd_on = _unpack_series(flight.power_on_drag_curve)
        fig.add_trace(
            go.Scatter(
                x=m_on,
                y=cd_on,
                mode="lines",
                name="Cd Power-On",
                line={"color": "#f97316", "width": 2, "dash": "dash"},
            ),
            row=2,
            col=1,
        )

    fig.update_xaxes(title_text="Tempo (s)", row=1, col=1)
    fig.update_yaxes(title_text="Arrasto (N)", row=1, col=1)
    fig.update_xaxes(title_text="Número de Mach (-)", row=2, col=1)
    fig.update_yaxes(title_text="Cd (-)", row=2, col=1)
    return _apply_standard_layout(
        fig,
        title="Aerodinâmica e Curvas de Arrasto",
        height=600,
        hovermode="closest",
    )


def build_propulsion_figure(
    flight: FlightResult | None,
    ballistics: BallisticsResult | None = None,
) -> go.Figure:
    """Panel 5: Propulsion (flight.thrust_series + BallisticsResult thrust/pressure/Kn)."""
    has_flight_thrust = flight is not None and bool(flight.thrust_series)
    has_ballistics_curves = ballistics is not None and bool(
        ballistics.thrust_curve or ballistics.pressure_curve or ballistics.kn_curve
    )
    if not (has_flight_thrust or has_ballistics_curves):
        return _empty_figure(
            "Propulsão e Balística Interna",
            "Sem curvas de empuxo ou balística disponíveis.",
            height=660,
        )

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.09,
        subplot_titles=(
            "Empuxo (N)",
            "Pressão de Câmara (MPa)",
            "Razão de Área Kn (-)",
        ),
    )

    if flight is not None and flight.thrust_series:
        t_ft, f_ft = _unpack_series(flight.thrust_series)
        fig.add_trace(
            go.Scatter(
                x=t_ft,
                y=f_ft,
                mode="lines",
                name="Empuxo Líquido no Voo — RocketPy (N)",
                line={"color": "#0284c7", "width": 2},
            ),
            row=1,
            col=1,
        )

    if ballistics is not None:
        if ballistics.thrust_curve:
            t_bt, f_bt = _unpack_series(ballistics.thrust_curve)
            fig.add_trace(
                go.Scatter(
                    x=t_bt,
                    y=f_bt,
                    mode="lines",
                    name="Empuxo Balístico — OpenMotor (N)",
                    line={"color": "#ea580c", "width": 2, "dash": "dot"},
                ),
                row=1,
                col=1,
            )
        if ballistics.pressure_curve:
            t_p, p_pa = _unpack_series(ballistics.pressure_curve)
            p_mpa = [val / _PA_PER_MPA for val in p_pa]
            fig.add_trace(
                go.Scatter(
                    x=t_p,
                    y=p_mpa,
                    mode="lines",
                    name="Pressão de Câmara (MPa)",
                    line={"color": "#7c3aed", "width": 2},
                ),
                row=2,
                col=1,
            )
        if ballistics.kn_curve:
            t_kn, kn_vals = _unpack_series(ballistics.kn_curve)
            fig.add_trace(
                go.Scatter(
                    x=t_kn,
                    y=kn_vals,
                    mode="lines",
                    name="Kn (-)",
                    line={"color": "#059669", "width": 2},
                ),
                row=3,
                col=1,
            )
    else:
        for row_idx in (2, 3):
            fig.add_annotation(
                text="Sem curva OpenMotor (.ric indisponível para este motor)",
                xref=f"x{row_idx} domain",
                yref=f"y{row_idx} domain",
                x=0.5,
                y=0.5,
                showarrow=False,
                font={"size": 12, "color": "#64748b"},
            )

    fig.update_yaxes(title_text="Empuxo (N)", row=1, col=1)
    fig.update_yaxes(title_text="Pressão (MPa)", row=2, col=1)
    fig.update_yaxes(title_text="Kn (-)", row=3, col=1)
    fig.update_xaxes(title_text="Tempo (s)", row=3, col=1)
    return _apply_standard_layout(fig, title="Propulsão e Balística Interna", height=680)


def build_all_panel_figures(
    result: SimulationResult | None,
    *,
    ballistics: BallisticsResult | None = None,
) -> dict[str, go.Figure]:
    """Build all five Plotly telemetry figures for a SimulationResult/BallisticsResult pair."""
    flight = result.flight if result is not None else None
    resolved_ballistics = (
        ballistics
        if ballistics is not None
        else (result.ballistics if result is not None else None)
    )
    return {
        "trajectory_3d": build_trajectory_3d_figure(flight),
        "kinematics": build_kinematics_figure(flight),
        "stability": build_stability_figure(flight),
        "aerodynamics": build_aerodynamics_figure(flight),
        "propulsion": build_propulsion_figure(flight, resolved_ballistics),
    }


def render_trajectory_3d_chart(flight: FlightResult | None) -> ui.plotly:
    """Render Panel 1 (3D Trajectory) with NiceGUI ui.plotly."""
    return ui.plotly(build_trajectory_3d_figure(flight)).classes("w-full")


def render_kinematics_chart(flight: FlightResult | None) -> ui.plotly:
    """Render Panel 2 (Kinematics) with NiceGUI ui.plotly."""
    return ui.plotly(build_kinematics_figure(flight)).classes("w-full")


def render_stability_chart(flight: FlightResult | None) -> ui.plotly:
    """Render Panel 3 (Stability) with NiceGUI ui.plotly."""
    return ui.plotly(build_stability_figure(flight)).classes("w-full")


def render_aerodynamics_chart(flight: FlightResult | None) -> ui.plotly:
    """Render Panel 4 (Aerodynamics) with NiceGUI ui.plotly."""
    return ui.plotly(build_aerodynamics_figure(flight)).classes("w-full")


def render_propulsion_chart(
    flight: FlightResult | None,
    ballistics: BallisticsResult | None = None,
) -> ui.plotly:
    """Render Panel 5 (Propulsion) with NiceGUI ui.plotly."""
    return ui.plotly(build_propulsion_figure(flight, ballistics)).classes("w-full")


def render_rocket_draw_panel(flight: FlightResult | None) -> ui.column:
    """Render RocketPy's rocket.draw() PNG diagram (rocket + mounted motor)."""
    panel = ui.column().classes("w-full items-center gap-2 py-2")
    with panel:
        draw_b64 = flight.rocket_draw_png_b64 if flight is not None else None
        if draw_b64:
            ui.label("Diagrama RocketPy (.draw) — Foguete com Motor Montado").classes(
                "text-sm font-semibold text-slate-700"
            )
            ui.image(f"data:image/png;base64,{draw_b64}").classes(
                "w-full max-w-5xl rounded border border-slate-200 bg-white"
            )
        else:
            ui.label(
                "Execute uma simulação para gerar o diagrama (.draw) do foguete com o motor."
            ).classes("text-sm text-slate-500 py-8")
    return panel


def render_telemetry_tabs(
    result: SimulationResult | None,
    *,
    ballistics: BallisticsResult | None = None,
) -> ui.column:
    """Render a 6-tab NiceGUI container hosting telemetry panels and rocket.draw()."""
    flight = result.flight if result is not None else None
    resolved_ballistics = (
        ballistics
        if ballistics is not None
        else (result.ballistics if result is not None else None)
    )

    container = ui.column().classes("w-full gap-2")
    with container:
        with ui.tabs().classes("w-full") as tabs:
            tab_traj = ui.tab("Trajetória 3D", icon="public")
            tab_kin = ui.tab("Cinemática", icon="speed")
            tab_stab = ui.tab("Estabilidade", icon="straighten")
            tab_aero = ui.tab("Aerodinâmica", icon="air")
            tab_prop = ui.tab("Propulsão", icon="local_fire_department")
            tab_draw = ui.tab("Foguete (.draw)", icon="rocket_launch")

        with ui.tab_panels(tabs, value=tab_traj).classes("w-full"):
            with ui.tab_panel(tab_traj):
                render_trajectory_3d_chart(flight)
            with ui.tab_panel(tab_kin):
                render_kinematics_chart(flight)
            with ui.tab_panel(tab_stab):
                render_stability_chart(flight)
            with ui.tab_panel(tab_aero):
                render_aerodynamics_chart(flight)
            with ui.tab_panel(tab_prop):
                render_propulsion_chart(flight, resolved_ballistics)
            with ui.tab_panel(tab_draw):
                render_rocket_draw_panel(flight)
    return container


__all__ = [
    "build_aerodynamics_figure",
    "build_all_panel_figures",
    "build_kinematics_figure",
    "build_propulsion_figure",
    "build_stability_figure",
    "build_trajectory_3d_figure",
    "render_aerodynamics_chart",
    "render_kinematics_chart",
    "render_propulsion_chart",
    "render_rocket_draw_panel",
    "render_stability_chart",
    "render_telemetry_tabs",
    "render_trajectory_3d_chart",
]
