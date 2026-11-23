"""Tests for frontend.state and frontend.components (metrics, safety, Plotly charts)."""

from __future__ import annotations

import shutil
from pathlib import Path

import plotly.graph_objects as go
import pytest
from nicegui import Client, ui
from nicegui.page import page

from frontend.components import (
    build_all_panel_figures,
    build_ballistics_metric_items,
    build_flight_metric_items,
    build_propulsion_figure,
    build_safety_rows,
    build_trajectory_3d_figure,
    render_alerts_banner,
    render_ballistics_metrics_cards,
    render_flight_metrics_cards,
    render_safety_panel,
    render_simulation_metrics_summary,
    render_telemetry_tabs,
)
from frontend.state import AppState, create_app_state
from hefesto.domain import (
    FlightResult,
    LaunchConfig,
    MotorOverride,
    OutputSelection,
    SafetyCheck,
    SafetyCriterion,
    SafetyLimits,
    SafetyReport,
)
from hefesto.services import ServiceAlert

REPO_ROOT = Path(__file__).resolve().parents[2]


def _seed_isolated_workspace(tmp_path: Path) -> Path:
    shutil.copytree(REPO_ROOT / "data" / "assets", tmp_path / "data" / "assets")
    shutil.copytree(REPO_ROOT / "data" / "catalog", tmp_path / "data" / "catalog")
    return tmp_path


