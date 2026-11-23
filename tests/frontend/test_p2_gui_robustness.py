"""Regression tests for Wave-2 P2 GUI robustness (async races, overrides, inputs)."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest
from nicegui import Client, ui
from nicegui.page import page

from frontend.pages.simulation_page import (
    _set_positive_factor,
    _update_launch,
    execute_simulation_async,
)
from frontend.state import AppState, create_app_state, get_client_state
from hefesto.domain import LaunchConfig, MotorOverride

REPO_ROOT = Path(__file__).resolve().parents[2]


def _seed_isolated_workspace(tmp_path: Path) -> Path:
    shutil.copytree(REPO_ROOT / "data" / "assets", tmp_path / "data" / "assets")
    shutil.copytree(REPO_ROOT / "data" / "catalog", tmp_path / "data" / "catalog")
    return tmp_path


def test_get_client_state_is_isolated_per_client_and_reused_within_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _seed_isolated_workspace(tmp_path)
    monkeypatch.setenv("NICEGUI_STORAGE_PATH", str(tmp_path / ".nicegui"))
    first_client = Client(page("/client-one"))
    second_client = Client(page("/client-two"))

    with first_client:
        first_state = get_client_state(repo_root=str(root))
        first_state.drag_factor = 1.75

    with second_client:
        second_state = get_client_state(repo_root=str(root))
        assert isinstance(second_state, AppState)
        assert second_state is not first_state
        assert second_state.drag_factor == pytest.approx(1.0)

    with first_client:
        assert get_client_state(repo_root=str(root)) is first_state
        assert first_state.drag_factor == pytest.approx(1.75)

    first_client.delete()
    second_client.delete()


def test_numeric_launch_inputs_validate_and_roll_back_widget_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frontend.pages import simulation_page

    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)
    state.launch_config = LaunchConfig()
    notices: list[tuple[str, str | None]] = []

    def _notify(message: object, **kwargs: object) -> None:
        notices.append((str(message), str(kwargs.get("type")) if kwargs.get("type") else None))

    monkeypatch.setattr(simulation_page.ui, "notify", _notify)
    client = Client(page("/numeric-inputs"))
    with client:
        rail_control = ui.number(label="Trilho", value=state.launch_config.rail_length_m)
        inclination_control = ui.number(
            label="Inclinação", value=state.launch_config.inclination_deg
        )
        heading_control = ui.number(label="Azimute", value=state.launch_config.heading_deg)
        factor_control = ui.number(label="Arrasto", value=state.drag_factor)

        for invalid in (None, float("nan"), float("inf"), -1.0, 0.0):
            _update_launch(state, rail_length_m=invalid, control=rail_control)
            assert state.launch_config.rail_length_m == pytest.approx(6.0)
            assert rail_control.value == pytest.approx(6.0)
            assert notices[-1][1] == "negative"

        for invalid in (None, float("nan"), 0.0, -5.0, 90.5):
            _update_launch(state, inclination_deg=invalid, control=inclination_control)
            assert state.launch_config.inclination_deg == pytest.approx(88.0)
            assert inclination_control.value == pytest.approx(88.0)
            assert notices[-1][1] == "negative"

        for invalid in (None, float("nan"), -1.0, 360.5):
            _update_launch(state, heading_deg=invalid, control=heading_control)
            assert state.launch_config.heading_deg == pytest.approx(90.0)
            assert heading_control.value == pytest.approx(90.0)
            assert notices[-1][1] == "negative"

        # 360 deg is accepted as the same heading as 0 deg.
        _update_launch(state, heading_deg=360, control=heading_control)
        assert state.launch_config.heading_deg == pytest.approx(0.0)

        for invalid in (None, float("nan"), -2.0, 0.0):
            _set_positive_factor(state, "drag_factor", invalid, control=factor_control)
            assert state.drag_factor == pytest.approx(1.0)
            assert factor_control.value == pytest.approx(1.0)
            assert notices[-1][1] == "negative"

        _set_positive_factor(state, "drag_factor", 1.2, control=factor_control)
        assert state.drag_factor == pytest.approx(1.2)

    client.delete()


@pytest.mark.anyio
async def test_simulation_discards_stale_result_when_configuration_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frontend.pages import simulation_page

    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)
    state.launch_config = LaunchConfig(terminate_on_apogee=True)
    notices: list[tuple[str, str | None]] = []

    def _notify(message: object, **kwargs: object) -> None:
        notices.append((str(message), str(kwargs.get("type")) if kwargs.get("type") else None))

    async def _fake_cpu_bound(*_args: object, **_kwargs: object) -> object:
        # Simulate a motor change while the 6-DOF run is executing in the worker process.
        state.selected_motor_id = "medusa_n3174"
        return object()

    monkeypatch.setattr(simulation_page.ui, "notify", _notify)
    monkeypatch.setattr(simulation_page.run, "cpu_bound", _fake_cpu_bound)

    result = await execute_simulation_async(state)

    assert result is None
    assert state.current_result is None
    assert state.simulation_config is not None
    assert not state.is_running
    assert "descartado" in state.status_message.lower()
    assert notices and notices[-1][1] == "warning"


def test_apply_motor_casing_noop_keeps_working_spec_and_unsaved_flag(
    tmp_path: Path,
) -> None:
    root = _seed_isolated_workspace(tmp_path)
    state = create_app_state(repo_root=str(root), initialize=True)
    rocket = state.ensure_working_rocket()
    casing = rocket.motor.casing
    state.has_unsaved_rocket_changes = False

    result = state.apply_motor_casing_update(
        new_length_m=casing.length_m,
        mode="tubular_delta",
        material_density_kg_m3=2700.0,
        motor_position_m=rocket.motor_position_m,
        grain_separation_m=rocket.motor.grain_separation_m,
        internal_clearance_m=casing.internal_clearance_m,
        wall_thickness_m=casing.wall_thickness_m,
        fixed_hardware_mass_kg=state.fixed_hardware_mass_kg(),
    )

    assert state.working_rocket_spec is rocket
    assert not state.has_unsaved_rocket_changes
    assert result.delta_mass_kg == 0.0
    assert state.last_casing_resize_result == result


@pytest.mark.slow
@pytest.mark.anyio
async def test_motor_overrides_editor_refreshes_after_motor_selection_resets_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nicegui.testing import user_simulation

    from frontend.app import register_pages

    root = _seed_isolated_workspace(tmp_path)
    monkeypatch.setenv("NICEGUI_STORAGE_PATH", str(tmp_path / ".nicegui"))

    async with user_simulation() as user:
        register_pages(repo_root=str(root))
        await user.open("/config")
        await user.should_see("Nenhum override de motor ativo.")

        client = user.client
        assert client is not None
        with client:
            state = get_client_state(repo_root=str(root))
            state.motor_overrides = (MotorOverride(path="nozzle.throat", value=0.04321),)
            state.notify()
        await asyncio.sleep(0.2)
        await user.should_see("0.04321")

        with client:
            state.load_motor_into_session("medusa_n3002_v2")
        await asyncio.sleep(0.2)
        assert state.motor_overrides == ()
        await user.should_see("Nenhum override de motor ativo.")
        await user.should_not_see("0.04321")
