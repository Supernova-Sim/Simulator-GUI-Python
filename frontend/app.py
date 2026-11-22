"""Main NiceGUI application entrypoint and multi-page navigation shell."""

from __future__ import annotations

import os

from nicegui import ui

from frontend.pages import (
    render_assets_page,
    render_config_page,
    render_history_page,
    render_simulation_page,
)
from frontend.state import AppState, get_client_state

_APP_TITLE = "Hefesto V1 — Simulação 6-DOF"


def build_app_shell(state: AppState) -> None:
    """Render the shared header navigation and client-side ui.sub_pages router."""
    with ui.header().classes("bg-slate-900 text-white px-4 py-2 items-center justify-between"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("rocket_launch").classes("text-2xl text-sky-400")
            ui.label(_APP_TITLE).classes("text-base font-bold tracking-wide")

        with ui.row().classes("items-center gap-2"):
            ui.button(
                "Simulação",
                icon="play_circle",
                on_click=lambda: ui.navigate.to("/"),
            ).props("flat color=white")
            ui.button(
                "Configuração",
                icon="tune",
                on_click=lambda: ui.navigate.to("/config"),
            ).props("flat color=white")
            ui.button(
                "Assets",
                icon="folder_open",
                on_click=lambda: ui.navigate.to("/assets"),
            ).props("flat color=white")
            ui.button(
                "Histórico",
                icon="history",
                on_click=lambda: ui.navigate.to("/history"),
            ).props("flat color=white")

    ui.sub_pages(
        {
            "/": lambda: render_simulation_page(state),
            "/config": lambda: render_config_page(state),
            "/assets": lambda: render_assets_page(state),
            "/history": lambda: render_history_page(state),
        }
    ).classes("w-full max-w-7xl mx-auto p-4")


def register_pages(repo_root: str | None = None) -> None:
    """Register /, /config, /assets, and /history routes on the active NiceGUI app."""

    @ui.page("/", title=_APP_TITLE)
    def _simulation_route() -> None:
        build_app_shell(get_client_state(repo_root=repo_root))

    @ui.page("/config", title=f"Configuração · {_APP_TITLE}")
    def _config_route() -> None:
        build_app_shell(get_client_state(repo_root=repo_root))

    @ui.page("/assets", title=f"Assets · {_APP_TITLE}")
    def _assets_route() -> None:
        build_app_shell(get_client_state(repo_root=repo_root))

    @ui.page("/history", title=f"Histórico · {_APP_TITLE}")
    def _history_route() -> None:
        build_app_shell(get_client_state(repo_root=repo_root))


def main(
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    reload: bool = False,
    show: bool = False,
) -> None:
    """Launch the NiceGUI server for Hefesto V1."""
    ui.run(
        title=_APP_TITLE,
        host=host,
        port=port,
        reload=reload,
        show=show,
        storage_secret=None,
    )


register_pages(repo_root=os.environ.get("HEFESTO_REPO_ROOT") or None)

if __name__ in {"__main__", "__mp_main__"}:
    main()
