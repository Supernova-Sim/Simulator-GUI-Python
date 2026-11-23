"""Motor dropdown and OpenMotor .ric upload dialog for the propulsion section."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from nicegui import ui
from nicegui.events import UploadEventArguments

if TYPE_CHECKING:
    from frontend.state import AppState


def render_motor_import_dialog(
    state: AppState,
    *,
    on_imported: Callable[[], Awaitable[None]],
) -> ui.dialog:
    """Build the .ric upload dialog wired to services.import_openmotor_ric via AppState."""
    dialog = ui.dialog()
    with dialog, ui.card().classes("w-full max-w-xl p-5 gap-3"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Importar motor OpenMotor (.ric)").classes(
                "text-lg font-semibold text-slate-800"
            )
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        ui.label(
            "O arquivo é validado, salvo em data/assets/motors/ e selecionado no foguete ativo."
        ).classes("text-xs text-slate-600")
        save_switch = ui.switch("Salvar também no catálogo (data/catalog/motors/)", value=True)
        status_label = ui.label("Nenhum arquivo .ric enviado nesta sessão.").classes(
            "text-xs text-slate-500"
        )

        async def _handle_upload(event: UploadEventArguments) -> None:
            raw = await event.file.read()
            try:
                preset = state.import_motor_ric(
                    event.file.name,
                    raw,
                    save_to_catalog=bool(save_switch.value),
                )
            except (ValueError, OSError) as exc:
                status_label.set_text(f"Importação rejeitada: {exc}")
                ui.notify(f"Motor .ric rejeitado: {exc}", type="negative")
                return
            status_label.set_text(f"Motor importado: {preset.name}")
            ui.notify(f"Motor '{preset.name}' importado e selecionado.", type="positive")
            dialog.close()
            await on_imported()

        ui.upload(
            label="Enviar arquivo .ric",
            auto_upload=True,
            max_files=1,
            on_upload=_handle_upload,
        ).props('accept=".ric"').classes("w-full")
    return dialog


__all__ = ["render_motor_import_dialog"]
