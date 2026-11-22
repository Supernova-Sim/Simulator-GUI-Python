"""Protocol contract for aerodynamic drag providers consumed by rocket builders."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class DragModelProtocol(Protocol):
    """Structural interface for Mach-dependent power-off and power-on drag models."""

    def power_off_cd(self, mach: float) -> float:
        """Return power-off axial drag coefficient Cd at the given Mach number."""

    def power_on_cd(self, mach: float) -> float:
        """Return power-on axial drag coefficient Cd at the given Mach number."""

    def power_off_curve(self) -> list[tuple[float, float]]:
        """Return in-memory (mach, cd) curve points for power-off flight."""

    def power_on_curve(self) -> list[tuple[float, float]]:
        """Return in-memory (mach, cd) curve points for power-on flight."""


__all__ = ["DragModelProtocol"]
