"""Frontend tests: auto-discovered .ric motors in the dropdown and upload import flow."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from nicegui import Client, ui
from nicegui.page import page

from frontend.pages import render_simulation_page
from frontend.state import create_app_state
from hefesto.services import summarize_rocket_structure

REPO_ROOT = Path(__file__).resolve().parents[2]
RIC_SOURCE = REPO_ROOT / "data" / "assets" / "motors" / "m1001voltas.ric"


def _seed_isolated_workspace(tmp_path: Path) -> Path:
    shutil.copytree(REPO_ROOT / "data" / "assets", tmp_path / "data" / "assets")
    shutil.copytree(REPO_ROOT / "data" / "catalog", tmp_path / "data" / "catalog")
    return tmp_path


def test_state_import_motor_ric_selects_motor_and_recalculates(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)
    before = state.ensure_working_rocket()

    preset = state.import_motor_ric("motor_upload.ric", RIC_SOURCE.read_bytes())

    assert state.selected_motor_id == preset.name == "motor_upload"
    rocket = state.ensure_working_rocket()
    assert rocket.motor.name == "motor_upload"
    assert rocket.motor.motor_asset == "motor_upload.ric"
    # The uploaded .ric is byte-identical to the catalog medusa asset, so its calibrated
    # casing is inherited instead of synthesizing a bare aluminium tube.
    assert rocket.motor.casing == before.motor.casing
    structure = summarize_rocket_structure(rocket)
    assert structure.center_of_mass_m == pytest.approx(rocket.center_of_mass_without_motor_m)
    assert state.has_unsaved_rocket_changes is True

    check = state.run_motor_check()
    assert check is not None
    ballistics, safety = check
    assert ballistics.motor_name == "motor_upload"
    assert ballistics.max_thrust_n > 0.0
    assert len(safety.checks) == 5


def test_state_import_without_catalog_marks_origin_as_ric(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)

    state.import_motor_ric("motor_avulso.ric", RIC_SOURCE.read_bytes(), save_to_catalog=False)

    assert state.selectable_motor_options()["motor_avulso"] == "motor_avulso (.ric)"


def test_state_import_rejects_invalid_ric_without_touching_selection(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)
    selected_before = state.selected_motor_id

    with pytest.raises(ValueError, match="inválido"):
        state.import_motor_ric("quebrado.ric", b"data: [corrupt")

    assert state.selected_motor_id == selected_before
    assert not (root / "data" / "assets" / "motors" / "quebrado.ric").exists()


def test_simulation_page_lists_ric_motors_and_offers_upload(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)

    sim_page = page("/smoke-motor-upload")
    with Client(sim_page) as client:
        render_simulation_page(state)

        selects = {
            str(el.props.get("label")): el
            for el in client.elements.values()
            if isinstance(el, ui.select)
        }
        motor_select = selects["Motor"]
        assert "medusa_knsb_a" in motor_select.options
        assert "m1001voltas" in motor_select.options
        assert state.selectable_motor_options()["m1001voltas"] == "m1001voltas (.ric)"

        buttons = [
            el
            for el in client.elements.values()
            if isinstance(el, ui.button) and el.text == "Importar motor (.ric)"
        ]
        assert len(buttons) == 1

        uploads = [el for el in client.elements.values() if isinstance(el, ui.upload)]
        assert len(uploads) == 1
        assert ".ric" in str(uploads[0].props.get("accept"))
    client.delete()

    assert not (REPO_ROOT / ".nicegui").exists()
    assert not (root / "data" / "runs").exists()
