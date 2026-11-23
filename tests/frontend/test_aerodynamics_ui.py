"""Frontend aerodynamics UI: drag_source/finish controls, RASAero CSV import, live Cd chart."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest
from nicegui import Client, ui
from nicegui.page import page

from frontend.components import (
    DRAG_SOURCE_OPTIONS,
    SURFACE_FINISH_OPTIONS,
    build_drag_curve_figure,
    build_drag_summary_rows,
)
from frontend.pages import render_config_page
from frontend.state import create_app_state
from hefesto.domain import DragCurveTable, SurfaceFinish
from hefesto.services import (
    load_rocket_spec,
    preview_rocket_drag_curves,
    recalculate_rocket_structure,
    rocket_preset_from_spec,
    save_rocket_preset,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.slow

RASAERO_CSV = """Mach Number,Angle of Attack (alpha),CD Power-Off,CD Power-On
0.30,0.00,0.4940,0.4900
0.30,2.00,0.5130,0.5090
0.70,0.00,0.5580,0.5540
0.70,2.00,0.5770,0.5730
1.20,0.00,0.6120,0.6060
1.20,2.00,0.6330,0.6270
"""


def _seed_isolated_workspace(tmp_path: Path) -> Path:
    shutil.copytree(REPO_ROOT / "data" / "assets", tmp_path / "data" / "assets")
    shutil.copytree(REPO_ROOT / "data" / "catalog", tmp_path / "data" / "catalog")
    return tmp_path


def _aero_payloads(client: Client) -> list[dict]:
    payloads = []
    for element in client.elements.values():
        if not isinstance(element, ui.plotly):
            continue
        payload = element._get_figure_json()
        title = str(payload.get("layout", {}).get("title", {}).get("text", ""))
        if title.startswith("Curvas de Arrasto"):
            payloads.append(payload)
    return payloads


def _single_aero_payload(client: Client) -> dict:
    payloads = _aero_payloads(client)
    assert len(payloads) == 1
    return payloads[0]


def _trace(payload: dict, name: str) -> dict:
    return next(trace for trace in payload["data"] if trace["name"] == name)


def _labels(client: Client) -> list[str]:
    return [
        str(getattr(element, "text", ""))
        for element in client.elements.values()
        if isinstance(element, ui.label)
    ]


def test_drag_source_options_match_required_labels_and_summary_badges() -> None:
    assert DRAG_SOURCE_OPTIONS == {
        "analytical": "Analítico Geométrico (Barrowman/Hoerner)",
        "ork_sim": "Simulação .ork Importada",
        "rasaero_csv": "Tabela CSV RASAero II",
        "legacy_csv": "CSV Legado (Baseline v1)",
    }
    assert set(SURFACE_FINISH_OPTIONS) == {"smooth", "regular", "rough", "unfinished"}

    table = DragCurveTable(
        mach=[0.3, 0.7, 1.2],
        cd_power_off=[0.494, 0.558, 0.612],
        cd_power_on=[0.49, 0.554, 0.606],
        source="rasaero_csv",
    )
    rows = build_drag_summary_rows(table)

    assert [row.mach for row in rows] == [0.3, 0.8, 0.95]
    assert rows[0].cd_power_off == pytest.approx(0.494)
    assert rows[0].cd_power_on == pytest.approx(0.49)
    assert rows[1].cd_power_off == pytest.approx(0.558 + 0.1 * (0.612 - 0.558) / 0.5)
    assert rows[2].cd_power_on == pytest.approx(0.554 + 0.25 * (0.606 - 0.554) / 0.5)


def test_build_drag_curve_figure_window_and_traces() -> None:
    analytical = preview_rocket_drag_curves(load_rocket_spec("hefesto_1.4"))

    short = build_drag_curve_figure(analytical)
    assert {trace.name for trace in short.data} == {"CD Power-Off", "CD Power-On"}
    assert max(_trace_payload(short, "CD Power-Off")[0]) == pytest.approx(1.5)
    assert len(_trace_payload(short, "CD Power-On")[0]) == 61

    extended = build_drag_curve_figure(analytical, max_mach=3.0)
    assert max(_trace_payload(extended, "CD Power-Off")[0]) == pytest.approx(3.0)
    assert len(_trace_payload(extended, "CD Power-Off")[0]) == 121

    supersonic_only = DragCurveTable(
        mach=[2.0, 2.5, 3.0],
        cd_power_off=[0.5, 0.4, 0.35],
        cd_power_on=[0.49, 0.39, 0.34],
        source="analytical",
    )
    clipped = build_drag_curve_figure(supersonic_only)
    assert len(clipped.data) == 0
    assert len(clipped.layout.annotations) >= 1


def _trace_payload(figure, name: str) -> tuple[list[float], list[float]]:
    trace = next(item for item in figure.data if item.name == name)
    return list(trace.x), list(trace.y)


def test_state_switches_drag_source_imports_csv_and_recomputes_finish(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)

    legacy = state.ensure_working_rocket()
    assert legacy.drag_source == "legacy_csv"

    analytical = state.set_working_drag_source("analytical")
    assert analytical.drag_source == "analytical"
    assert analytical.power_off_drag.asset_name is None
    assert analytical.power_on_drag.asset_name is None
    smooth_cd = preview_rocket_drag_curves(analytical).cd_power_off[32]

    rough = state.set_working_surface_finish(SurfaceFinish.UNFINISHED)
    assert rough.drag_source == "analytical"
    assert rough.surface_finish == SurfaceFinish.UNFINISHED
    assert preview_rocket_drag_curves(rough).cd_power_off[32] > smooth_cd

    with pytest.raises(ValueError, match="<flightdata>"):
        state.set_working_drag_source("ork_sim")
    with pytest.raises(ValueError, match="Importe um CSV"):
        state.set_working_drag_source("rasaero_csv")
    assert state.ensure_working_rocket().drag_source == "analytical"

    imported = state.import_rasaero_csv(RASAERO_CSV, "l.cs")
    assert imported.drag_source == "rasaero_csv"
    assert imported.power_off_drag.points == ((0.3, 0.494), (0.7, 0.558), (1.2, 0.612))
    assert state.rasaero_csv_filename == "l.cs"
    assert state.rasaero_alpha_options == (0.0, 2.0)
    assert state.rasaero_mach_range == pytest.approx((0.3, 1.2))

    at_alpha = state.set_rasaero_alpha(2.0)
    assert state.rasaero_alpha_deg == 2.0
    assert at_alpha.power_off_drag.points == ((0.3, 0.513), (0.7, 0.577), (1.2, 0.633))

    restored_legacy = state.set_working_drag_source("legacy_csv")
    assert restored_legacy.drag_source == "legacy_csv"
    assert restored_legacy.power_off_drag.asset_name == "power_off.csv"
    assert restored_legacy.power_on_drag.asset_name == "power_on.csv"

    # The session CSV survives a round-trip through the legacy assets.
    reimported = state.set_working_drag_source("rasaero_csv")
    assert reimported.power_off_drag.points == at_alpha.power_off_drag.points
    assert state.rasaero_alpha_deg == 2.0

    # Session-only RASAero curves cannot be persisted as a catalog preset.
    with pytest.raises(ValueError, match="RASAero II vivem apenas na sessão"):
        state.save_working_rocket_preset("hefesto_rasaero_session")

    with pytest.raises(ValueError, match="no RASAero header row"):
        state.import_rasaero_csv("not a rasaero export", "bad.csv")

    state.reset_working_rocket()
    assert state.rasaero_csv_content is None
    assert state.rasaero_alpha_options == ()


def test_state_enables_ork_sim_when_the_preset_carries_flightdata_curves(
    tmp_path: Path,
) -> None:
    root = _seed_isolated_workspace(tmp_path)
    table = DragCurveTable(
        mach=[0.0, 0.5, 1.0],
        cd_power_off=[0.4, 0.5, 0.9],
        cd_power_on=[0.38, 0.48, 0.88],
        source="ork_sim",
    )
    power_off_drag, power_on_drag = table.to_specs()
    base = load_rocket_spec("hefesto_v1", repo_root=root)
    ork_rocket = base.model_copy(
        update={
            "drag_source": "ork_sim",
            "power_off_drag": power_off_drag,
            "power_on_drag": power_on_drag,
        }
    )
    save_rocket_preset(
        rocket_preset_from_spec(ork_rocket, drag_table=table),
        preset_id="hefesto_ork",
        repo_root=root,
    )
    save_rocket_preset(
        rocket_preset_from_spec(base.model_copy(update={"name": "Hefesto Legado"})),
        preset_id="hefesto_legado",
        repo_root=root,
    )

    state = create_app_state(repo_root=str(root), initialize=True)
    state.load_rocket_into_config("hefesto_ork")
    assert state.preset_ork_drag_table() is not None

    analytical = state.set_working_drag_source("analytical")
    assert analytical.power_off_drag.asset_name is None

    ork = state.set_working_drag_source("ork_sim")
    assert ork.drag_source == "ork_sim"
    assert ork.power_off_drag.points == ((0.0, 0.4), (0.5, 0.5), (1.0, 0.9))
    assert ork.power_on_drag.points == ((0.0, 0.38), (0.5, 0.48), (1.0, 0.88))

    state.load_rocket_into_config("hefesto_legado")
    assert state.preset_ork_drag_table() is None


def test_config_page_renders_aerodynamics_controls(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)

    cfg_page = page("/smoke-config-aero")
    with Client(cfg_page) as client:
        render_config_page(state)

        selects = {
            str(el.props.get("label")): el
            for el in client.elements.values()
            if isinstance(el, ui.select)
        }
        source_select = selects["Fonte de Arrasto (drag_source)"]
        assert set(source_select.options) == {
            "analytical",
            "ork_sim",
            "rasaero_csv",
            "legacy_csv",
        }
        assert source_select.value == "legacy_csv"
        finish_select = selects["Acabamento Superficial (finish)"]
        assert set(finish_select.options) == {"smooth", "regular", "rough", "unfinished"}
        assert finish_select.value == "regular"
        assert any(isinstance(el, ui.upload) for el in client.elements.values())
        assert any("Seção D — Aerodinâmica Multi-Fonte" in text for text in _labels(client))
        # hefesto_v1 has no <flightdata> curve: the ork_sim hint must be visible.
        assert any("Simulação .ork Importada indisponível" in text for text in _labels(client))

        payload = _single_aero_payload(client)
        # Default window clips the 2500-point legacy CSV to Mach 0.01 .. 1.5.
        assert len(_trace(payload, "CD Power-Off")["x"]) == 150
        assert max(_trace(payload, "CD Power-Off")["x"]) == pytest.approx(1.5)
        assert _trace(payload, "CD Power-On")["y"] != _trace(payload, "CD Power-Off")["y"]
    client.delete()

    assert not (REPO_ROOT / ".nicegui").exists()
    assert not (root / "data" / "runs").exists()


@pytest.mark.anyio
async def test_config_page_aerodynamics_chart_refreshes_on_state_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nicegui.testing import user_simulation

    from frontend.app import register_pages
    from frontend.state import AppState

    root = _seed_isolated_workspace(tmp_path)
    monkeypatch.setenv("NICEGUI_STORAGE_PATH", str(tmp_path / ".nicegui"))

    async with user_simulation() as user:
        register_pages(repo_root=str(root))
        await user.open("/config")
        await user.should_see("Seção D — Aerodinâmica Multi-Fonte (Cd × Mach)")

        client = user.client
        assert client is not None
        state = client.storage.get("hefesto_app_state")
        assert isinstance(state, AppState)

        legacy_payload = _single_aero_payload(client)
        assert len(_trace(legacy_payload, "CD Power-Off")["x"]) == 150

        state.set_working_drag_source("analytical")
        await asyncio.sleep(0.2)
        analytical_payload = _single_aero_payload(client)
        assert len(_trace(analytical_payload, "CD Power-Off")["x"]) == 61
        assert max(_trace(analytical_payload, "CD Power-Off")["x"]) == pytest.approx(1.5)
        await user.should_see("drag_source: analytical")

        state.drag_chart_max_mach = 3.0
        state.notify()
        await asyncio.sleep(0.2)
        extended_payload = _single_aero_payload(client)
        assert max(_trace(extended_payload, "CD Power-Off")["x"]) == pytest.approx(3.0)

        state.set_working_surface_finish(SurfaceFinish.UNFINISHED)
        await asyncio.sleep(0.2)
        rough_payload = _single_aero_payload(client)
        assert _trace(rough_payload, "CD Power-Off")["y"] != _trace(
            extended_payload, "CD Power-Off"
        )["y"]

        working = state.ensure_working_rocket()
        state.update_working_rocket(
            recalculate_rocket_structure(
                working.model_copy(
                    update={
                        "nose_cone": working.nose_cone.model_copy(update={"length_m": 0.30})
                    }
                )
            )
        )
        await asyncio.sleep(0.2)
        nose_payload = _single_aero_payload(client)
        assert _trace(nose_payload, "CD Power-Off")["y"] != _trace(
            rough_payload, "CD Power-Off"
        )["y"]

        state.import_rasaero_csv(RASAERO_CSV, "l.cs")
        await asyncio.sleep(0.2)
        csv_payload = _single_aero_payload(client)
        assert _trace(csv_payload, "CD Power-Off")["x"] == pytest.approx([0.3, 0.7, 1.2])
        await user.should_see("Arquivo carregado: l.cs")
        await user.should_see("Faixa de Mach importada: 0.3 – 1.2")

        alpha_selects = [
            el
            for el in client.elements.values()
            if isinstance(el, ui.select)
            and str(el.props.get("label")) == "Ângulo de Ataque (alpha_deg) do CSV"
        ]
        assert len(alpha_selects) == 1
        assert set(alpha_selects[0].options) == {0.0, 2.0}

    assert not (REPO_ROOT / ".nicegui").exists()
    assert not (root / "data" / "runs").exists()


def test_config_page_keeps_legacy_drag_untouched_on_geometry_edits(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)

    before = preview_rocket_drag_curves(state.ensure_working_rocket())
    state.set_working_surface_finish(SurfaceFinish.ROUGH)
    after = preview_rocket_drag_curves(state.ensure_working_rocket())

    # finish only feeds the analytical build-up; CSV-backed curves must not move.
    assert after.cd_power_off == before.cd_power_off
    assert state.ensure_working_rocket().surface_finish == SurfaceFinish.ROUGH
    assert state.ensure_working_rocket().power_off_drag.asset_name == "power_off.csv"