def test_app_state_lifecycle_errors_and_manual_snapshots(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    events: list[str] = []
    state = create_app_state(repo_root=str(root), initialize=True)
    unsubscribe = state.subscribe(lambda: events.append(state.status_message))

    assert state.catalog is not None
    assert state.simulation_config is not None
    assert state.last_error is None
    assert not (root / "data" / "runs").exists()

    # Measured mass mode with dry_mass_override_kg must compose cleanly.
    state.mass_mode = "measured"
    state.dry_mass_override_kg = 21.644
    measured_cfg = state.compose_config()
    assert measured_cfg.mass_mode == "measured"
    assert measured_cfg.mission.rocket.dry_mass_override_kg == pytest.approx(21.644)

    # Restore calculated mode and run fast deterministic flight (terminate_on_apogee=True).
    state.mass_mode = "calculated"
    state.dry_mass_override_kg = None
    state.launch_config = LaunchConfig(terminate_on_apogee=True)
    result = state.run_simulation()
    assert result is not None
    assert state.current_result == result
    assert state.ballistics_preview is not None
    assert state.safety_preview is not None
    assert state.safety_preview.all_passed is True
    assert not state.is_running
    assert state.last_error is None
    assert not (root / "data" / "runs").exists()
    assert len(events) >= 2

    # Blocking GeometryValidationError must be captured cleanly without crashing UI.
    state.motor_overrides = (MotorOverride(path="grains.*.properties.length", value=0.25),)
    assert state.run_simulation() is None
    assert state.last_error_stage == "geometry"
    assert state.last_error is not None
    assert "exceeds available casing" in state.last_error
    assert not state.is_running

    # OpenMotor SimulationServiceError must expose stage="ballistics" and ServiceAlerts.
    state.motor_overrides = (MotorOverride(path="nozzle.throat", value=0.0),)
    assert state.run_simulation() is None
    assert state.last_error_stage == "ballistics"
    assert len(state.last_alerts) >= 1

    # Standalone motor check recovers cleanly once overrides are cleared.
    state.motor_overrides = ()
    check_output = state.run_motor_check()
    assert check_output is not None
    ballistics, safety = check_output
    assert ballistics.max_thrust_n > 3000.0
    assert safety.all_passed is True

    # A failed run invalidated the previous flight; recover one before snapshot CRUD.
    result = state.run_simulation()
    assert result is not None

    # On-demand snapshot CRUD.
    summary = state.save_current_run()
    assert summary is not None
    assert (root / "data" / "runs" / f"{summary.run_id}.json").is_file()
    assert len(state.run_summaries) == 1
    loaded = state.load_saved_run(summary.run_id)
    assert loaded == result
    assert state.delete_saved_run(summary.run_id) is True
    assert state.run_summaries == ()

    count_before = len(events)
    unsubscribe()
    state.notify()
    assert len(events) == count_before


def test_metrics_cards_and_safety_panel_builders(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    state = AppState(
        repo_root=str(root),
        launch_config=LaunchConfig(terminate_on_apogee=True),
    )
    state.initialize()
    result = state.run_simulation()
    assert result is not None
    assert result.ballistics is not None
    assert result.safety is not None

    flight_items = build_flight_metric_items(result.flight, safety=result.safety)
    assert len(flight_items) == 8
    by_key = {item.key: item for item in flight_items}
    assert by_key["apogee_agl"].unit == "m"
    assert by_key["impact_distance"].value == "N/D"
    assert by_key["static_margin"].tone == "positive"

    low_margin_flight = result.flight.model_copy(update={"min_static_margin_calibers": 0.8})
    low_items = {item.key: item for item in build_flight_metric_items(low_margin_flight)}
    assert low_items["static_margin"].tone == "negative"

    ballistics_items = build_ballistics_metric_items(result.ballistics)
    assert len(ballistics_items) == 6
    assert {item.key for item in ballistics_items} == {
        "max_thrust",
        "motor_impulse",
        "peak_pressure",
        "peak_kn",
        "propellant_mass",
        "port_throat",
    }

    rows = build_safety_rows(result.safety)
    assert len(rows) == 5
    assert [row.criterion for row in rows] == [
        SafetyCriterion.CASE_SAFETY_FACTOR,
        SafetyCriterion.PEAK_CHAMBER_PRESSURE,
        SafetyCriterion.PEAK_KN,
        SafetyCriterion.PEAK_MASS_FLUX,
        SafetyCriterion.PORT_TO_THROAT_RATIO,
    ]
    assert rows[0].passed is True
    assert rows[0].below_target is True  # ~2.79 < target 3.00

    # Fail-closed check with value=None must show passed=False and N/D (fail-closed).
    fail_closed_report = SafetyReport(
        limits=SafetyLimits(),
        checks=(
            SafetyCheck(
                criterion=SafetyCriterion.CASE_SAFETY_FACTOR,
                name="Case safety factor",
                value=None,
                min_limit=2.0,
                passed=False,
            ),
            SafetyCheck(
                criterion=SafetyCriterion.PEAK_CHAMBER_PRESSURE,
                name="Peak chamber pressure",
                value=None,
                max_limit=8_000_000.0,
                unit="Pa",
                passed=False,
            ),
            SafetyCheck(
                criterion=SafetyCriterion.PEAK_KN,
                name="Peak Kn",
                value=None,
                max_limit=250.0,
                passed=False,
            ),
            SafetyCheck(
                criterion=SafetyCriterion.PEAK_MASS_FLUX,
                name="Peak mass flux",
                value=None,
                max_limit=1406.0,
                unit="kg/(m^2*s)",
                passed=False,
            ),
            SafetyCheck(
                criterion=SafetyCriterion.PORT_TO_THROAT_RATIO,
                name="Aft port-to-throat ratio",
                value=2.5,
                min_limit=2.0,
                passed=True,
            ),
        ),
    )
    fc_rows = build_safety_rows(fail_closed_report)
    assert fc_rows[0].passed is False
    assert fc_rows[0].formatted_value == "N/D (fail-closed)"
    assert fc_rows[4].passed is True


def test_plotly_figures_cover_all_five_panels_and_edge_cases(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)

    # 1) Empty / None inputs must return valid empty-state go.Figure objects.
    empty_figs = build_all_panel_figures(None)
    assert set(empty_figs) == {
        "trajectory_3d",
        "kinematics",
        "stability",
        "aerodynamics",
        "propulsion",
    }
    for fig in empty_figs.values():
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 0
        assert len(fig.layout.annotations) >= 1

    # 2) Full SimulationResult populates all 5 panels with expected traces.
    state = AppState(
        repo_root=str(root),
        launch_config=LaunchConfig(terminate_on_apogee=True),
        output_selection=OutputSelection.all(),
    )
    state.initialize()
    result = state.run_simulation()
    assert result is not None
    assert result.ballistics is not None

    figs = build_all_panel_figures(result)
    assert any(isinstance(trace, go.Scatter3d) for trace in figs["trajectory_3d"].data)
    assert {trace.name for trace in figs["kinematics"].data} == {
        "Velocidade Total (m/s)",
        "Velocidade Vertical Vz (m/s)",
        "Mach (-)",
        "Aceleração (m/s²)",
    }
    assert {trace.name for trace in figs["stability"].data} == {
        "Centro de Gravidade CG (m)",
        "Centro de Pressão CP (m)",
        "Margem Estática (cal)",
    }
    assert {trace.name for trace in figs["aerodynamics"].data} == {
        "Arrasto Aerodinâmico (N)",
        "Cd Power-Off",
        "Cd Power-On",
    }
    assert {trace.name for trace in figs["propulsion"].data} == {
        "Empuxo Líquido no Voo — RocketPy (N)",
        "Empuxo Balístico — OpenMotor (N)",
        "Pressão de Câmara (MPa)",
        "Kn (-)",
    }

    # 3) OutputSelection.none() produces clean empty-state figures without crashing.
    no_curves_flight = FlightResult(
        apogee_agl_m=3500.0,
        apogee_msl_m=4900.0,
        apogee_time_s=26.0,
        flight_time_s=26.0,
        max_speed_ms=300.0,
        max_mach=0.9,
        rail_exit_velocity_ms=27.0,
        min_static_margin_calibers=2.3,
        total_impulse_ns=11500.0,
        dry_mass_kg=18.85,
    )
    no_curves_result = result.model_copy(update={"flight": no_curves_flight, "ballistics": None})
    no_curve_figs = build_all_panel_figures(no_curves_result)
    for fig in no_curve_figs.values():
        assert len(fig.data) == 0

    # 4) Propulsion handles flight-only (.eng) and ballistics-only previews.
    eng_only_prop = build_propulsion_figure(result.flight, None)
    assert [t.name for t in eng_only_prop.data] == ["Empuxo Líquido no Voo — RocketPy (N)"]
    assert len(eng_only_prop.layout.annotations) >= 2

    ballistics_only_prop = build_propulsion_figure(None, result.ballistics)
    assert {t.name for t in ballistics_only_prop.data} == {
        "Empuxo Balístico — OpenMotor (N)",
        "Pressão de Câmara (MPa)",
        "Kn (-)",
    }

    # 5) Trajectory 3D interpolates mismatched series timestamps cleanly.
    mismatched_flight = no_curves_flight.model_copy(
        update={
            "x_series": ((0.0, 0.0), (2.0, 10.0), (4.0, 20.0)),
            "y_series": ((0.0, 0.0), (4.0, -8.0)),
            "altitude_agl_series": ((0.0, 0.0), (1.0, 50.0), (2.0, 120.0), (4.0, 200.0)),
        }
    )
    mismatched_fig = build_trajectory_3d_figure(mismatched_flight)
    scatter_3d_traces = [t for t in mismatched_fig.data if isinstance(t, go.Scatter3d)]
    assert len(scatter_3d_traces) == 5
    assert list(scatter_3d_traces[1].x) == pytest.approx([0.0, 5.0, 10.0, 20.0])
    assert list(scatter_3d_traces[1].y) == pytest.approx([0.0, -2.0, -4.0, -8.0])


def test_nicegui_components_render_headless_without_disk_side_effects(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    state = AppState(
        repo_root=str(root),
        launch_config=LaunchConfig(terminate_on_apogee=True),
    )
    state.initialize()
    result = state.run_simulation()
    assert result is not None

    test_page = page("/test-components")
    with Client(test_page) as client:
        render_alerts_banner(
            "Sobreposição de grãos",
            error_stage="geometry",
            alerts=(
                ServiceAlert(
                    level="warning",
                    category="geometry",
                    description="Folga reduzida",
                    location="grains",
                ),
            ),
        )
        render_flight_metrics_cards(None)
        render_ballistics_metrics_cards(None)
        render_simulation_metrics_summary(result)
        render_safety_panel(result.safety)
        render_telemetry_tabs(result)

        plotly_elements = [
            el for el in client.elements.values() if isinstance(el, ui.plotly)
        ]
        assert len(plotly_elements) == 5
        for plt_el in plotly_elements:
            payload = plt_el._get_figure_json()
            assert "data" in payload
            assert "layout" in payload
    client.delete()

    assert not (REPO_ROOT / ".nicegui").exists()
    assert not (REPO_ROOT / "data" / "runs").exists()


def test_page_helpers_override_parsing_error_classification_and_asset_upload(
    tmp_path: Path,
) -> None:
    from frontend.pages import (
        build_simulation_error_state,
        parse_override_value,
        store_asset_bytes,
    )
    from hefesto.domain import AssetCategory, GeometryValidationError
    from hefesto.services import SimulationServiceError

    root = _seed_isolated_workspace(tmp_path)

    assert parse_override_value("4") == 4
    assert isinstance(parse_override_value("4"), int)
    assert parse_override_value("0.036") == pytest.approx(0.036)
    assert isinstance(parse_override_value("0.036"), float)
    assert parse_override_value(" Both ") == "Both"
    for invalid in ("", "   ", "nan", "inf", "-inf"):
        with pytest.raises(ValueError):
            parse_override_value(invalid)

    geom_stage, geom_msg, geom_alerts = build_simulation_error_state(
        GeometryValidationError("grain stack exceeds available casing")
    )
    assert geom_stage == "geometry"
    assert "exceeds available casing" in geom_msg
    assert geom_alerts == ()

    svc_alert = ServiceAlert(level="error", category="nozzle", description="bad throat")
    svc_stage, svc_msg, svc_alerts = build_simulation_error_state(
        SimulationServiceError("ballistics failed", alerts=(svc_alert,), stage="ballistics")
    )
    assert svc_stage == "ballistics"
    assert svc_msg == "ballistics failed"
    assert svc_alerts == (svc_alert,)

    nc_stage, nc_msg, _ = build_simulation_error_state(
        FileNotFoundError("Asset not found under 'atmosphere': missing_era5.nc")
    )
    assert nc_stage == "flight"
    assert ".nc" in nc_msg
    assert "sem fallback ISA" in nc_msg

    drag_stage, drag_msg, _ = build_simulation_error_state(
        FileNotFoundError("Asset not found under 'drag': missing.csv")
    )
    assert drag_stage == "validation"
    assert "missing.csv" in drag_msg

    saved_csv = store_asset_bytes(
        AssetCategory.DRAG,
        "custom_drag.csv",
        b"mach,cd\n0.0,0.4\n1.0,0.5\n",
        repo_root=str(root),
    )
    assert saved_csv == (root / "data" / "assets" / "drag" / "custom_drag.csv").resolve()
    assert saved_csv.is_file()

    saved_nc = store_asset_bytes(
        AssetCategory.ATMOSPHERE,
        "custom_atm.nc",
        b"CDF\x01mock",
        repo_root=str(root),
    )
    assert saved_nc.is_file()

    with pytest.raises(ValueError, match="vazio"):
        store_asset_bytes(AssetCategory.DRAG, "empty.csv", b"", repo_root=str(root))
    with pytest.raises(ValueError):
        store_asset_bytes(AssetCategory.DRAG, "../escape.csv", b"mach,cd\n", repo_root=str(root))
    with pytest.raises(ValueError, match="Disallowed file extension"):
        store_asset_bytes(
            AssetCategory.ATMOSPHERE,
            "not_netcdf.csv",
            b"mach,cd\n",
            repo_root=str(root),
        )


def test_all_three_pages_render_headless_and_support_snapshot_crud(tmp_path: Path) -> None:
    from frontend.pages import (
        render_assets_page,
        render_history_page,
        render_simulation_page,
    )

    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)
    state.launch_config = LaunchConfig(terminate_on_apogee=True)

    sim_page = page("/smoke-sim")
    with Client(sim_page) as sim_client:
        render_simulation_page(state)
        selects = [el for el in sim_client.elements.values() if isinstance(el, ui.select)]
        numbers = [el for el in sim_client.elements.values() if isinstance(el, ui.number)]
        checkboxes = [el for el in sim_client.elements.values() if isinstance(el, ui.checkbox)]
        plotly_els = [el for el in sim_client.elements.values() if isinstance(el, ui.plotly)]
        assert len(selects) >= 8
        assert len(numbers) >= 7
        assert len(checkboxes) == 12
        assert len(plotly_els) == 5
    sim_client.delete()

    assets_page = page("/smoke-assets")
    with Client(assets_page) as assets_client:
        render_assets_page(state)
        uploads = [el for el in assets_client.elements.values() if isinstance(el, ui.upload)]
        tables = [el for el in assets_client.elements.values() if isinstance(el, ui.table)]
        assert len(uploads) == 1
        assert len(tables) == 1
        assert len(tables[0].rows) == 15
    assets_client.delete()

    assert not (root / "data" / "runs").exists()
    result = state.run_simulation()
    assert result is not None
    summary = state.save_current_run()
    assert summary is not None

    history_page = page("/smoke-history")
    with Client(history_page) as history_client:
        render_history_page(state)
        labels = [
            getattr(el, "text", "")
            for el in history_client.elements.values()
            if isinstance(el, ui.label)
        ]
        assert any(summary.run_id in text for text in labels)
    history_client.delete()

    assert not (REPO_ROOT / ".nicegui").exists()
    assert not (REPO_ROOT / "data" / "runs").exists()


@pytest.mark.slow
@pytest.mark.anyio
async def test_app_routes_and_cpu_bound_simulation_with_user_simulation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nicegui.testing import user_simulation

    from frontend.app import register_pages
    from frontend.pages import execute_motor_check_async, execute_simulation_async
    from hefesto.services import load_site_preset, save_site_preset

    root = _seed_isolated_workspace(tmp_path)
    monkeypatch.setenv("NICEGUI_STORAGE_PATH", str(tmp_path / ".nicegui"))

    async with user_simulation() as user:
        register_pages(repo_root=str(root))
        await user.open("/")
        await user.should_see("Hefesto V1 — Simulação 6-DOF")
        await user.should_see("Configuração da Missão e Física 6-DOF")
        await user.should_see("Modo de Massa (MassMode)")
        await user.should_see("Geometria das Aletas (FinGeometryMode)")

        await user.open("/assets")
        await user.should_see("Upload de Assets Brutos (data/assets/)")
        await user.should_see("Inventário de Assets (data/assets/)")

        await user.open("/history")
        await user.should_see("Snapshots Sob Demanda (data/runs/)")

        # 1) Real cpu_bound deterministic 6-DOF simulation.
        state = create_app_state(repo_root=str(root), initialize=True)
        state.launch_config = LaunchConfig(terminate_on_apogee=True)
        result = await execute_simulation_async(state)
        assert result is not None
        assert result.flight.apogee_agl_m > 3500.0
        assert state.safety_preview is not None
        assert state.safety_preview.all_passed is True
        assert state.last_error is None
        assert not state.is_running

        # 2) Blocking GeometryValidationError via cpu_bound.
        state.motor_overrides = (MotorOverride(path="grains.*.properties.length", value=0.25),)
        assert await execute_simulation_async(state) is None
        assert state.last_error_stage == "geometry"
        assert state.last_error is not None
        assert "exceeds available casing" in state.last_error

        # 3) Blocking missing .nc atmosphere error (no ISA fallback).
        state.motor_overrides = ()
        base_site = load_site_preset("irec_oper", repo_root=root)
        missing_site = base_site.model_copy(update={"atmosphere_asset": "missing_era5.nc"})
        save_site_preset(missing_site, preset_id="missing_nc_site", repo_root=root)
        state.refresh_catalog()
        state.selected_site_id = "missing_nc_site"
        assert await execute_simulation_async(state) is None
        assert state.last_error_stage == "flight"
        assert state.last_error is not None
        assert ".nc" in state.last_error

        # 4) Non-blocking SafetyReport fail-closed with .eng-only motor.
        state.selected_site_id = "irec_oper"
        state.selected_motor_id = "medusa_n3174"
        eng_result = await execute_simulation_async(state)
        assert eng_result is not None
        assert state.safety_preview is not None
        assert not state.safety_preview.all_passed
        assert state.last_error is None

        # 5) Standalone motor ballistics check via cpu_bound.
        state.selected_motor_id = "medusa_knsb_a"
        check_res = await execute_motor_check_async(state)
        assert check_res is not None
        assert check_res[0].max_thrust_n > 3000.0

    assert not (REPO_ROOT / ".nicegui").exists()
    assert not (REPO_ROOT / "data" / "runs").exists()


def test_configurable_metric_catalogs_working_rocket_state_and_config_page_render(
    tmp_path: Path,
) -> None:
    from frontend.components import (
        BALLISTICS_METRIC_CATALOG,
        DEFAULT_BALLISTICS_METRIC_KEYS,
        DEFAULT_FLIGHT_METRIC_KEYS,
        FLIGHT_METRIC_CATALOG,
    )
    from frontend.pages import render_config_page
    from hefesto.domain import PointMassComponent
    from hefesto.services import DEFAULT_ROCKET_ID, recalculate_rocket_structure

    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)
    state.launch_config = LaunchConfig(terminate_on_apogee=True)

    # 1) Metric catalog defaults & custom selection.
    assert len(DEFAULT_FLIGHT_METRIC_KEYS) == 8
    assert len(FLIGHT_METRIC_CATALOG) >= 12
    assert len(DEFAULT_BALLISTICS_METRIC_KEYS) == 6
    assert len(BALLISTICS_METRIC_CATALOG) >= 14

    result = state.run_simulation()
    assert result is not None and result.ballistics is not None
    rocket_motor = state.simulation_config.mission.rocket.motor  # type: ignore[union-attr]

    extra_flight = build_flight_metric_items(
        result.flight,
        safety=result.safety,
        selected_keys=("apogee_agl", "apogee_msl", "max_mach", "landing_velocity"),
    )
    assert [item.key for item in extra_flight] == [
        "apogee_agl",
        "apogee_msl",
        "max_mach",
        "landing_velocity",
    ]

    extra_ballistics = build_ballistics_metric_items(
        result.ballistics,
        motor=rocket_motor,
        selected_keys=(
            "max_thrust",
            "total_loaded_mass",
            "motor_dry_mass",
            "propellant_mass_fraction",
            "casing_length",
            "outer_diameter",
            "expansion_ratio",
            "average_thrust",
        ),
    )
    assert len(extra_ballistics) == 8
    by_bkey = {item.key: item for item in extra_ballistics}
    assert by_bkey["total_loaded_mass"].unit == "kg"
    assert by_bkey["motor_dry_mass"].unit == "kg"
    assert by_bkey["propellant_mass_fraction"].unit == "%"
    assert by_bkey["casing_length"].unit == "m"
    assert by_bkey["outer_diameter"].unit == "mm"
    assert float(by_bkey["expansion_ratio"].value) > 1.0

    # 2) Guided motor override options via AppState.
    override_opts = state.available_motor_override_options()
    assert any(opt.path == "nozzle.throat" for opt in override_opts)

    # 3) working_rocket_spec lifecycle, protection of hefesto_v1, and preset save/reset.
    working = state.ensure_working_rocket()
    assert not state.has_unsaved_rocket_changes
    edited = recalculate_rocket_structure(
        working.model_copy(
            update={
                "components": (
                    *working.components,
                    PointMassComponent(name="Session Payload", mass_kg=0.5, position_m=1.1),
                )
            }
        )
    )
    state.update_working_rocket(edited)
    assert bool(state.has_unsaved_rocket_changes)
    composed = state.compose_config()
    assert any(c.name == "Session Payload" for c in composed.mission.rocket.components)

    with pytest.raises(ValueError, match=DEFAULT_ROCKET_ID):
        state.save_working_rocket_preset(DEFAULT_ROCKET_ID)

    saved_path = state.save_working_rocket_preset("hefesto_v1_test", preset_name="Hefesto Test")
    assert saved_path.is_file()
    assert not state.has_unsaved_rocket_changes
    assert state.selected_rocket_id == "hefesto_v1_test"

    state.selected_rocket_id = DEFAULT_ROCKET_ID
    reloaded = state.reset_working_rocket()
    assert all(c.name != "Session Payload" for c in reloaded.components)
    assert not state.has_unsaved_rocket_changes

    # 4) Headless render of Configuration page.
    cfg_page = page("/smoke-config")
    with Client(cfg_page) as cfg_client:
        render_config_page(state)
        labels = [
            getattr(el, "text", "")
            for el in cfg_client.elements.values()
            if isinstance(el, ui.label)
        ]
        assert any("Estrutura do Foguete" in text for text in labels)
        assert any("Aletas, Ogiva e Recuperação" in text for text in labels)
        assert any("Overrides do Motor" in text for text in labels)
    cfg_client.delete()

    assert not (REPO_ROOT / ".nicegui").exists()
    assert not (REPO_ROOT / "data" / "runs").exists()


def test_execution_audit_panel_and_assets_database_subtabs_render(tmp_path: Path) -> None:
    from frontend.components import render_execution_audit_panel
    from frontend.pages import render_assets_page
    from hefesto.domain import PointMassComponent
    from hefesto.services import recalculate_rocket_structure

    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)
    state.launch_config = LaunchConfig(terminate_on_apogee=True)
    state.output_selection = OutputSelection.none()
    state.auto_save_runs = True

    # Edit rocket in session + apply MotorOverride and run with auto_save_runs=True.
    base_rocket = state.ensure_working_rocket()
    state.update_working_rocket(
        recalculate_rocket_structure(
            base_rocket.model_copy(
                update={
                    "components": (
                        *base_rocket.components,
                        PointMassComponent(name="UI Audit Mass", mass_kg=0.4, position_m=1.0),
                    )
                }
            )
        )
    )
    state.motor_overrides = (MotorOverride(path="nozzle.throat", value=0.036),)
    result = state.run_simulation()
    assert result is not None
    assert state.current_audit_report is not None
    assert len(state.current_audit_report.applied_overrides) == 1
    assert state.current_audit_report.rocket_modified_in_session is True
    assert len(state.run_summaries) == 1

    audit_page = page("/smoke-audit")
    with Client(audit_page) as audit_client:
        render_execution_audit_panel(state.current_audit_report)
        labels = [
            getattr(el, "text", "")
            for el in audit_client.elements.values()
            if isinstance(el, ui.label)
        ]
        assert any("nozzle.throat" in text for text in labels)
        assert any("UI Audit Mass" in text for text in labels)
    audit_client.delete()

    assets_db_page = page("/smoke-assets-db")
    with Client(assets_db_page) as db_client:
        render_assets_page(state)
        tabs = [el for el in db_client.elements.values() if isinstance(el, ui.tab)]
        assert len(tabs) == 4
        uploads = [el for el in db_client.elements.values() if isinstance(el, ui.upload)]
        tables = [el for el in db_client.elements.values() if isinstance(el, ui.table)]
        assert len(uploads) == 1
        assert len(tables) == 1
        assert len(tables[0].rows) == 15
    db_client.delete()

    # Quick-load helpers from catalog browser.
    state.load_motor_into_session("medusa_n3174")
    assert state.selected_motor_id == "medusa_n3174"
    assert state.motor_overrides == ()
    loaded_rkt = state.load_rocket_into_config("hefesto_v1")
    assert loaded_rkt.name == "hefesto_v1"
    assert not (REPO_ROOT / ".nicegui").exists()
    assert not (REPO_ROOT / "data" / "runs").exists()


