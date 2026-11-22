"""Guided OpenMotor override selector and active override editor component."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from nicegui import ui
from pydantic import ValidationError

from hefesto.domain import MotorOverride, MotorOverrideOption

if TYPE_CHECKING:
    from frontend.state import AppState

_GROUP_LABELS: dict[str, str] = {
    "nozzle": "Tubeira",
    "grain": "Grãos",
    "propellant": "Propelente",
    "config": "Solver",
}


def parse_override_value(raw: str) -> float | int | str:
    """Parse a MotorOverride value string into int, finite float, or non-empty str."""
    stripped = raw.strip()
    if not stripped:
        raise ValueError("Informe um valor não vazio para o override.")

    if stripped.lstrip("+-").isdigit():
        return int(stripped)

    try:
        numeric = float(stripped)
    except ValueError:
        return stripped

    if not math.isfinite(numeric):
        raise ValueError(f"Valor numérico inválido (não finito): {raw!r}")
    return numeric


def format_override_option_label(option: MotorOverrideOption) -> str:
    """Format a guided MotorOverrideOption with group, SI unit, and current .ric value."""
    group_pt = _GROUP_LABELS.get(option.group, option.group)
    current_str = f" · atual: {option.current_value}" if option.current_value is not None else ""
    unit_str = f" [{option.unit}]" if option.unit != "-" else ""
    return f"[{group_pt}] {option.label} ({option.path}){unit_str}{current_str}"


def format_override_label(
    override: MotorOverride,
    options_by_path: dict[str, MotorOverrideOption] | None = None,
) -> str:
    """Format an active MotorOverride with unit/label context when available."""
    opt = options_by_path.get(override.path) if options_by_path else None
    if opt is None:
        return f"{override.path} = {override.value}"
    unit_str = f" {opt.unit}" if opt.unit != "-" else ""
    return f"{opt.label} ({override.path}) = {override.value}{unit_str}"


def render_motor_overrides_editor(
    state: AppState,
    *,
    on_change: Callable[[], None] | None = None,
) -> ui.column:
    """Render guided OpenMotor override selector, value editor, and active override list."""
    container = ui.column().classes("w-full gap-2")

    @ui.refreshable
    def _render_body() -> None:
        options = state.available_motor_override_options()
        options_by_path = {opt.path: opt for opt in options}
        select_options = {opt.path: format_override_option_label(opt) for opt in options}

        if not options:
            ui.label(
                "O motor selecionado não possui arquivo .ric; overrides OpenMotor indisponíveis."
            ).classes("text-xs text-amber-700")
            return

        default_path = "nozzle.throat" if "nozzle.throat" in options_by_path else options[0].path
        default_opt = options_by_path[default_path]
        default_val = "" if default_opt.current_value is None else str(default_opt.current_value)

        with ui.row().classes("w-full items-end gap-2 flex-wrap"):
            path_select = ui.select(
                options=select_options,
                value=default_path,
                label="Parâmetro OpenMotor (.ric)",
                with_input=True,
            ).classes("flex-1 min-w-72")

            value_input = ui.input(
                label=f"Valor ({default_opt.unit})",
                value=default_val,
                placeholder="ex.: 0.036 ou Both",
            ).classes("w-52")

            def _on_select_path(raw_path: object) -> None:
                path = str(raw_path or "")
                opt = options_by_path.get(path)
                if opt is None:
                    return
                value_input.props(f'label="Valor ({opt.unit})"')
                existing = next(
                    (item.value for item in state.motor_overrides if item.path == path),
                    None,
                )
                if existing is not None:
                    value_input.value = str(existing)
                elif opt.current_value is not None:
                    value_input.value = str(opt.current_value)
                else:
                    value_input.value = ""

            path_select.on_value_change(lambda e: _on_select_path(e.value))

            def _add_or_update_override() -> None:
                raw_path = str(path_select.value or "").strip()
                raw_val = value_input.value or ""
                try:
                    parsed = parse_override_value(raw_val)
                    item = MotorOverride(path=raw_path, value=parsed)
                except (ValidationError, ValueError) as exc:
                    ui.notify(f"Override inválido: {exc}", type="negative")
                    return

                filtered = tuple(ov for ov in state.motor_overrides if ov.path != raw_path)
                state.motor_overrides = (*filtered, item)
                _render_list.refresh()
                if on_change is not None:
                    on_change()

            def _clear_overrides() -> None:
                state.motor_overrides = ()
                _render_list.refresh()
                if on_change is not None:
                    on_change()

            ui.button(
                "Aplicar Override",
                icon="add",
                on_click=_add_or_update_override,
            ).props("outline color=primary")
            ui.button(
                "Limpar Tudo",
                icon="clear_all",
                on_click=_clear_overrides,
            ).props("flat color=grey")

        @ui.refreshable
        def _render_list() -> None:
            if not state.motor_overrides:
                ui.label("Nenhum override de motor ativo.").classes("text-xs text-slate-500")
                return
            with ui.column().classes("w-full gap-1"):
                for idx, override in enumerate(state.motor_overrides):
                    with ui.row().classes(
                        "w-full items-center justify-between bg-slate-50 border "
                        "border-slate-200 rounded px-2 py-1"
                    ):
                        ui.label(format_override_label(override, options_by_path)).classes(
                            "text-xs font-mono text-slate-800"
                        )
                        with ui.row().classes("items-center gap-1"):
                            def _edit(target: MotorOverride = override) -> None:
                                if target.path in options_by_path:
                                    path_select.value = target.path
                                value_input.value = str(target.value)

                            def _remove(target_idx: int = idx) -> None:
                                state.motor_overrides = tuple(
                                    item
                                    for item_idx, item in enumerate(state.motor_overrides)
                                    if item_idx != target_idx
                                )
                                _render_list.refresh()
                                if on_change is not None:
                                    on_change()

                            ui.button(icon="edit", on_click=_edit).props(
                                "flat dense round size=sm color=primary"
                            )
                            ui.button(icon="delete", on_click=_remove).props(
                                "flat dense round size=sm color=negative"
                            )

        _render_list()

    with container:
        _render_body()

    return container


__all__ = [
    "format_override_label",
    "format_override_option_label",
    "parse_override_value",
    "render_motor_overrides_editor",
]
