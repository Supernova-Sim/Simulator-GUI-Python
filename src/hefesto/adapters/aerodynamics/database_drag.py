"""Tabulated Mach vs Cd aerodynamic drag model backed by in-memory DragCurveSpec."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from hefesto.domain import DragCurveSpec, RocketSpec


def _validate_positive_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and > 0, got {value!r}")
    return float(value)


def _validate_non_negative_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and >= 0, got {value!r}")
    return float(value)


@dataclass(frozen=True)
class DatabaseDragModel:
    """In-memory tabulated drag provider implementing DragModelProtocol with linear lookup."""

    power_off: DragCurveSpec
    power_on: DragCurveSpec
    drag_factor: float = 1.0
    _off_mach: NDArray[np.float64] = field(init=False, repr=False, compare=False)
    _off_cd: NDArray[np.float64] = field(init=False, repr=False, compare=False)
    _on_mach: NDArray[np.float64] = field(init=False, repr=False, compare=False)
    _on_cd: NDArray[np.float64] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        factor = _validate_positive_finite(self.drag_factor, "drag_factor")
        object.__setattr__(self, "drag_factor", factor)

        off_mach = np.array([pt[0] for pt in self.power_off.points], dtype=np.float64)
        off_cd = np.array([pt[1] * factor for pt in self.power_off.points], dtype=np.float64)
        on_mach = np.array([pt[0] for pt in self.power_on.points], dtype=np.float64)
        on_cd = np.array([pt[1] * factor for pt in self.power_on.points], dtype=np.float64)

        object.__setattr__(self, "_off_mach", off_mach)
        object.__setattr__(self, "_off_cd", off_cd)
        object.__setattr__(self, "_on_mach", on_mach)
        object.__setattr__(self, "_on_cd", on_cd)

    @classmethod
    def from_rocket(
        cls,
        rocket: RocketSpec,
        *,
        drag_factor: float = 1.0,
    ) -> DatabaseDragModel:
        """Build a DatabaseDragModel directly from a RocketSpec domain model."""
        return cls(
            power_off=rocket.power_off_drag,
            power_on=rocket.power_on_drag,
            drag_factor=drag_factor,
        )

    def scaled(self, drag_factor: float) -> DatabaseDragModel:
        """Return a new DatabaseDragModel with the given absolute drag multiplier."""
        return DatabaseDragModel(
            power_off=self.power_off,
            power_on=self.power_on,
            drag_factor=drag_factor,
        )

    def power_off_cd(self, mach: float) -> float:
        """Interpolate power-off Cd linearly over Mach with constant endpoint clamping."""
        m = _validate_non_negative_finite(mach, "mach")
        return float(np.interp(m, self._off_mach, self._off_cd))

    def power_on_cd(self, mach: float) -> float:
        """Interpolate power-on Cd linearly over Mach with constant endpoint clamping."""
        m = _validate_non_negative_finite(mach, "mach")
        return float(np.interp(m, self._on_mach, self._on_cd))

    def power_off_curve(self) -> list[tuple[float, float]]:
        """Return scaled power-off (mach, cd) points as a fresh in-memory list."""
        return [
            (float(mach), float(cd * self.drag_factor))
            for mach, cd in self.power_off.points
        ]

    def power_on_curve(self) -> list[tuple[float, float]]:
        """Return scaled power-on (mach, cd) points as a fresh in-memory list."""
        return [
            (float(mach), float(cd * self.drag_factor))
            for mach, cd in self.power_on.points
        ]

    def to_specs(self) -> tuple[DragCurveSpec, DragCurveSpec]:
        """Return scaled (power_off, power_on) DragCurveSpec models."""
        return (
            DragCurveSpec(
                points=tuple(self.power_off_curve()),
                asset_name=self.power_off.asset_name,
            ),
            DragCurveSpec(
                points=tuple(self.power_on_curve()),
                asset_name=self.power_on.asset_name,
            ),
        )


__all__ = ["DatabaseDragModel"]
