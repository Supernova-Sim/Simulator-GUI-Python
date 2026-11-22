"""Aerodynamic drag protocols and tabulated drag database implementations."""

from __future__ import annotations

from hefesto.adapters.aerodynamics.database_drag import DatabaseDragModel
from hefesto.adapters.aerodynamics.protocol import DragModelProtocol

__all__ = [
    "DatabaseDragModel",
    "DragModelProtocol",
]
