"""Dedicated Configuration page for rocket structure, fins/nose/recovery, overrides, and metrics."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from nicegui import context, ui
from pydantic import ValidationError

from frontend.components import (
    BALLISTICS_METRIC_CATALOG,
    FLIGHT_METRIC_CATALOG,
    AerodynamicsView,
    render_aerodynamics_panel,
    render_metric_selector,
    render_motor_overrides_editor,
)
from frontend.state import AppState
from hefesto.domain import (
    AssetCategory,
    CasingScalingMode,
    DragSource,
    FinComponent,
    FinGeometryMode,
    GeometryValidationError,
    NoseConeKind,
    OrkImportSummary,
    ParachuteSpec,
    PointMassComponent,
    SafetyCriterion,
    SurfaceFinish,
    TubeComponent,
)
from hefesto.services import (
    CASING_MATERIAL_DENSITY_PRESETS,
    CASING_MATERIAL_LABELS,
    DEFAULT_MIN_CASE_SAFETY_FACTOR,
    DEFAULT_MOTOR_ID,
    SimulationServiceError,
    import_and_save_ork_rocket,
    list_ork_assets,
    preview_ork_import,
    preview_rocket_drag_curves,
    recalculate_rocket_structure,
    summarize_rocket_structure,
    sync_rocket_fins,
    update_rocket_motor_casing_length,
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


def _attach_client_cleanup(unsubscribe: Callable[[], None]) -> None:
    try:
        context.client.on_delete(unsubscribe)
    except RuntimeError:
        return


def _format_shape_points(points: tuple[tuple[float, float], ...]) -> str:
    return "; ".join(f"{x:.4g}, {y:.4g}" for x, y in points)


def _parse_shape_points(raw: str) -> tuple[tuple[float, float], ...]:
    pairs: list[tuple[float, float]] = []
    for chunk in raw.split(";"):
        cleaned = chunk.strip()
        if not cleaned:
            continue
        parts = [p.strip() for p in cleaned.split(",")]
        if len(parts) != 2:
            raise ValueError(f"Ponto inválido: {cleaned!r}. Use 'x, y; x, y; ...'")
        pairs.append((float(parts[0]), float(parts[1])))
    if len(pairs) < 3:
        raise ValueError("Informe pelo menos 3 pontos para o polígono das aletas.")
    return tuple(pairs)


def _set_target_safety_factor(state: AppState, raw_value: float | int | None) -> None:
    if raw_value is None:
        return
    numeric = float(raw_value)
    if numeric >= DEFAULT_MIN_CASE_SAFETY_FACTOR:
        state.casing_target_safety_factor = numeric


def render_config_page(state: AppState) -> ui.column:
    """Render the dedicated rocket structure, aerodynamics, overrides, and metrics config page."""
    if state.catalog is None:
        state.initialize()
    state.ensure_working_rocket()

    root = ui.column().classes("w-full gap-4")

    @ui.refreshable
    def render_structure_summary_card() -> None:
        rocket = state.ensure_working_rocket()
        summary = summarize_rocket_structure(rocket)
        override_val = (
            f"{rocket.dry_mass_override_kg:.3f} kg"
            if rocket.dry_mass_override_kg is not None
            else "não definida"
        )

        with ui.card().classes("w-full p-4 shadow-sm border-l-4 border-sky-500"):
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
                ui.label("Resumo Estrutural ao Vivo (Sem Motor)").classes(
                    "text-base font-semibold text-slate-800"
                )
                status_badge = (
                    "Alterações não salvas"
                    if state.has_unsaved_rocket_changes
                    else "Sincronizado"
                )
                ui.badge(
                    status_badge,
                    color="warning" if state.has_unsaved_rocket_changes else "positive",
                )

            with ui.grid(columns=4).classes(
                "w-full gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 mt-2"
            ):
                with ui.column().classes("gap-0"):
                    ui.label("Massa Seca Calculada").classes("text-xs text-slate-500")
                    ui.label(f"{summary.dry_mass_kg:.3f} kg").classes(
                        "text-lg font-bold text-slate-900"
                    )
                with ui.column().classes("gap-0"):
                    ui.label("CG sem Motor (nose_to_tail)").classes("text-xs text-slate-500")
                    ui.label(f"{summary.center_of_mass_m:.4f} m").classes(
                        "text-lg font-bold text-slate-900"
                    )
                with ui.column().classes("gap-0"):
                    ui.label("Inércia Transversal (I_t)").classes("text-xs text-slate-500")
                    ui.label(f"{summary.i_transverse_kg_m2:.3f} kg·m²").classes(
                        "text-lg font-bold text-slate-900"
                    )
                with ui.column().classes("gap-0"):
                    ui.label("Inércia Longitudinal (I_l)").classes("text-xs text-slate-500")
                    ui.label(f"{summary.i_longitudinal_kg_m2:.4f} kg·m²").classes(
                        "text-lg font-bold text-slate-900"
                    )

            if state.mass_mode == "measured":
                measured = rocket.dry_mass_override_kg is not None
                with ui.row().classes(
                    "w-full items-center gap-2 mt-2 p-2 rounded border "
                    + (
                        "bg-sky-50 border-sky-200"
                        if measured
                        else "bg-amber-50 border-amber-200"
                    )
                ):
                    ui.icon("scale" if measured else "warning_amber").classes(
                        "text-sky-700" if measured else "text-amber-700"
                    )
                    ui.label(
                        (
                            f"Modo Medida (measured): o voo 6-DOF usará a massa seca "
                            f"informada ({override_val}), não a massa calculada dos "
                            f"componentes."
                        )
                        if measured
                        else (
                            "Modo Medida (measured) exige o campo 'Massa Seca Medida (kg)' "
                            "preenchido; a simulação será bloqueada enquanto estiver vazio."
                        )
                    ).classes("text-xs font-medium text-slate-800")
            elif rocket.dry_mass_override_kg is not None:
                with ui.row().classes(
                    "w-full items-center gap-2 mt-2 p-2 rounded bg-amber-50 border border-amber-200"
                ):
                    ui.icon("warning_amber").classes("text-amber-700")
                    ui.label(
                        f"Modo Calculada (calculated): dry_mass_override_kg={override_val} "
                        "é IGNORADO e o voo 6-DOF usará a massa seca calculada dos componentes."
                    ).classes("text-xs font-medium text-amber-900")

    @ui.refreshable
    def render_components_section() -> None:
        rocket = state.ensure_working_rocket()
        indexed = sorted(
            enumerate(rocket.components),
            key=lambda pair: (pair[1].position_m, pair[0]),
        )
        tube_editors: dict[
            int,
            tuple[ui.input, ui.number, ui.number, ui.number, ui.number, ui.number],
        ] = {}
        pm_editors: dict[int, tuple[ui.input, ui.number, ui.number]] = {}

        def _apply_all_section_edits(*, notify_msg: str = "Todas as alterações aplicadas.") -> None:
            try:
                comps = list(state.ensure_working_rocket().components)
                for idx, (n_in, p_in, l_in, r_in, w_in, d_in) in tube_editors.items():
                    comps[idx] = TubeComponent(
                        name=(n_in.value or "").strip(),
                        position_m=float(p_in.value or 0.0),
                        length_m=float(l_in.value or 0.01),
                        outer_radius_m=float(r_in.value or 0.01),
                        wall_thickness_m=float(w_in.value or 0.001),
                        density_kg_m3=float(d_in.value or 1000.0),
                    )
                for idx, (n_in, p_in, m_in) in pm_editors.items():
                    comps[idx] = PointMassComponent(
                        name=(n_in.value or "").strip(),
                        position_m=float(p_in.value or 0.0),
                        mass_kg=float(m_in.value or 0.1),
                    )
                updated = recalculate_rocket_structure(
                    state.ensure_working_rocket().model_copy(
                        update={"components": tuple(comps)}
                    )
                )
                state.update_working_rocket(updated)
                render_components_section.refresh()
                render_structure_summary_card.refresh()
                ui.notify(notify_msg, type="positive")
            except (ValidationError, ValueError) as exc:
                ui.notify(f"Componente inválido: {exc}", type="negative")

        with ui.card().classes("w-full p-4 shadow-sm"):
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 mb-3"):
                ui.label("Seção A — Estrutura do Foguete (Módulos e Junções)").classes(
                    "text-base font-semibold text-slate-800"
                )
                with ui.row().classes("items-center gap-2 flex-wrap"):
                    def _add_tube() -> None:
                        new_tube = TubeComponent(
                            name="Novo Módulo",
                            outer_radius_m=rocket.radius_m,
                            wall_thickness_m=0.002,
                            length_m=0.20,
                            density_kg_m3=1850.0,
                            position_m=1.0,
                        )
                        updated = recalculate_rocket_structure(
                            rocket.model_copy(update={"components": (*rocket.components, new_tube)})
                        )
                        state.update_working_rocket(updated)
                        render_components_section.refresh()
                        render_structure_summary_card.refresh()

                    def _add_point_mass() -> None:
                        new_pm = PointMassComponent(
                            name="Nova Junção / Massa",
                            mass_kg=0.25,
                            position_m=1.0,
                        )
                        updated = recalculate_rocket_structure(
                            rocket.model_copy(update={"components": (*rocket.components, new_pm)})
                        )
                        state.update_working_rocket(updated)
                        render_components_section.refresh()
                        render_structure_summary_card.refresh()

                    ui.button(
                        "Aplicar todas as alterações da seção",
                        icon="done_all",
                        on_click=lambda: _apply_all_section_edits(),
                    ).props("size=sm color=positive")
                    ui.button("Adicionar Módulo (Tube)", icon="add", on_click=_add_tube).props(
                        "outline size=sm color=primary"
                    )
                    ui.button(
                        "Adicionar Junção / Massa",
                        icon="add",
                        on_click=_add_point_mass,
                    ).props("outline size=sm color=secondary")

            with ui.column().classes("w-full gap-2"):
                for orig_idx, comp in indexed:
                    if isinstance(comp, FinComponent):
                        with ui.row().classes(
                            "w-full items-center justify-between bg-slate-100 rounded p-2"
                        ):
                            ui.label(
                                f"[Aletas] {comp.name} · pos={comp.position_m:.3f} m · "
                                f"count={comp.count} (editável na Seção B)"
                            ).classes("text-xs text-slate-600")
                        continue

                    with ui.card().classes("w-full p-3 bg-slate-50 border border-slate-200"):
                        with ui.row().classes("w-full items-end gap-2 flex-wrap"):
                            name_in = ui.input(label="Nome", value=comp.name).classes("w-44")
                            pos_in = ui.number(
                                label="Posição (m)",
                                value=comp.position_m,
                                min=0.0,
                                step=0.01,
                                format="%.4f",
                            ).classes("w-28")

                            if isinstance(comp, TubeComponent):
                                len_in = ui.number(
                                    label="Compr. (m)",
                                    value=comp.length_m,
                                    min=0.001,
                                    step=0.01,
                                    format="%.4f",
                                ).classes("w-28")
                                rad_in = ui.number(
                                    label="Raio Ext. (m)",
                                    value=comp.outer_radius_m,
                                    min=0.001,
                                    step=0.001,
                                    format="%.4f",
                                ).classes("w-28")
                                wall_in = ui.number(
                                    label="Espessura (m)",
                                    value=comp.wall_thickness_m,
                                    min=0.0005,
                                    step=0.001,
                                    format="%.4f",
                                ).classes("w-28")
                                dens_in = ui.number(
                                    label="Dens. (kg/m³)",
                                    value=comp.density_kg_m3,
                                    min=1.0,
                                    step=50.0,
                                ).classes("w-28")
                                tube_editors[orig_idx] = (
                                    name_in,
                                    pos_in,
                                    len_in,
                                    rad_in,
                                    wall_in,
                                    dens_in,
                                )

                                ui.button(
                                    icon="check",
                                    on_click=lambda: _apply_all_section_edits(
                                        notify_msg="Módulo atualizado."
                                    ),
                                ).props("flat dense round color=positive")
                            elif isinstance(comp, PointMassComponent):
                                mass_in = ui.number(
                                    label="Massa (kg)",
                                    value=comp.mass_kg,
                                    min=0.001,
                                    step=0.05,
                                    format="%.4f",
                                ).classes("w-32")
                                pm_editors[orig_idx] = (name_in, pos_in, mass_in)

                                ui.button(
                                    icon="check",
                                    on_click=lambda: _apply_all_section_edits(
                                        notify_msg="Junção/massa atualizada."
                                    ),
                                ).props("flat dense round color=positive")

                            def _remove_comp(target_idx: int = orig_idx) -> None:
                                cur = state.ensure_working_rocket()
                                if len(cur.components) <= 1:
                                    ui.notify(
                                        "O foguete deve manter pelo menos 1 componente.",
                                        type="warning",
                                    )
                                    return
                                remaining = tuple(
                                    c for idx, c in enumerate(cur.components) if idx != target_idx
                                )
                                updated = recalculate_rocket_structure(
                                    cur.model_copy(update={"components": remaining})
                                )
                                state.update_working_rocket(updated)
                                render_components_section.refresh()
                                render_structure_summary_card.refresh()

                            ui.button(icon="delete", on_click=_remove_comp).props(
                                "flat dense round color=negative"
                            )

    @ui.refreshable
    def render_aero_recovery_section() -> None:
        rocket = state.ensure_working_rocket()
        fins = rocket.fins
        fin_comp = next((c for c in rocket.components if isinstance(c, FinComponent)), None)
        nose = rocket.nose_cone

        with ui.card().classes("w-full p-4 shadow-sm"):
            ui.label("Seção B — Aletas, Ogiva e Recuperação").classes(
                "text-base font-semibold text-slate-800 mb-3"
            )
            ui.label(
                f"Modo geométrico ativo: {state.fin_geometry_mode} "
                "(alterar abaixo atualiza FinSetSpec e FinComponent em sincronia)."
            ).classes("text-xs text-slate-600 mb-2")

            with ui.grid(columns=4).classes(
                "w-full gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
            ):
                fin_mode_sel = ui.select(
                    options={"freeform": "Freeform", "trapezoidal": "Trapezoidal"},
                    value=state.fin_geometry_mode,
                    label="FinGeometryMode",
                ).classes("w-full")
                fin_count_in = ui.number(
                    label="Qtd. de Aletas", value=fins.count, min=1, step=1
                ).classes("w-full")
                fin_pos_in = ui.number(
                    label="Posição das Aletas (m)",
                    value=fins.position_m,
                    min=0.0,
                    step=0.01,
                    format="%.4f",
                ).classes("w-full")
                fin_cant_in = ui.number(
                    label="Cant Angle (deg)",
                    value=fins.cant_angle_deg,
                    min=-45.0,
                    max=45.0,
                    step=0.5,
                ).classes("w-full")

                fin_thick_in = ui.number(
                    label="Espessura da Aleta (m)",
                    value=fin_comp.thickness_m if fin_comp else 0.004,
                    min=0.0005,
                    step=0.001,
                    format="%.4f",
                ).classes("w-full")
                fin_dens_in = ui.number(
                    label="Densidade da Aleta (kg/m³)",
                    value=fin_comp.density_kg_m3 if fin_comp else 2700.0,
                    min=1.0,
                    step=50.0,
                ).classes("w-full")
                root_in = ui.number(
                    label="Root Chord (m)",
                    value=fins.root_chord_m if fins.root_chord_m is not None else 0.18,
                    min=0.01,
                    step=0.01,
                ).classes("w-full")
                tip_in = ui.number(
                    label="Tip Chord (m)",
                    value=fins.tip_chord_m if fins.tip_chord_m is not None else 0.14,
                    min=0.0,
                    step=0.01,
                ).classes("w-full")
                span_in = ui.number(
                    label="Span (m)",
                    value=fins.span_m if fins.span_m is not None else 0.14,
                    min=0.01,
                    step=0.01,
                ).classes("w-full")
                sweep_in = ui.number(
                    label="Sweep Length (m)",
                    value=fins.sweep_length_m if fins.sweep_length_m is not None else 0.07,
                    step=0.01,
                ).classes("w-full")

            points_in = ui.input(
                label="Pontos Freeform (x, y; ... em metros)",
                value=_format_shape_points(fins.shape_points_m),
            ).classes("w-full mt-2")

            def _apply_fins() -> None:
                mode: FinGeometryMode = (
                    "trapezoidal" if fin_mode_sel.value == "trapezoidal" else "freeform"
                )
                state.fin_geometry_mode = mode
                try:
                    parsed_points = (
                        fins.shape_points_m
                        if mode == "trapezoidal"
                        else _parse_shape_points(points_in.value or "")
                    )
                    new_fins = fins.model_copy(
                        update={
                            "count": int(fin_count_in.value or 4),
                            "position_m": float(fin_pos_in.value or 0.0),
                            "cant_angle_deg": float(fin_cant_in.value or 0.0),
                            "shape_points_m": parsed_points,
                            "root_chord_m": (
                                float(root_in.value) if root_in.value is not None else None
                            ),
                            "tip_chord_m": (
                                float(tip_in.value) if tip_in.value is not None else None
                            ),
                            "span_m": float(span_in.value) if span_in.value is not None else None,
                            "sweep_length_m": (
                                float(sweep_in.value) if sweep_in.value is not None else None
                            ),
                        }
                    )
                    updated = sync_rocket_fins(
                        state.ensure_working_rocket(),
                        new_fins,
                        thickness_m=float(fin_thick_in.value or 0.004),
                        density_kg_m3=float(fin_dens_in.value or 2700.0),
                        fin_geometry_mode=mode,
                    )
                    state.update_working_rocket(updated)
                    render_aero_recovery_section.refresh()
                    render_components_section.refresh()
                    render_structure_summary_card.refresh()
                    ui.notify("Aletas sincronizadas com sucesso.", type="positive")
                except (ValidationError, ValueError) as exc:
                    ui.notify(f"Erro nas aletas: {exc}", type="negative")

            ui.button("Aplicar Aletas", icon="check", on_click=_apply_fins).props(
                "outline color=primary"
            ).classes("mt-2")

            ui.separator().classes("my-3")

            with ui.grid(columns=3).classes("w-full gap-3 grid-cols-1 sm:grid-cols-3"):
                nose_kind_sel = ui.select(
                    options={k.value: k.name for k in NoseConeKind},
                    value=nose.kind.value,
                    label="Perfil da Ogiva",
                ).classes("w-full")
                nose_len_in = ui.number(
                    label="Comprimento da Ogiva (m)",
                    value=nose.length_m,
                    min=0.01,
                    step=0.01,
                    format="%.4f",
                ).classes("w-full")
                nose_pos_in = ui.number(
                    label="Posição da Ogiva (m)",
                    value=nose.position_m,
                    min=0.0,
                    step=0.01,
                    format="%.4f",
                ).classes("w-full")

            def _apply_nose() -> None:
                try:
                    new_nose = nose.model_copy(
                        update={
                            "kind": NoseConeKind(str(nose_kind_sel.value)),
                            "length_m": float(nose_len_in.value or 0.45),
                            "position_m": float(nose_pos_in.value or 0.0),
                        }
                    )
                    updated = recalculate_rocket_structure(
                        state.ensure_working_rocket().model_copy(
                            update={"nose_cone": new_nose}
                        )
                    )
                    state.update_working_rocket(updated)
                    ui.notify("Ogiva atualizada.", type="positive")
                except (ValidationError, ValueError) as exc:
                    ui.notify(f"Erro na ogiva: {exc}", type="negative")

            ui.button("Aplicar Ogiva", icon="check", on_click=_apply_nose).props(
                "outline color=primary"
            ).classes("mt-2")

            ui.separator().classes("my-3")
            ui.label("Paraquedas").classes("text-sm font-semibold text-slate-700 mb-2")

            for p_idx, chute in enumerate(rocket.parachutes):
                with ui.row().classes("w-full items-end gap-2 flex-wrap mb-2"):
                    ui.label(chute.name).classes("w-28 text-sm font-medium text-slate-700")
                    cds_in = ui.number(
                        label="Cd·S (m²)",
                        value=chute.cd_s_m2,
                        min=0.01,
                        step=0.05,
                    ).classes("w-32")
                    trig_in = ui.input(
                        label="Gatilho ('apogee' ou m)",
                        value=str(chute.trigger),
                    ).classes("w-40")
                    lag_in = ui.number(
                        label="Atraso (s)",
                        value=chute.lag_s,
                        min=0.0,
                        step=0.1,
                    ).classes("w-28")

                    def _apply_chute(
                        target_idx: int = p_idx,
                        c_in: ui.number = cds_in,
                        t_in: ui.input = trig_in,
                        l_in: ui.number = lag_in,
                        base_chute: ParachuteSpec = chute,
                    ) -> None:
                        try:
                            raw_trig = (t_in.value or "").strip()
                            parsed_trig: Literal["apogee"] | float = (
                                "apogee" if raw_trig.lower() == "apogee" else float(raw_trig)
                            )
                            new_chute = base_chute.model_copy(
                                update={
                                    "cd_s_m2": float(c_in.value or 1.0),
                                    "trigger": parsed_trig,
                                    "lag_s": float(l_in.value or 0.0),
                                }
                            )
                            chutes = list(state.ensure_working_rocket().parachutes)
                            chutes[target_idx] = new_chute
                            updated = state.ensure_working_rocket().model_copy(
                                update={"parachutes": tuple(chutes)}
                            )
                            state.update_working_rocket(updated)
                            ui.notify(
                                f"Paraquedas '{base_chute.name}' atualizado.",
                                type="positive",
                            )
                        except (ValidationError, ValueError) as exc:
                            ui.notify(f"Erro no paraquedas: {exc}", type="negative")

                    ui.button(icon="check", on_click=_apply_chute).props(
                        "flat dense round color=positive"
                    )

    @ui.refreshable
    def render_motor_casing_section() -> None:
        rocket = state.ensure_working_rocket()
        casing = rocket.motor.casing
        hardware_mass_kg = state.fixed_hardware_mass_kg()

        with ui.card().classes("w-full p-4 shadow-sm"):
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 mb-3"):
                ui.label("Carcaça e Massa do Motor").classes(
                    "text-base font-semibold text-slate-800"
                )

                def _restore_casing() -> None:
                    try:
                        state.restore_motor_casing_from_preset()
                        render_structure_summary_card.refresh()
                        render_motor_casing_section.refresh()
                        ui.notify("Carcaça restaurada do preset.", type="info")
                    except (FileNotFoundError, ValueError) as exc:
                        ui.notify(f"Falha ao restaurar carcaça: {exc}", type="negative")

                ui.button(
                    "Restaurar carcaça do preset",
                    icon="restart_alt",
                    on_click=_restore_casing,
                ).props("outline size=sm color=grey")

            with ui.grid(columns=3).classes(
                "w-full gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
            ):
                length_in = ui.number(
                    label="Comprimento da carcaça (m)",
                    value=casing.length_m,
                    min=0.01,
                    step=0.01,
                    format="%.4f",
                ).classes("w-full")

                wall_in = ui.number(
                    label="Espessura da parede (mm)",
                    value=casing.wall_thickness_m * 1000.0,
                    min=0.2,
                    step=0.1,
                    format="%.2f",
                ).classes("w-full")

                hardware_in = ui.number(
                    label="Hardware fixo / fechamentos (kg)",
                    value=hardware_mass_kg,
                    min=0.0,
                    step=0.1,
                    format="%.3f",
                ).classes("w-full")

                mode_select = ui.select(
                    options={
                        "tubular_delta": "Delta tubular por material (padrão)",
                        "proportional": "Proporcional",
                        "manual": "Manual",
                    },
                    value=state.casing_scaling_mode,
                    label="Modo de atualização de massa",
                ).classes("w-full")

                material_select = ui.select(
                    options=CASING_MATERIAL_LABELS,
                    value=state.casing_material_preset,
                    label="Material da carcaça",
                ).classes("w-full")

                density_in = ui.number(
                    label="Densidade (kg/m³)",
                    value=state.casing_density_kg_m3,
                    min=100.0,
                    step=50.0,
                    format="%.1f",
                ).classes("w-full")
                if state.casing_scaling_mode != "tubular_delta":
                    density_in.disable()

                clearance_in = ui.number(
                    label="Folga interna (m)",
                    value=casing.internal_clearance_m,
                    min=0.0,
                    step=0.005,
                    format="%.4f",
                ).classes("w-full")

                grain_sep_in = ui.number(
                    label="Separação entre grãos (m)",
                    value=rocket.motor.grain_separation_m,
                    min=0.0,
                    step=0.002,
                    format="%.4f",
                ).classes("w-full")

                motor_pos_in = ui.number(
                    label="Posição do motor no foguete (m)",
                    value=rocket.motor_position_m,
                    min=0.0,
                    step=0.02,
                    format="%.4f",
                ).classes("w-full")

            @ui.refreshable
            def _render_casing_feedback() -> None:
                cur_rocket = state.ensure_working_rocket()
                cur_casing = cur_rocket.motor.casing
                resize_res = state.last_casing_resize_result
                if resize_res is None:
                    _, resize_res = update_rocket_motor_casing_length(
                        cur_rocket,
                        cur_casing.length_m,
                        mode=state.casing_scaling_mode,
                        material_density_kg_m3=state.casing_density_kg_m3,
                    )

                with ui.column().classes(
                    "w-full gap-2 mt-3 p-3 rounded bg-slate-50 border border-slate-200"
                ):
                    with ui.row().classes("w-full gap-2 flex-wrap"):
                        ui.badge(
                            f"Massa seca: {cur_casing.dry_mass_kg:.3f} kg",
                            color="primary",
                        )
                        ui.badge(
                            f"Δ massa: {resize_res.delta_mass_kg:+.4f} kg",
                            color="secondary",
                        )
                        ui.badge(
                            f"Tubo est.: {resize_res.estimated_tube_mass_kg:.3f} kg",
                            color="info",
                        )
                        ui.badge(
                            f"Hardware fixo est.: "
                            f"{resize_res.estimated_fixed_hardware_mass_kg:.3f} kg",
                            color="info",
                        )
                        ui.badge(
                            f"CG seco: {cur_casing.center_of_dry_mass_m:.4f} m",
                            color="dark",
                        )
                        ui.badge(
                            f"Inércia: ({cur_casing.dry_inertia_kg_m2[0]:.4f}, "
                            f"{cur_casing.dry_inertia_kg_m2[2]:.5f}) kg·m²",
                            color="dark",
                        )

                    for warn in resize_res.warnings:
                        with ui.row().classes(
                            "w-full items-center gap-2 p-2 rounded bg-amber-50 "
                            "border border-amber-200"
                        ):
                            ui.icon("warning_amber").classes("text-amber-700 text-sm")
                            ui.label(warn).classes("text-xs text-amber-900")

            def _apply_casing_changes() -> None:
                try:
                    raw_mode = str(mode_select.value or "tubular_delta")
                    selected_mode: CasingScalingMode = (
                        "proportional"
                        if raw_mode == "proportional"
                        else ("manual" if raw_mode == "manual" else "tubular_delta")
                    )
                    if selected_mode == "tubular_delta":
                        density_in.enable()
                    else:
                        density_in.disable()

                    new_len = float(length_in.value or casing.length_m)
                    density_val = float(density_in.value or state.casing_density_kg_m3)
                    clearance_val = float(
                        clearance_in.value
                        if clearance_in.value is not None
                        else casing.internal_clearance_m
                    )
                    grain_sep_val = float(
                        grain_sep_in.value
                        if grain_sep_in.value is not None
                        else rocket.motor.grain_separation_m
                    )
                    motor_pos_val = float(
                        motor_pos_in.value
                        if motor_pos_in.value is not None
                        else rocket.motor_position_m
                    )
                    wall_val_m = float(
                        wall_in.value
                        if wall_in.value is not None
                        else casing.wall_thickness_m * 1000.0
                    ) / 1000.0
                    hardware_val_kg = float(
                        hardware_in.value
                        if hardware_in.value is not None
                        else hardware_mass_kg
                    )
                    state.apply_motor_casing_update(
                        new_length_m=new_len,
                        mode=selected_mode,
                        material_density_kg_m3=density_val,
                        motor_position_m=motor_pos_val,
                        grain_separation_m=grain_sep_val,
                        internal_clearance_m=clearance_val,
                        wall_thickness_m=wall_val_m,
                        fixed_hardware_mass_kg=hardware_val_kg,
                    )
                    render_structure_summary_card.refresh()
                    _render_casing_feedback.refresh()
                except (GeometryValidationError, ValidationError, ValueError) as exc:
                    ui.notify(f"Erro na carcaça do motor: {exc}", type="negative")

            def _on_material_change(new_mat: str) -> None:
                state.casing_material_preset = new_mat
                if new_mat in CASING_MATERIAL_DENSITY_PRESETS:
                    preset_rho = CASING_MATERIAL_DENSITY_PRESETS[new_mat]
                    density_in.value = preset_rho
                    state.casing_density_kg_m3 = preset_rho
                _apply_casing_changes()

            material_select.on_value_change(lambda e: _on_material_change(str(e.value)))
            mode_select.on_value_change(lambda _: _apply_casing_changes())
            length_in.on_value_change(lambda _: _apply_casing_changes())
            wall_in.on_value_change(lambda _: _apply_casing_changes())
            hardware_in.on_value_change(lambda _: _apply_casing_changes())
            density_in.on_value_change(lambda _: _apply_casing_changes())
            clearance_in.on_value_change(lambda _: _apply_casing_changes())
            grain_sep_in.on_value_change(lambda _: _apply_casing_changes())
            motor_pos_in.on_value_change(lambda _: _apply_casing_changes())

            _render_casing_feedback()

            def _on_auto_size_wall() -> None:
                try:
                    target_fs = float(fs_in.value or state.casing_target_safety_factor)
                    updated = state.auto_size_motor_casing_wall(target_fs)
                    wall_in.value = updated.motor.casing.wall_thickness_m * 1000.0
                    hardware_in.value = state.fixed_hardware_mass_kg()
                    state.run_motor_check()
                except (
                    FileNotFoundError,
                    GeometryValidationError,
                    SimulationServiceError,
                    ValueError,
                ) as exc:
                    ui.notify(f"Falha no dimensionamento: {exc}", type="negative")
                    return
                render_structure_summary_card.refresh()
                _render_casing_feedback.refresh()
                wall_mm = updated.motor.casing.wall_thickness_m * 1000.0
                if state.last_error:
                    ui.notify(
                        f"Parede {wall_mm:.1f} mm aplicada, mas o motor check falhou: "
                        f"{state.last_error}",
                        type="warning",
                    )
                    return
                fs_check = next(
                    (
                        check
                        for check in (state.safety_preview.checks if state.safety_preview else ())
                        if check.criterion == SafetyCriterion.CASE_SAFETY_FACTOR
                    ),
                    None,
                )
                fs_text = (
                    f"{fs_check.value:.2f}"
                    if fs_check is not None and fs_check.value is not None
                    else "N/D"
                )
                ui.notify(
                    f"Parede mínima: {wall_mm:.1f} mm · FS {fs_text} · "
                    f"massa seca do motor {updated.motor.casing.dry_mass_kg:.3f} kg",
                    type="positive",
                )

            with ui.row().classes("w-full items-center gap-3 mt-3 flex-wrap"):
                fs_in = ui.number(
                    label="FS Alvo",
                    value=state.casing_target_safety_factor,
                    min=DEFAULT_MIN_CASE_SAFETY_FACTOR,
                    step=0.1,
                    format="%.2f",
                    on_change=lambda e: _set_target_safety_factor(state, e.value),
                ).classes("w-40")
                ui.button(
                    "Dimensionar parede mínima",
                    icon="straighten",
                    on_click=_on_auto_size_wall,
                ).props("outline size=sm color=primary")

    @ui.refreshable
    def render_aerodynamics_section() -> None:
        rocket = state.ensure_working_rocket()
        try:
            table = preview_rocket_drag_curves(rocket)
        except ValueError as exc:
            with ui.card().classes("w-full p-4 border-l-4 border-rose-500 bg-rose-50"):
                ui.label("Falha ao materializar as curvas Cd(Mach)").classes(
                    "text-sm font-semibold text-rose-900"
                )
                ui.label(str(exc)).classes("text-xs text-rose-800")
            return

        def _on_source_change(drag_source: DragSource) -> None:
            try:
                state.set_working_drag_source(drag_source)
                ui.notify(f"Fonte de arrasto ativa: {drag_source}", type="positive")
            except (FileNotFoundError, ValueError) as exc:
                ui.notify(f"Fonte indisponível: {exc}", type="negative")
                render_aerodynamics_section.refresh()

        def _on_finish_change(finish: SurfaceFinish) -> None:
            state.set_working_surface_finish(finish)
            ui.notify(f"Acabamento superficial: {finish.value}", type="info")

        def _on_csv_import(csv_content: str, filename: str) -> None:
            try:
                state.import_rasaero_csv(csv_content, filename)
                ui.notify(f"CSV do RASAero II importado: {filename}", type="positive")
            except (FileNotFoundError, ValueError) as exc:
                ui.notify(f"CSV do RASAero II inválido: {exc}", type="negative")
                render_aerodynamics_section.refresh()

        def _on_alpha_change(alpha_deg: float) -> None:
            try:
                state.set_rasaero_alpha(alpha_deg)
                ui.notify(f"Ângulo de ataque aplicado: {alpha_deg:g}°", type="info")
            except (FileNotFoundError, ValueError) as exc:
                ui.notify(f"Falha ao trocar o ângulo de ataque: {exc}", type="negative")
                render_aerodynamics_section.refresh()

        def _on_chart_range_change(max_mach: float) -> None:
            state.drag_chart_max_mach = max_mach
            state.notify()

        render_aerodynamics_panel(
            AerodynamicsView(
                rocket=rocket,
                table=table,
                ork_table_available=state.preset_ork_drag_table() is not None,
                rasaero_alpha_options=state.rasaero_alpha_options,
                rasaero_alpha_deg=state.rasaero_alpha_deg,
                rasaero_filename=(
                    state.rasaero_csv_filename if state.rasaero_csv_content else None
                ),
                rasaero_mach_range=state.rasaero_mach_range,
                chart_max_mach=state.drag_chart_max_mach,
            ),
            on_source_change=_on_source_change,
            on_finish_change=_on_finish_change,
            on_csv_import=_on_csv_import,
            on_alpha_change=_on_alpha_change,
            on_chart_range_change=_on_chart_range_change,
        )

    with root:
        uploaded_ork: dict[str, bytes | str | None] = {"bytes": None, "filename": None}
        ork_preview_state: dict[str, OrkImportSummary | None] = {"summary": None}

        ork_dialog = ui.dialog()
        with ork_dialog, ui.card().classes("w-full max-w-3xl p-5 gap-3"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Importar Foguete do OpenRocket (.ork)").classes(
                    "text-lg font-semibold text-slate-800"
                )
                ui.button(icon="close", on_click=ork_dialog.close).props("flat round dense")

            catalog = state.catalog
            motor_choices = list(state.available_motor_ids()) or [DEFAULT_MOTOR_ID]
            drag_choices = (
                [entry.relative_path for entry in catalog.assets_for(AssetCategory.DRAG)]
                if catalog
                else ["power_off.csv", "power_on.csv"]
            )
            if not drag_choices:
                drag_choices = ["power_off.csv", "power_on.csv"]
            default_off = "power_off.csv" if "power_off.csv" in drag_choices else drag_choices[0]
            default_on = "power_on.csv" if "power_on.csv" in drag_choices else drag_choices[-1]

            saved_ork_assets = list(list_ork_assets(repo_root=state.repo_root))
            saved_ork_select = ui.select(
                options=saved_ork_assets,
                value=saved_ork_assets[0] if saved_ork_assets else None,
                label="Ou escolher .ork salvo em data/assets/openrocket/",
                clearable=True,
            ).classes("w-full")

            ork_status_lbl = ui.label("Nenhum arquivo .ork enviado nesta sessão.").classes(
                "text-xs text-slate-500"
            )

            async def _on_ork_upload(e) -> None:  # type: ignore[no-untyped-def]
                raw = await e.file.read()
                uploaded_ork["bytes"] = raw
                uploaded_ork["filename"] = e.file.name
                ork_status_lbl.set_text(
                    f"Arquivo carregado: {e.file.name} ({len(raw) / 1024.0:.1f} KB)"
                )

            ui.upload(
                label="Enviar arquivo .ork",
                auto_upload=True,
                on_upload=_on_ork_upload,
            ).props('accept=".ork"').classes("w-full")

            with ui.grid(columns=2).classes("w-full gap-3 grid-cols-1 sm:grid-cols-2"):
                ork_id_in = ui.input(
                    label="ID do novo preset (slug)",
                    placeholder="meu_foguete_ork",
                ).classes("w-full")
                ork_name_in = ui.input(
                    label="Nome de exibição (opcional)",
                    placeholder="Meu Foguete",
                ).classes("w-full")
                ork_overwrite_switch = ui.checkbox(
                    "Sobrescrever preset/.ork existente (destrutivo)",
                    value=False,
                ).classes("text-xs text-amber-900")
                default_motor = (
                    state.selected_motor_id
                    if state.selected_motor_id in motor_choices
                    else motor_choices[0]
                )
                ork_motor_sel = ui.select(
                    options=motor_choices,
                    value=default_motor,
                    label="Motor base",
                ).classes("w-full")
                ork_drag_off_sel = ui.select(
                    options=drag_choices,
                    value=default_off,
                    label="Arrasto Power-Off (.csv)",
                ).classes("w-full")
                ork_drag_on_sel = ui.select(
                    options=drag_choices,
                    value=default_on,
                    label="Arrasto Power-On (.csv)",
                ).classes("w-full")

            @ui.refreshable
            def render_ork_preview() -> None:
                summary = ork_preview_state["summary"]
                if summary is None:
                    return
                spec = summary.rocket_spec
                tube_count = sum(1 for c in spec.components if isinstance(c, TubeComponent))
                pm_count = sum(1 for c in spec.components if isinstance(c, PointMassComponent))
                with ui.card().classes("w-full p-3 bg-slate-50 border border-slate-200 gap-2"):
                    with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
                        ui.label(f"Prévia: {spec.name}").classes(
                            "text-sm font-semibold text-slate-800"
                        )
                        ui.badge(
                            "Cache SHA-256" if summary.from_cache else "Parse XML Novo",
                            color="info" if summary.from_cache else "positive",
                        )
                    ui.label(
                        f"Massa Seca: {summary.calculated_dry_mass_kg:.3f} kg · "
                        f"CG sem motor: {summary.center_of_mass_without_motor_m:.4f} m · "
                        f"Raio: {spec.radius_m * 1000.0:.1f} mm"
                    ).classes("text-xs text-slate-700")
                    ui.label(
                        f"Componentes: {tube_count} tubos/anéis · {pm_count} massas · "
                        f"{spec.fins.count} aletas · {len(spec.parachutes)} paraquedas · "
                        f"datapoints={summary.stored_datapoint_count}"
                    ).classes("text-xs text-slate-600")
                    if summary.warnings:
                        with ui.column().classes("w-full gap-1 max-h-40 overflow-y-auto"):
                            for w in summary.warnings:
                                color = (
                                    "text-amber-800"
                                    if w.severity == "warning"
                                    else "text-sky-800"
                                )
                                msg = f"[{w.severity.upper()}] {w.component_name}: {w.message}"
                                ui.label(msg).classes(f"text-xs {color}")

            render_ork_preview()

            def _resolve_ork_source() -> bytes | str:
                raw = uploaded_ork["bytes"]
                if isinstance(raw, bytes) and raw:
                    return raw
                if saved_ork_select.value:
                    return str(saved_ork_select.value)
                raise ValueError("Envie um arquivo .ork ou selecione um arquivo salvo.")

            def _analyze_ork() -> None:
                try:
                    source = _resolve_ork_source()
                    summary = preview_ork_import(
                        source,
                        base_motor_id=str(ork_motor_sel.value or motor_choices[0]),
                        power_off_drag_asset=str(ork_drag_off_sel.value or default_off),
                        power_on_drag_asset=str(ork_drag_on_sel.value or default_on),
                        repo_root=state.repo_root,
                    )
                    ork_preview_state["summary"] = summary
                    if not (ork_id_in.value or "").strip():
                        slug_guess = (
                            summary.rocket_spec.name.lower()
                            .replace(" ", "_")
                            .replace("-", "_")
                        )
                        ork_id_in.set_value(slug_guess)
                    render_ork_preview.refresh()
                    ui.notify("Arquivo .ork analisado com sucesso.", type="positive")
                except (FileNotFoundError, ValueError) as exc:
                    ui.notify(f"Falha ao analisar .ork: {exc}", type="negative")

            def _export_ork() -> None:
                try:
                    source = _resolve_ork_source()
                    summary = import_and_save_ork_rocket(
                        source,
                        rocket_id=(ork_id_in.value or "").strip(),
                        base_motor_id=str(ork_motor_sel.value or motor_choices[0]),
                        power_off_drag_asset=str(ork_drag_off_sel.value or default_off),
                        power_on_drag_asset=str(ork_drag_on_sel.value or default_on),
                        rocket_name=(ork_name_in.value or "").strip() or None,
                        overwrite=bool(ork_overwrite_switch.value),
                        repo_root=state.repo_root,
                    )
                    state.refresh_catalog()
                    if summary.rocket_id is not None:
                        state.load_rocket_into_config(summary.rocket_id)
                    render_rocket_selector_row.refresh()
                    render_structure_summary_card.refresh()
                    render_components_section.refresh()
                    render_aero_recovery_section.refresh()
                    render_motor_casing_section.refresh()
                    ork_dialog.close()
                    ui.notify(
                        f"Foguete '{summary.rocket_id}' importado e selecionado.",
                        type="positive",
                    )
                except FileExistsError as exc:
                    ui.notify(
                        f"ID/.ork já existe: {exc} Marque 'Sobrescrever preset/.ork "
                        "existente' para confirmar.",
                        type="warning",
                    )
                except (FileNotFoundError, ValueError, OSError) as exc:
                    ui.notify(f"Falha ao exportar .ork: {exc}", type="negative")

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Analisar .ork", icon="search", on_click=_analyze_ork).props(
                    "outline color=primary"
                )
                ui.button(
                    "Exportar para o Banco e Selecionar",
                    icon="save_alt",
                    on_click=_export_ork,
                ).props("color=positive")

        @ui.refreshable
        def render_rocket_selector_row() -> None:
            rocket_options = (
                list(state.catalog.rocket_presets)
                if state.catalog and state.catalog.rocket_presets
                else [state.selected_rocket_id]
            )

            def _on_select_rocket(new_id: str) -> None:
                if not new_id or new_id == state.selected_rocket_id:
                    return
                try:
                    state.load_rocket_into_config(new_id)
                    render_structure_summary_card.refresh()
                    render_components_section.refresh()
                    render_aero_recovery_section.refresh()
                    render_motor_casing_section.refresh()
                    ui.notify(f"Foguete '{new_id}' carregado na configuração.", type="info")
                except (FileNotFoundError, ValueError) as exc:
                    ui.notify(f"Erro ao carregar foguete '{new_id}': {exc}", type="negative")

            with ui.row().classes("w-full items-center justify-between flex-wrap gap-3 mb-2"):
                ui.select(
                    options=rocket_options,
                    value=state.selected_rocket_id,
                    label="Foguete do Catálogo",
                    on_change=lambda e: _on_select_rocket(str(e.value)),
                ).classes("w-64")
                ui.button(
                    "Importar .ork (OpenRocket)",
                    icon="upload_file",
                    on_click=ork_dialog.open,
                ).props("outline color=primary")

        with ui.card().classes("w-full p-4 shadow-sm"):
            render_rocket_selector_row()
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-3"):
                ui.label("Configuração Detalhada — Foguete, Motor e Métricas").classes(
                    "text-lg font-semibold text-slate-800"
                )
                with ui.row().classes("items-center gap-2 flex-wrap"):
                    def _use_in_session() -> None:
                        state.compose_config()
                        ui.notify("Configuração aplicada à sessão atual.", type="positive")

                    def _restore_preset() -> None:
                        state.reset_working_rocket()
                        render_structure_summary_card.refresh()
                        render_components_section.refresh()
                        render_aero_recovery_section.refresh()
                        render_motor_casing_section.refresh()
                        ui.notify("Preset restaurado.", type="info")

                    ui.button(
                        "Usar nesta sessão",
                        icon="play_circle",
                        on_click=_use_in_session,
                    ).props("color=primary")
                    ui.button(
                        "Restaurar preset",
                        icon="restart_alt",
                        on_click=_restore_preset,
                    ).props("outline color=grey")

            with ui.row().classes("w-full items-end gap-2 mt-3 flex-wrap"):
                new_preset_id_in = ui.input(
                    label="Novo ID do Preset (ex.: hefesto_v1_mod)",
                    placeholder="hefesto_v1_mod",
                ).classes("w-64")
                new_preset_name_in = ui.input(
                    label="Nome de Exibição (opcional)",
                    placeholder="Hefesto Modificado",
                ).classes("w-64")
                overwrite_preset_switch = ui.checkbox(
                    "Sobrescrever preset existente (destrutivo)",
                    value=False,
                ).classes("text-xs text-amber-900")

                def _save_as_preset() -> None:
                    try:
                        saved_path = state.save_working_rocket_preset(
                            new_preset_id_in.value or "",
                            preset_name=(new_preset_name_in.value or "") or None,
                            overwrite=bool(overwrite_preset_switch.value),
                        )
                        render_rocket_selector_row.refresh()
                        render_structure_summary_card.refresh()
                        ui.notify(f"Preset salvo em {saved_path.name}.", type="positive")
                    except FileExistsError as exc:
                        ui.notify(
                            f"ID já existe: {exc} Marque a caixa 'Sobrescrever preset "
                            "existente' para confirmar.",
                            type="warning",
                        )
                    except (ValueError, OSError) as exc:
                        ui.notify(f"Falha ao salvar preset: {exc}", type="negative")

                ui.button(
                    "Salvar como novo preset",
                    icon="save",
                    on_click=_save_as_preset,
                ).props("outline color=positive")

        render_structure_summary_card()
        render_components_section()
        render_aero_recovery_section()
        render_aerodynamics_section()
        render_motor_casing_section()

        with ui.card().classes("w-full p-4 shadow-sm"):
            ui.label("Seção C — Overrides do Motor & Métricas Visíveis").classes(
                "text-base font-semibold text-slate-800 mb-3"
            )
            render_motor_overrides_editor(state)

            ui.separator().classes("my-3")

            with ui.row().classes("w-full gap-4 flex-wrap"):
                render_metric_selector(
                    label="Métricas Visíveis — Motor",
                    catalog=BALLISTICS_METRIC_CATALOG,
                    selected_keys=state.selected_ballistics_metrics,
                    on_change=lambda keys: setattr(state, "selected_ballistics_metrics", keys),
                )
                render_metric_selector(
                    label="Métricas Visíveis — Voo 6-DOF",
                    catalog=FLIGHT_METRIC_CATALOG,
                    selected_keys=state.selected_flight_metrics,
                    on_change=lambda keys: setattr(state, "selected_flight_metrics", keys),
                )

            ui.separator().classes("my-3")

            def _on_dry_mass_change(value: float | int | None) -> None:
                state.dry_mass_override_kg = float(value) if value is not None else None
                state.invalidate_simulation_results(clear_ballistics=True)

            def _on_factor_change(attr_name: str, value: float | int | None) -> None:
                if value is None or float(value) <= 0.0:
                    return
                setattr(state, attr_name, float(value))
                state.invalidate_simulation_results(clear_ballistics=True)

            with ui.grid(columns=4).classes(
                "w-full gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
            ):
                mass_mode_select = ui.select(
                    options={"calculated": "Calculada", "measured": "Medida"},
                    value=state.mass_mode,
                    label="MassMode",
                ).classes("w-full")
                mass_override_input = ui.number(
                    label="Massa Seca Medida (kg)",
                    value=state.dry_mass_override_kg,
                    min=0.1,
                    step=0.1,
                    on_change=lambda e: _on_dry_mass_change(e.value),
                ).classes("w-full")
                mass_override_input.set_enabled(state.mass_mode == "measured")
                ui.number(
                    label="Fator de Arrasto",
                    value=state.drag_factor,
                    min=0.05,
                    step=0.05,
                    on_change=lambda e: _on_factor_change("drag_factor", e.value),
                ).classes("w-full")
                ui.number(
                    label="Fator de Empuxo",
                    value=state.thrust_factor,
                    min=0.05,
                    step=0.05,
                    on_change=lambda e: _on_factor_change("thrust_factor", e.value),
                ).classes("w-full")

            def _mass_mode_hint() -> str:
                if state.mass_mode == "measured":
                    return (
                        "Modo Medida (measured): o campo Massa Seca Medida é OBRIGATÓRIO "
                        "e o voo 6-DOF usará exatamente esse valor."
                    )
                return (
                    "Modo Calculada (calculated): o campo Massa Seca Medida fica "
                    "desabilitado e é IGNORADO; o voo usa a massa calculada dos componentes."
                )

            mass_mode_banner = ui.label(_mass_mode_hint()).classes(
                "w-full text-xs font-medium mt-2 p-2 rounded "
                + (
                    "bg-sky-50 border border-sky-200 text-sky-900"
                    if state.mass_mode == "measured"
                    else "bg-slate-50 border border-slate-200 text-slate-700"
                )
            )

            def _on_mass_mode_change(value: object) -> None:
                state.mass_mode = "measured" if value == "measured" else "calculated"
                mass_override_input.set_enabled(state.mass_mode == "measured")
                mass_mode_banner.set_text(_mass_mode_hint())
                state.invalidate_simulation_results(clear_ballistics=True)

            mass_mode_select.on_value_change(lambda e: _on_mass_mode_change(e.value))

            ui.label("Curvas Extraídas (OutputSelection)").classes(
                "text-sm font-semibold text-slate-700 mt-3 mb-1"
            )
            with ui.grid(columns=4).classes("w-full gap-2 grid-cols-2 sm:grid-cols-4"):
                for field_name, label_pt in _OUTPUT_FIELD_LABELS:
                    ui.checkbox(
                        label_pt,
                        value=bool(getattr(state.output_selection, field_name)),
                        on_change=lambda e, key=field_name: setattr(
                            state,
                            "output_selection",
                            state.output_selection.model_copy(update={key: bool(e.value)}),
                        ),
                    ).classes("text-xs")

    def _refresh_summary() -> None:
        render_structure_summary_card.refresh()
        render_aerodynamics_section.refresh()

    unsub = state.subscribe(_refresh_summary)
    _attach_client_cleanup(unsub)
    return root


__all__ = ["render_config_page"]
