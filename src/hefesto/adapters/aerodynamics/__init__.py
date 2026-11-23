"""Aerodynamic drag protocols, tabulated databases, and external CSV parsers."""

from __future__ import annotations

from hefesto.adapters.aerodynamics.database_drag import DatabaseDragModel
from hefesto.adapters.aerodynamics.protocol import DragModelProtocol
from hefesto.adapters.aerodynamics.rasaero_csv import (
    parse_rasaero_csv_file,
    parse_rasaero_csv_text,
)

__all__ = [
    "DatabaseDragModel",
    "DragModelProtocol",
    "parse_rasaero_csv_file",
    "parse_rasaero_csv_text",
]