def test_config_page_rocket_selector_and_ork_import_ui(tmp_path: Path) -> None:
    """Verify config_page renders catalog rocket selector and OpenRocket (.ork) import flow."""
    import io
    import shutil
    import zipfile

    from nicegui import Client, ui
    from nicegui.page import page

    from frontend.pages.config_page import render_config_page
    from frontend.state import create_app_state
    from hefesto.services import import_and_save_ork_rocket

    for sub in (
        "assets/motors",
        "assets/drag",
        "catalog/motors",
        "catalog/rockets",
        "catalog/sites",
        "catalog/limits",
    ):
        (tmp_path / "data" / sub).mkdir(parents=True)

    for rel in ("assets/motors/medusa_knsb_a.eng", "assets/motors/medusa_knsb_a.ric"):
        shutil.copy2(REPO_ROOT / "data" / rel, tmp_path / "data" / rel)
    for rel in ("assets/drag/power_off.csv", "assets/drag/power_on.csv"):
        shutil.copy2(REPO_ROOT / "data" / rel, tmp_path / "data" / rel)
    shutil.copy2(
        REPO_ROOT / "data" / "catalog" / "motors" / "medusa_knsb_a.json",
        tmp_path / "data" / "catalog" / "motors" / "medusa_knsb_a.json",
    )
    shutil.copy2(
        REPO_ROOT / "data" / "catalog" / "rockets" / "hefesto_v1.json",
        tmp_path / "data" / "catalog" / "rockets" / "hefesto_v1.json",
    )
    shutil.copy2(
        REPO_ROOT / "data" / "catalog" / "sites" / "irec_oper.json",
        tmp_path / "data" / "catalog" / "sites" / "irec_oper.json",
    )
    shutil.copy2(
        REPO_ROOT / "data" / "catalog" / "limits" / "default.json",
        tmp_path / "data" / "catalog" / "limits" / "default.json",
    )

    xml_text = """<?xml version='1.0' encoding='utf-8'?>
<openrocket version="1.9">
  <rocket>
    <name>UI Ork Rocket</name>
    <subcomponents>
      <stage>
        <name>Sustainer</name>
        <subcomponents>
          <nosecone>
            <name>Ogiva</name>
            <shape>ogive</shape>
            <length>0.35</length>
            <aftradius>0.06</aftradius>
          </nosecone>
          <bodytube>
            <name>Corpo</name>
            <length>0.90</length>
            <thickness>0.002</thickness>
            <radius>0.06</radius>
            <subcomponents>
              <trapezoidfinset>
                <name>Aletas</name>
                <fincount>3</fincount>
                <rootchord>0.20</rootchord>
                <tipchord>0.10</tipchord>
                <height>0.10</height>
                <sweeplength>0.05</sweeplength>
              </trapezoidfinset>
            </subcomponents>
          </bodytube>
        </subcomponents>
      </stage>
    </subcomponents>
  </rocket>
</openrocket>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("rocket.ork", xml_text.encode("utf-8"))

    import_and_save_ork_rocket(
        buf.getvalue(),
        rocket_id="ui_ork_v1",
        base_motor_id="medusa_knsb_a",
        power_off_drag_asset="power_off.csv",
        power_on_drag_asset="power_on.csv",
        repo_root=tmp_path,
    )

    state = create_app_state(repo_root=str(tmp_path), initialize=True)
    cfg_page = page("/smoke-config-ork")
    with Client(cfg_page) as client:
        render_config_page(state)
        selects = [el for el in client.elements.values() if isinstance(el, ui.select)]
        buttons = [el for el in client.elements.values() if isinstance(el, ui.button)]
        rocket_sel = [
            sel for sel in selects if sel.props.get("label") == "Foguete do Catálogo"
        ]
        assert len(rocket_sel) == 1
        assert "hefesto_v1" in rocket_sel[0].options
        assert "ui_ork_v1" in rocket_sel[0].options
        assert any(
            getattr(btn, "text", "") == "Importar .ork (OpenRocket)" for btn in buttons
        )
        assert any(getattr(btn, "text", "") == "Analisar .ork" for btn in buttons)
        assert any(
            getattr(btn, "text", "") == "Exportar para o Banco e Selecionar"
            for btn in buttons
        )
        checkboxes = [
            getattr(el, "text", "")
            for el in client.elements.values()
            if isinstance(el, ui.checkbox)
        ]
        assert any("Sobrescrever preset existente" in text for text in checkboxes)
        assert any("Sobrescrever preset/.ork existente" in text for text in checkboxes)
    client.delete()

    switched = state.load_rocket_into_config("ui_ork_v1")
    assert switched.name == "UI Ork Rocket"
    assert state.selected_rocket_id == "ui_ork_v1"


def test_config_page_motor_casing_update_and_restore(tmp_path: Path) -> None:
    """Verify AppState and config_page motor casing length update and preset restore."""
    import shutil

    from nicegui import Client, ui
    from nicegui.page import page

    from frontend.pages.config_page import render_config_page
    from frontend.state import create_app_state

    for sub in (
        "assets/motors",
        "assets/drag",
        "catalog/motors",
        "catalog/rockets",
        "catalog/sites",
        "catalog/limits",
    ):
        (tmp_path / "data" / sub).mkdir(parents=True)

    for rel in ("assets/motors/medusa_knsb_a.eng", "assets/motors/medusa_knsb_a.ric"):
        shutil.copy2(REPO_ROOT / "data" / rel, tmp_path / "data" / rel)
    for rel in ("assets/drag/power_off.csv", "assets/drag/power_on.csv"):
        shutil.copy2(REPO_ROOT / "data" / rel, tmp_path / "data" / rel)
    shutil.copy2(
        REPO_ROOT / "data" / "catalog" / "motors" / "medusa_knsb_a.json",
        tmp_path / "data" / "catalog" / "motors" / "medusa_knsb_a.json",
    )
    shutil.copy2(
        REPO_ROOT / "data" / "catalog" / "rockets" / "hefesto_v1.json",
        tmp_path / "data" / "catalog" / "rockets" / "hefesto_v1.json",
    )
    shutil.copy2(
        REPO_ROOT / "data" / "catalog" / "sites" / "irec_oper.json",
        tmp_path / "data" / "catalog" / "sites" / "irec_oper.json",
    )
    shutil.copy2(
        REPO_ROOT / "data" / "catalog" / "limits" / "default.json",
        tmp_path / "data" / "catalog" / "limits" / "default.json",
    )

    state = create_app_state(repo_root=str(tmp_path), initialize=True)
    orig_casing = state.ensure_working_rocket().motor.casing

    resize_res = state.apply_motor_casing_update(
        new_length_m=orig_casing.length_m + 0.15,
        mode="tubular_delta",
        material_density_kg_m3=2700.0,
    )
    updated_rocket = state.ensure_working_rocket()
    assert updated_rocket.motor.casing.length_m == pytest.approx(orig_casing.length_m + 0.15)
    assert updated_rocket.motor.casing.dry_mass_kg > orig_casing.dry_mass_kg
    assert resize_res.delta_mass_kg > 0.0
    assert state.has_unsaved_rocket_changes is True

    hardware_before_kg = state.fixed_hardware_mass_kg()
    edits_res = state.apply_motor_casing_update(
        new_length_m=orig_casing.length_m + 0.15,
        wall_thickness_m=0.002,
        fixed_hardware_mass_kg=hardware_before_kg + 2.0,
        material_density_kg_m3=2700.0,
    )
    edited_casing = state.ensure_working_rocket().motor.casing
    assert edited_casing.wall_thickness_m == pytest.approx(0.002)
    assert edits_res.estimated_fixed_hardware_mass_kg == pytest.approx(hardware_before_kg + 2.0)
    assert edited_casing.dry_mass_kg == pytest.approx(
        edits_res.estimated_tube_mass_kg + hardware_before_kg + 2.0
    )
    assert edited_casing.dry_mass_kg > updated_rocket.motor.casing.dry_mass_kg

    cfg_page = page("/smoke-config-casing")
    with Client(cfg_page) as client:
        render_config_page(state)
        labels = [
            getattr(el, "text", "")
            for el in client.elements.values()
            if isinstance(el, ui.label)
        ]
        assert any("Carcaça e Massa do Motor" in txt for txt in labels)
        numbers_by_label = {
            str(el.props.get("label")): el
            for el in client.elements.values()
            if isinstance(el, ui.number)
        }
        assert numbers_by_label["Espessura da parede (mm)"].value == pytest.approx(2.0)
        assert numbers_by_label["Hardware fixo / fechamentos (kg)"].value == pytest.approx(
            hardware_before_kg + 2.0
        )
        assert numbers_by_label["FS Alvo"].value == pytest.approx(3.0)
        buttons = [
            el
            for el in client.elements.values()
            if isinstance(el, ui.button) and el.text == "Dimensionar parede mínima"
        ]
        assert len(buttons) == 1
    client.delete()

    restored = state.restore_motor_casing_from_preset()
    assert restored.motor.casing.length_m == pytest.approx(orig_casing.length_m)
    assert restored.motor.casing.dry_mass_kg == pytest.approx(orig_casing.dry_mass_kg)
    assert restored.motor.casing.wall_thickness_m == pytest.approx(orig_casing.wall_thickness_m)
    assert state.fixed_hardware_mass_kg() == pytest.approx(hardware_before_kg)


def test_state_auto_size_casing_wall_and_motor_check(tmp_path: Path) -> None:
    """Auto-sizing shrinks the wall to the FS target and the motor check reports it."""
    from frontend.pages.config_page import render_config_page
    from hefesto.domain import SafetyCriterion
    from hefesto.physics import (
        compute_case_hoop_stress_pa,
        compute_minimum_casing_wall_thickness_m,
    )
    from hefesto.services import run_motor_ballistics_for_preset

    shutil.copytree(REPO_ROOT / "data" / "assets", tmp_path / "data" / "assets")
    shutil.copytree(REPO_ROOT / "data" / "catalog", tmp_path / "data" / "catalog")
    state = create_app_state(repo_root=str(tmp_path), initialize=True)
    base_rocket = state.ensure_working_rocket()
    base_casing = base_rocket.motor.casing
    ballistics = run_motor_ballistics_for_preset(base_rocket.motor.name, repo_root=tmp_path)
    expected_wall_m = compute_minimum_casing_wall_thickness_m(
        ballistics.peak_chamber_pressure_pa,
        base_casing.inner_radius_m,
        base_casing.yield_strength_pa,
        3.0,
    )

    assert state.casing_target_safety_factor == pytest.approx(3.0)
    sized_rocket = state.auto_size_motor_casing_wall()
    sized_casing = sized_rocket.motor.casing
    assert sized_casing.wall_thickness_m == pytest.approx(expected_wall_m)
    assert sized_casing.wall_thickness_m > base_casing.wall_thickness_m
    assert sized_casing.dry_mass_kg > base_casing.dry_mass_kg
    assert state.has_unsaved_rocket_changes is True

    motor_check = state.run_motor_check()
    assert motor_check is not None
    _, safety = motor_check
    fs_check = next(
        chk for chk in safety.checks if chk.criterion == SafetyCriterion.CASE_SAFETY_FACTOR
    )
    hoop_stress_pa = compute_case_hoop_stress_pa(
        ballistics.peak_chamber_pressure_pa,
        sized_casing.inner_radius_m,
        sized_casing.wall_thickness_m,
    )
    assert hoop_stress_pa is not None
    assert safety.hoop_stress_pa == pytest.approx(hoop_stress_pa)
    assert fs_check.value == pytest.approx(sized_casing.yield_strength_pa / hoop_stress_pa)
    assert fs_check.value >= 2.0

    page_obj = page("/smoke-config-autosize")
    with Client(page_obj) as client:
        render_config_page(state)
        numbers_by_label = {
            str(el.props.get("label")): el
            for el in client.elements.values()
            if isinstance(el, ui.number)
        }
        assert numbers_by_label["Espessura da parede (mm)"].value == pytest.approx(
            expected_wall_m * 1000.0
        )
        assert numbers_by_label["FS Alvo"].value == pytest.approx(3.0)
        assert numbers_by_label["Hardware fixo / fechamentos (kg)"].value == pytest.approx(
            state.fixed_hardware_mass_kg()
        )
    client.delete()


def test_state_motor_selection_binds_ric_motor_and_casing_edits_reach_check(
    tmp_path: Path,
) -> None:
    """A .ric-only motor selected in the GUI owns the casing edits and the motor check."""
    from hefesto.physics import compute_case_hoop_stress_pa
    from hefesto.services import resolve_motor_for_simulation

    shutil.copytree(REPO_ROOT / "data" / "assets", tmp_path / "data" / "assets")
    shutil.copytree(REPO_ROOT / "data" / "catalog", tmp_path / "data" / "catalog")
    state = create_app_state(repo_root=str(tmp_path), initialize=True)
    assert state.ensure_working_rocket().motor.name == "medusa_knsb_a"

    state.load_motor_into_session("m1001voltas")
    bound_casing = state.ensure_working_rocket().motor.casing
    assert state.selected_motor_id == "m1001voltas"
    assert state.ensure_working_rocket().motor.name == "m1001voltas"
    assert state.ensure_working_rocket().motor.motor_asset == "m1001voltas.ric"

    hardware_kg = state.fixed_hardware_mass_kg()
    state.apply_motor_casing_update(
        new_length_m=bound_casing.length_m,
        wall_thickness_m=0.002,
        fixed_hardware_mass_kg=hardware_kg + 2.0,
    )
    edited_casing = state.ensure_working_rocket().motor.casing
    assert edited_casing.wall_thickness_m == pytest.approx(0.002)
    assert edited_casing.dry_mass_kg > bound_casing.dry_mass_kg

    cfg = state.compose_config()
    assert cfg.mission.rocket.motor.name == "m1001voltas"
    assert cfg.mission.rocket.motor.casing.wall_thickness_m == pytest.approx(0.002)
    assert cfg.mission.rocket.motor.casing.dry_mass_kg == pytest.approx(
        edited_casing.dry_mass_kg
    )

    resolved_motor, _ = resolve_motor_for_simulation(cfg.mission.rocket.motor, repo_root=tmp_path)
    assert resolved_motor.casing.wall_thickness_m == pytest.approx(0.002)
    assert resolved_motor.casing.dry_mass_kg == pytest.approx(edited_casing.dry_mass_kg)

    motor_check = state.run_motor_check()
    assert motor_check is not None
    ballistics, safety = motor_check
    assert ballistics.motor_name == "m1001voltas"
    expected_hoop_pa = compute_case_hoop_stress_pa(
        ballistics.peak_chamber_pressure_pa,
        edited_casing.inner_radius_m,
        edited_casing.wall_thickness_m,
    )
    assert expected_hoop_pa is not None
    assert safety.hoop_stress_pa == pytest.approx(expected_hoop_pa)
    fs_check = next(
        check for check in safety.checks if check.criterion == SafetyCriterion.CASE_SAFETY_FACTOR
    )
    assert fs_check.value == pytest.approx(edited_casing.yield_strength_pa / expected_hoop_pa)


def test_state_save_preset_requires_explicit_overwrite_and_protects_golden_master(
    tmp_path: Path,
) -> None:
    from hefesto.domain import PointMassComponent
    from hefesto.services import DEFAULT_ROCKET_ID, recalculate_rocket_structure

    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)
    working = state.ensure_working_rocket()
    saved_path = state.save_working_rocket_preset("hefesto_saved_once")
    original_bytes = saved_path.read_bytes()

    edited = recalculate_rocket_structure(
        working.model_copy(
            update={
                "components": (
                    *working.components,
                    PointMassComponent(name="Overwrite Payload", mass_kg=0.4, position_m=1.2),
                )
            }
        )
    )
    state.update_working_rocket(edited)
    with pytest.raises(FileExistsError, match="hefesto_saved_once"):
        state.save_working_rocket_preset("hefesto_saved_once")
    assert saved_path.read_bytes() == original_bytes

    state.save_working_rocket_preset("hefesto_saved_once", overwrite=True)
    assert saved_path.read_bytes() != original_bytes
    assert any(
        component.name == "Overwrite Payload"
        for component in state.load_rocket_into_config("hefesto_saved_once").components
    )

    with pytest.raises(ValueError, match=DEFAULT_ROCKET_ID):
        state.save_working_rocket_preset(DEFAULT_ROCKET_ID, overwrite=True)


@pytest.mark.anyio
async def test_simulation_page_reloads_rocket_and_mission_without_stale_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nicegui.testing import user_simulation

    from frontend.app import register_pages
    from frontend.state import get_client_state

    root = _seed_isolated_workspace(tmp_path)
    monkeypatch.setenv("NICEGUI_STORAGE_PATH", str(tmp_path / ".nicegui"))
    async with user_simulation() as user:
        register_pages(repo_root=str(root))
        await user.open("/")
        client = user.client
        assert client is not None
        with client:
            state = get_client_state(repo_root=str(root))
            state.launch_config = LaunchConfig(terminate_on_apogee=True)
            result = state.run_simulation()
        assert result is not None
        await user.should_see(result.run_id)

        selects = {
            str(element.props.get("label")): element
            for element in user.find(kind=ui.select).elements
            if element.props.get("label") is not None
        }
        with client:
            selects["Foguete"].value = "hefesto_1.4"

        assert state.selected_rocket_id == "hefesto_1.4"
        assert state.working_rocket_spec is not None
        assert state.working_rocket_spec.name == "Hefesto v1.2"
        assert state.current_result is None
        assert state.safety_preview is None
        assert state.ballistics_preview is None
        await user.should_see("Nenhuma simulação de voo 6-DOF executada.")
        await user.should_not_see(result.run_id)

        with client:
            selects["Missão (Preset)"].value = "ork_parity"

        assert state.selected_mission_id == "ork_parity"
        assert state.selected_site_id == "ork_reference"
        assert state.launch_config.inclination_deg == pytest.approx(84.0)
        assert state.launch_config.rail_length_m == pytest.approx(6.48)
        await user.should_see("ISA")

        cfg = state.compose_config()
        assert cfg.mission.rocket_preset_id == "hefesto_1.4"
        assert cfg.mission.rocket.name == "Hefesto v1.2"
        assert cfg.mission.environment.name == "OpenRocket Reference (ISA)"
        assert cfg.mission.atmosphere is not None
        assert cfg.mission.atmosphere.type == "isa"


def test_config_page_mass_mode_contract_disables_and_ignores_override(
    tmp_path: Path,
) -> None:
    from frontend.pages import render_config_page

    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)
    state.mass_mode = "calculated"
    state.dry_mass_override_kg = 21.0

    calculated_cfg = state.compose_config()
    assert calculated_cfg.mass_mode == "calculated"
    assert calculated_cfg.mission.rocket.dry_mass_override_kg is None

    cfg_page = page("/smoke-config-mass-mode")
    with Client(cfg_page) as client:
        render_config_page(state)
        numbers = {
            str(el.props.get("label")): el
            for el in client.elements.values()
            if isinstance(el, ui.number)
        }
        selects = {
            str(el.props.get("label")): el
            for el in client.elements.values()
            if isinstance(el, ui.select)
        }

        def _labels() -> list[str]:
            return [
                getattr(el, "text", "")
                for el in client.elements.values()
                if isinstance(el, ui.label)
            ]

        assert not numbers["Massa Seca Medida (kg)"].enabled
        assert any("IGNORADO" in text for text in _labels())

        selects["MassMode"].value = "measured"
        assert numbers["Massa Seca Medida (kg)"].enabled
        assert any("OBRIGATÓRIO" in text for text in _labels())

        measured_cfg = state.compose_config()
        assert measured_cfg.mass_mode == "measured"
        assert measured_cfg.mission.rocket.dry_mass_override_kg == pytest.approx(21.0)

        state.dry_mass_override_kg = None
        with pytest.raises(ValueError, match="measured"):
            state.compose_config()
    client.delete()


def test_state_saves_ork_sim_preset_by_materializing_active_curves(tmp_path: Path) -> None:
    from hefesto.services import load_rocket_preset, load_rocket_spec

    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)
    base_spec = state.ensure_working_rocket()
    state.update_working_rocket(base_spec.model_copy(update={"drag_source": "ork_sim"}))

    saved_path = state.save_working_rocket_preset("ork_sim_state")
    assert saved_path.is_file()

    preset = load_rocket_preset("ork_sim_state", repo_root=root)
    assert preset.drag_source == "ork_sim"
    assert preset.drag_table is not None
    assert preset.drag_table.source == "ork_sim"

    reloaded = load_rocket_spec("ork_sim_state", repo_root=root)
    assert reloaded.drag_source == "ork_sim"
    assert reloaded.power_off_drag.asset_name is None
    assert reloaded.power_on_drag.asset_name is None
    assert reloaded.power_off_drag.points == base_spec.power_off_drag.points
    assert reloaded.power_on_drag.points == base_spec.power_on_drag.points


def test_state_invalidates_stale_results_on_motor_casing_drag_and_mission_mutations(
    tmp_path: Path,
) -> None:
    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)
    state.launch_config = LaunchConfig(terminate_on_apogee=True)

    assert state.run_simulation() is not None
    assert state.current_result is not None
    assert state.ballistics_preview is not None
    assert state.safety_preview is not None
    assert state.current_audit_report is not None

    state.load_motor_into_session("medusa_n3174")
    assert state.current_result is None
    assert state.ballistics_preview is None
    assert state.safety_preview is None
    assert state.current_audit_report is None
    assert state.simulation_config is None

    state.load_motor_into_session("m1001voltas")
    assert state.run_motor_check() is not None
    assert state.ballistics_preview is not None
    assert state.safety_preview is not None

    state.apply_motor_casing_update(
        new_length_m=state.ensure_working_rocket().motor.casing.length_m,
        wall_thickness_m=0.003,
    )
    assert state.current_result is None
    assert state.ballistics_preview is None
    assert state.safety_preview is None

    state.set_working_drag_source("analytical")
    assert state.current_result is None
    assert state.ballistics_preview is None

    rasaero_csv = (
        "Mach Number,Angle of Attack (alpha),CD Power-Off,CD Power-On\n"
        "0.30,0.00,0.4940,0.4900\n"
        "0.70,0.00,0.5580,0.5540\n"
        "1.20,0.00,0.6120,0.6060\n"
    )
    state.import_rasaero_csv(rasaero_csv, "stale.cs")
    assert state.current_result is None
    assert state.ballistics_preview is None
    assert state.safety_preview is None

    state.apply_mission_preset("ork_parity")
    assert state.current_result is None
    assert state.ballistics_preview is None
    assert state.safety_preview is None
    assert state.current_audit_report is None
