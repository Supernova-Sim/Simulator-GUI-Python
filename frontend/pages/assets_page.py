"""Database & catalog browser, raw asset upload, and run audit inspection page."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from nicegui import ui
from nicegui.events import UploadEventArguments

from frontend.components import render_execution_audit_panel
from frontend.state import AppState
from hefesto.domain import (
    AssetCategory,
    AssetEntry,
    CatalogDatabaseInspection,
    SavedMotorInspection,
    SavedRocketInspection,
)
from hefesto.services import (
    inspect_catalog_database,
    list_assets,
    load_drag_curve_asset,
    load_thrust_curve_asset,
    resolve_asset_path,
)

_CATEGORY_LABELS: dict[str, str] = {
    AssetCategory.MOTORS.value: "Motores (.eng, .ric)",
    AssetCategory.DRAG.value: "Curvas de Arrasto (.csv)",
    AssetCategory.ATMOSPHERE.value: "Atmosfera ERA5 (.nc)",
}

_FILTER_OPTIONS: dict[str, str] = {
    "all": "Todas as categorias",
    **_CATEGORY_LABELS,
}

_ASSET_COLUMNS: list[dict[str, str | bool]] = [
    {"name": "category", "label": "Categoria", "field": "category", "sortable": True},
    {
        "name": "relative_path",
        "label": "Caminho Relativo",
        "field": "relative_path",
        "sortable": True,
    },
    {"name": "name", "label": "Nome", "field": "name", "sortable": True},
    {"name": "file_format", "label": "Formato", "field": "file_format", "sortable": True},
]

_SOURCE_BADGE_MAP: dict[str, tuple[str, str]] = {
    "ric_and_eng": (".ric + .eng", "primary"),
    "ric_only": (".ric OpenMotor", "secondary"),
    "eng_only": (".eng Curva Fixa", "grey"),
}


def store_asset_bytes(
    category: AssetCategory,
    relative_path: str,
    payload: bytes,
    *,
    repo_root: str | None = None,
) -> Path:
    """Validate category/extension/path via asset_service and write bytes atomically."""
    if not payload:
        raise ValueError("Arquivo enviado está vazio.")

    target = resolve_asset_path(
        category,
        relative_path,
        must_exist=False,
        repo_root=repo_root,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, mode="wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return target


def _entries_to_rows(entries: tuple[AssetEntry, ...]) -> list[dict[str, str]]:
    return [
        {
            "category": entry.category.value,
            "relative_path": entry.relative_path,
            "name": entry.name,
            "file_format": entry.file_format,
        }
        for entry in entries
    ]


def _render_motor_inspection_card(state: AppState, motor: SavedMotorInspection) -> None:
    badge_label, badge_color = _SOURCE_BADGE_MAP.get(motor.source_kind, ("Desconhecido", "grey"))
    with ui.card().classes("w-full p-4 bg-slate-50 border border-slate-200 shadow-none"):
        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 mb-2"):
            with ui.row().classes("items-center gap-2 flex-wrap"):
                ui.label(f"{motor.name} ({motor.preset_id})").classes(
                    "text-sm font-bold text-slate-800"
                )
                ui.badge(badge_label, color=badge_color)
                if motor.preset_overrides:
                    ui.badge(f"{len(motor.preset_overrides)} override(s) padrão", color="warning")

            def _load_motor(motor_id: str = motor.preset_id) -> None:
                state.load_motor_into_session(motor_id)
                ui.notify(f"Motor '{motor_id}' carregado na sessão de simulação.", type="positive")
                ui.navigate.to("/")

            ui.button("Carregar na Simulação", icon="play_arrow", on_click=_load_motor).props(
                "outline size=sm color=primary"
            )

        with ui.grid(columns=3).classes(
            "w-full gap-2 text-xs text-slate-700 grid-cols-1 md:grid-cols-3"
        ):
            ui.label(f"Asset .ric: {motor.motor_asset or 'Nenhum'}")
            ui.label(f"Curva .eng: {motor.thrust_curve_asset or 'Nenhuma'}")
            ui.label(
                f"Propelente: {motor.propellant_name} ({motor.propellant_density_kg_m3:.1f} kg/m³)"
            )
            casing_d_mm = motor.casing_outer_diameter_m * 1000.0
            wall_mm = motor.casing.wall_thickness_m * 1000.0
            ui.label(
                f"Carcaça: L={motor.casing.length_m:.3f} m · Øext={casing_d_mm:.1f} mm · "
                f"parede={wall_mm:.1f} mm"
            )
            ui.label(
                f"Massa Seca: {motor.casing.dry_mass_kg:.3f} kg · "
                f"Escoamento={motor.casing.yield_strength_pa / 1e6:.1f} MPa"
            )
            ui.label(
                f"Tubeira: Øg={motor.nozzle.throat_radius_m * 2000.0:.2f} mm · "
                f"Øs={motor.nozzle.exit_radius_m * 2000.0:.2f} mm · "
                f"η={motor.nozzle.efficiency:.3f}"
            )

        with ui.expansion(
            f"Grãos ({len(motor.grains)}) e Overrides do Preset", icon="grain"
        ).classes("w-full mt-2 bg-white border border-slate-200 rounded"):
            with ui.column().classes("w-full p-2 gap-1"):
                for idx, grain in enumerate(motor.grains):
                    ui.label(
                        f"Grão {idx + 1}: L={grain.length_m * 1000.0:.1f} mm · "
                        f"Øext={grain.outer_radius_m * 2000.0:.1f} mm · "
                        f"Øfuro={grain.inner_radius_m * 2000.0:.1f} mm · "
                        f"inibição={grain.inhibited_ends.value}"
                    ).classes("text-xs font-mono text-slate-700")
                if motor.preset_overrides:
                    ui.separator().classes("my-1")
                    for ov in motor.preset_overrides:
                        ui.label(f"Override padrão: {ov.path} = {ov.value}").classes(
                            "text-xs font-mono text-amber-800"
                        )


def _render_rocket_inspection_card(state: AppState, rocket: SavedRocketInspection) -> None:
    with ui.card().classes("w-full p-4 bg-slate-50 border border-slate-200 shadow-none"):
        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 mb-2"):
            with ui.row().classes("items-center gap-2 flex-wrap"):
                ui.label(f"{rocket.name} ({rocket.preset_id})").classes(
                    "text-sm font-bold text-slate-800"
                )
                ui.badge(f"Motor: {rocket.motor_preset_name}", color="primary")
                if rocket.dry_mass_override_kg is not None:
                    ui.badge(
                        f"Override Massa: {rocket.dry_mass_override_kg:.3f} kg",
                        color="warning",
                    )

            def _load_rocket(rocket_id: str = rocket.preset_id) -> None:
                state.load_rocket_into_config(rocket_id)
                ui.notify(f"Foguete '{rocket_id}' carregado na Configuração.", type="positive")
                ui.navigate.to("/config")

            ui.button("Carregar na Configuração", icon="settings", on_click=_load_rocket).props(
                "outline size=sm color=primary"
            )

        with ui.grid(columns=3).classes(
            "w-full gap-2 text-xs text-slate-700 grid-cols-1 md:grid-cols-3"
        ):
            ui.label(f"Massa Seca Calc.: {rocket.calculated_dry_mass_kg:.3f} kg")
            ui.label(f"CG sem Motor: {rocket.center_of_mass_without_motor_m:.4f} m")
            ui.label(f"Raio Referência: {rocket.radius_m * 1000.0:.1f} mm")
            ui.label(
                f"Estrutura: {rocket.tube_count} módulo(s) · {rocket.point_mass_count} junção(ões)"
            )
            ui.label(f"Aletas: {rocket.fin_count} @ {rocket.fin_position_m:.3f} m")
            ui.label(
                f"Ogiva: {rocket.nose_cone_kind} (L={rocket.nose_cone_length_m:.3f} m)"
            )
            chutes_txt = (
                ", ".join(rocket.parachute_names) if rocket.parachute_names else "Nenhum"
            )
            ui.label(f"Paraquedas: {chutes_txt}")
            ui.label(
                f"Arrasto Off/On: {rocket.power_off_drag_asset} / {rocket.power_on_drag_asset}"
            )
            ui.label(f"Posição Motor: {rocket.motor_position_m:.3f} m")

        if rocket.components_summary:
            with ui.expansion(
                f"Componentes ({len(rocket.components_summary)})", icon="view_list"
            ).classes("w-full mt-2 bg-white border border-slate-200 rounded"):
                with ui.column().classes("w-full p-2 gap-0.5"):
                    for line in rocket.components_summary:
                        ui.label(f"• {line}").classes("text-xs font-mono text-slate-700")


def render_assets_page(state: AppState) -> ui.column:
    """Render database & catalog browser (motors, rockets, sites/limits/assets, runs)."""
    if state.catalog is None:
        state.initialize()

    selected_category_holder: list[str] = [AssetCategory.MOTORS.value]
    filter_holder: list[str] = ["all"]
    upload_feedback: list[str | None] = [None]
    upload_is_error: list[bool] = [False]
    preview_message: list[str] = ["Selecione um asset .csv ou .eng para inspecionar."]
    db_holder: list[CatalogDatabaseInspection] = [
        inspect_catalog_database(repo_root=state.repo_root)
    ]

    root = ui.column().classes("w-full gap-4")

    def _reload_db() -> None:
        state.refresh_catalog()
        state.refresh_runs()
        db_holder[0] = inspect_catalog_database(repo_root=state.repo_root)
        render_motors_tab.refresh()
        render_rockets_tab.refresh()
        render_sites_limits_section.refresh()
        render_assets_inventory.refresh()
        render_runs_tab.refresh()

    @ui.refreshable
    def render_upload_status() -> None:
        msg = upload_feedback[0]
        if not msg:
            return
        cls = (
            "w-full p-2.5 border-l-4 border-rose-500 bg-rose-50 text-rose-900"
            if upload_is_error[0]
            else "w-full p-2.5 border-l-4 border-emerald-500 bg-emerald-50 text-emerald-900"
        )
        with ui.card().classes(cls):
            ui.label(msg).classes("text-sm")

    @ui.refreshable
    def render_motors_tab() -> None:
        motors = db_holder[0].motors
        if not motors:
            ui.label("Nenhum preset de motor encontrado.").classes("text-sm text-slate-500")
            return
        with ui.column().classes("w-full gap-3"):
            for motor in motors:
                _render_motor_inspection_card(state, motor)

    @ui.refreshable
    def render_rockets_tab() -> None:
        rockets = db_holder[0].rockets
        if not rockets:
            ui.label("Nenhum preset de foguete encontrado.").classes("text-sm text-slate-500")
            return
        with ui.column().classes("w-full gap-3"):
            for rocket in rockets:
                _render_rocket_inspection_card(state, rocket)

    @ui.refreshable
    def render_sites_limits_section() -> None:
        db = db_holder[0]
        with ui.grid(columns=2).classes("w-full gap-4 grid-cols-1 lg:grid-cols-2"):
            with ui.card().classes("w-full p-4 shadow-sm"):
                ui.label(f"Sítios de Lançamento ({len(db.sites)})").classes(
                    "text-base font-semibold text-slate-800 mb-2"
                )
                with ui.column().classes("w-full gap-2"):
                    for site in db.sites:
                        with ui.card().classes(
                            "w-full p-2.5 bg-slate-50 border border-slate-200 shadow-none"
                        ):
                            ui.label(f"{site.spec.name} ({site.preset_id})").classes(
                                "text-xs font-bold text-slate-800"
                            )
                            ui.label(
                                f"Lat={site.spec.latitude_deg:.4f}° · "
                                f"Lon={site.spec.longitude_deg:.4f}° · "
                                f"Elev={site.spec.elevation_m:.1f} m · {site.spec.atmosphere_asset}"
                            ).classes("text-xs font-mono text-slate-600")

            with ui.card().classes("w-full p-4 shadow-sm"):
                ui.label(f"Limites de Segurança ({len(db.limits)})").classes(
                    "text-base font-semibold text-slate-800 mb-2"
                )
                with ui.column().classes("w-full gap-2"):
                    for lim in db.limits:
                        with ui.card().classes(
                            "w-full p-2.5 bg-slate-50 border border-slate-200 shadow-none"
                        ):
                            ui.label(lim.preset_id).classes("text-xs font-bold text-slate-800")
                            min_fs = lim.limits.min_case_safety_factor
                            tgt_fs = lim.limits.target_case_safety_factor
                            ui.label(
                                f"FS mín={min_fs:.2f} (alvo {tgt_fs:.2f}) · "
                                f"Pmáx={lim.limits.max_chamber_pressure_pa / 1e6:.2f} MPa · "
                                f"Kn máx={lim.limits.max_kn:.0f} · "
                                f"G máx={lim.limits.max_mass_flux_kg_m2_s:.0f} kg/(m²·s) · "
                                f"Ap/At mín={lim.limits.min_port_to_throat_ratio:.2f}"
                            ).classes("text-xs font-mono text-slate-600")

    @ui.refreshable
    def render_assets_inventory() -> None:
        selected_filter = filter_holder[0]
        cat_filter = None if selected_filter == "all" else AssetCategory(selected_filter)
        entries = list_assets(cat_filter, repo_root=state.repo_root)
        rows = _entries_to_rows(entries)
        ui.label(f"Total listado: {len(rows)} arquivo(s)").classes("text-xs text-slate-500")
        ui.table(
            columns=_ASSET_COLUMNS,
            rows=rows,
            row_key="relative_path",
            pagination=12,
        ).classes("w-full")

        inspectable = [
            e
            for e in entries
            if e.category == AssetCategory.DRAG
            or (e.category == AssetCategory.MOTORS and e.file_format == "eng")
        ]
        if inspectable:
            options = {
                f"{e.category.value}:{e.relative_path}": f"[{e.category.value}] {e.relative_path}"
                for e in inspectable
            }
            with ui.row().classes("w-full items-center gap-3 mt-2 flex-wrap"):
                inspect_select = ui.select(
                    options=options,
                    label="Inspecionar curva (.csv / .eng)",
                ).classes("w-80")

                def _inspect_selected() -> None:
                    raw_key = inspect_select.value
                    if not raw_key or ":" not in str(raw_key):
                        return
                    cat_str, rel = str(raw_key).split(":", 1)
                    try:
                        if cat_str == AssetCategory.DRAG.value:
                            spec = load_drag_curve_asset(rel, repo_root=state.repo_root)
                            machs = [pt[0] for pt in spec.points]
                            cds = [pt[1] for pt in spec.points]
                            preview_message[0] = (
                                f"Arrasto '{rel}': {len(spec.points)} pontos · "
                                f"Mach [{min(machs):.3f}, {max(machs):.3f}] · "
                                f"Cd [{min(cds):.4f}, {max(cds):.4f}]"
                            )
                        else:
                            curve = load_thrust_curve_asset(rel, repo_root=state.repo_root)
                            times = [pt[0] for pt in curve]
                            thrusts = [pt[1] for pt in curve]
                            preview_message[0] = (
                                f"Empuxo '{rel}': {len(curve)} pontos · "
                                f"t [{min(times):.2f}, {max(times):.2f}] s · "
                                f"Empuxo máx. {max(thrusts):.1f} N"
                            )
                    except (FileNotFoundError, ValueError) as exc:
                        preview_message[0] = f"Falha ao inspecionar '{rel}': {exc}"
                    render_preview_box.refresh()

                ui.button("Inspecionar", icon="analytics", on_click=_inspect_selected).props(
                    "outline color=primary"
                )

    @ui.refreshable
    def render_preview_box() -> None:
        ui.label(preview_message[0]).classes("text-xs font-mono text-slate-700")

    @ui.refreshable
    def render_runs_tab() -> None:
        runs = db_holder[0].runs
        if not runs:
            with ui.card().classes("w-full p-4 bg-slate-50 border border-slate-200 shadow-none"):
                ui.label(
                    "Nenhuma execução salva em data/runs/. Salve um snapshot na Simulação "
                    "ou ative o salvamento automático."
                ).classes("text-sm text-slate-600")
            return

        with ui.column().classes("w-full gap-2"):
            for summary in runs:
                with ui.card().classes(
                    "w-full p-3 bg-slate-50 border border-slate-200 shadow-none"
                ):
                    with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
                        with ui.column().classes("gap-0.5"):
                            ui.label(summary.run_id).classes(
                                "text-sm font-mono font-bold text-slate-800"
                            )
                            ui.label(
                                f"{summary.mission_name} · motor {summary.motor_name} · "
                                f"Apogeu {summary.apogee_agl_m:,.1f} m AGL"
                            ).classes("text-xs text-slate-600")
                        with ui.row().classes("items-center gap-2"):
                            def _inspect_run(run_id: str = summary.run_id) -> None:
                                loaded = state.load_saved_run(run_id)
                                if loaded is not None:
                                    render_run_audit_preview.refresh()
                                    ui.notify(f"Execução carregada: {run_id}", type="positive")

                            def _open_history() -> None:
                                ui.navigate.to("/history")

                            ui.button("Auditar", icon="fact_check", on_click=_inspect_run).props(
                                "outline size=sm color=primary"
                            )
                            ui.button(
                                "Ir ao Histórico",
                                icon="history",
                                on_click=_open_history,
                            ).props("flat size=sm color=primary")

    @ui.refreshable
    def render_run_audit_preview() -> None:
        if state.current_audit_report is not None:
            render_execution_audit_panel(state.current_audit_report)

    with root:
        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
            ui.label("Banco de Dados & Catálogo Local").classes(
                "text-lg font-semibold text-slate-800"
            )
            ui.button("Atualizar Banco", icon="refresh", on_click=_reload_db).props(
                "outline color=primary"
            )

        with ui.tabs().classes("w-full") as db_tabs:
            tab_motors = ui.tab("Motores Salvos", icon="local_fire_department")
            tab_rockets = ui.tab("Foguetes Salvos", icon="rocket_launch")
            tab_assets = ui.tab("Sítios, Limites & Assets", icon="folder_open")
            tab_runs = ui.tab("Execuções (data/runs/)", icon="history")

        with ui.tab_panels(db_tabs, value=tab_motors).classes("w-full bg-transparent"):
            with ui.tab_panel(tab_motors).classes("w-full p-0 pt-2"):
                render_motors_tab()

            with ui.tab_panel(tab_rockets).classes("w-full p-0 pt-2"):
                render_rockets_tab()

            with ui.tab_panel(tab_assets).classes("w-full p-0 pt-2 gap-4"):
                with ui.column().classes("w-full gap-4"):
                    render_sites_limits_section()

                    with ui.card().classes("w-full p-4 shadow-sm"):
                        ui.label("Upload de Assets Brutos (data/assets/)").classes(
                            "text-lg font-semibold text-slate-800 mb-2"
                        )
                        with ui.row().classes("w-full items-end gap-3 flex-wrap"):
                            ui.select(
                                options=_CATEGORY_LABELS,
                                value=selected_category_holder[0],
                                label="Categoria (AssetCategory)",
                                on_change=lambda e: selected_category_holder.__setitem__(
                                    0, str(e.value)
                                ),
                            ).classes("w-64")
                            subpath_input = ui.input(
                                label="Subcaminho relativo (opcional)",
                                placeholder="Padrão: nome original do arquivo",
                            ).classes("flex-1 min-w-64")

                        async def _handle_upload(event: UploadEventArguments) -> None:
                            category = AssetCategory(selected_category_holder[0])
                            custom_rel = (subpath_input.value or "").strip()
                            target_rel = custom_rel or event.file.name
                            try:
                                data = await event.file.read()
                                saved_path = store_asset_bytes(
                                    category,
                                    target_rel,
                                    data,
                                    repo_root=state.repo_root,
                                )
                                _reload_db()
                                upload_is_error[0] = False
                                upload_feedback[0] = (
                                    f"Asset salvo em '{category.value}/{target_rel}' "
                                    f"({saved_path.stat().st_size} bytes)."
                                )
                                ui.notify(f"Asset enviado: {target_rel}", type="positive")
                            except (ValueError, OSError) as exc:
                                upload_is_error[0] = True
                                upload_feedback[0] = f"Upload rejeitado: {exc}"
                                ui.notify(f"Erro no upload: {exc}", type="negative")
                            render_upload_status.refresh()

                        ui.upload(
                            on_upload=_handle_upload,
                            auto_upload=True,
                            max_files=1,
                            label="Selecionar arquivo (.eng, .ric, .csv ou .nc)",
                        ).classes("w-full mt-2")
                        render_upload_status()

                    with ui.card().classes("w-full p-4 shadow-sm"):
                        with ui.row().classes(
                            "w-full items-center justify-between flex-wrap gap-2 mb-2"
                        ):
                            ui.label("Inventário de Assets (data/assets/)").classes(
                                "text-base font-semibold text-slate-800"
                            )
                            with ui.row().classes("items-center gap-2"):
                                ui.select(
                                    options=_FILTER_OPTIONS,
                                    value=filter_holder[0],
                                    label="Filtrar Categoria",
                                    on_change=lambda e: (
                                        filter_holder.__setitem__(0, str(e.value)),
                                        render_assets_inventory.refresh(),
                                    ),
                                ).classes("w-56")
                                ui.button("Atualizar", icon="refresh", on_click=_reload_db).props(
                                    "outline color=primary"
                                )

                        render_assets_inventory()
                        render_preview_box()

            with ui.tab_panel(tab_runs).classes("w-full p-0 pt-2 gap-4"):
                with ui.column().classes("w-full gap-4"):
                    render_runs_tab()
                    render_run_audit_preview()

    return root


__all__ = [
    "render_assets_page",
    "store_asset_bytes",
]
