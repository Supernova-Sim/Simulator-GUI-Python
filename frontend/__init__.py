"""NiceGUI presentation layer: pages, reusable components, and reactive AppState.

Widgets call hefesto.services and read hefesto.domain only: the AST Gate forbids
importing hefesto.adapters, hefesto.physics, and hefesto.storage here. State is
per-client and refreshed via AppState.notify; frontend imports domain/services/frontend.
"""

from __future__ import annotations

from frontend.state import AppState, create_app_state, get_client_state

__all__ = [
    "AppState",
    "create_app_state",
    "get_client_state",
]
