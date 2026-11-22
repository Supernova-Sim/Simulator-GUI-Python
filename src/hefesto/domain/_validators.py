"""Pure domain validation helpers shared across Hefesto domain models."""

from __future__ import annotations

import math


def require_non_empty_text(value: str, field_name: str) -> str:
    """Strip surrounding whitespace and reject blank strings."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must be a non-empty string")
    return cleaned


def require_relative_asset(value: str, field_name: str) -> str:
    """Ensure an asset reference is a clean relative path without parent traversal."""
    cleaned = require_non_empty_text(value, field_name)
    normalized = cleaned.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized:
        raise ValueError(f"{field_name} must be a relative asset path, got {value!r}")
    parts = [part for part in normalized.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        raise ValueError(f"{field_name} must not contain '.' or '..' segments: {value!r}")
    return normalized


def require_axisymmetric_inertia(
    inertia: tuple[float, float, float],
    field_name: str,
) -> tuple[float, float, float]:
    """Validate positive finite axisymmetric inertia tensor (I_t, I_t, I_l)."""
    i_t1, i_t2, i_l = inertia
    if not all(math.isfinite(val) and val > 0.0 for val in (i_t1, i_t2, i_l)):
        raise ValueError(f"{field_name} components must be positive and finite: {inertia!r}")
    if not math.isclose(i_t1, i_t2, rel_tol=1e-6, abs_tol=1e-12):
        raise ValueError(
            f"{field_name} must be axisymmetric (I_t, I_t, I_l), got {inertia!r}"
        )
    return inertia


def require_xy_curve(
    points: tuple[tuple[float, float], ...],
    *,
    x_name: str,
    y_name: str,
    min_points: int = 2,
    min_x: float | None = 0.0,
    min_y: float | None = 0.0,
    strict_x: bool = True,
) -> tuple[tuple[float, float], ...]:
    """Validate finite 2D curve samples with monotonic abscissa."""
    if len(points) < min_points:
        raise ValueError(f"Curve must contain at least {min_points} points, got {len(points)}")

    prev_x: float | None = None
    for idx, (x_val, y_val) in enumerate(points):
        if not (math.isfinite(x_val) and math.isfinite(y_val)):
            raise ValueError(f"Curve point [{idx}] contains non-finite values: {(x_val, y_val)!r}")
        if min_x is not None and x_val < min_x:
            raise ValueError(f"Curve {x_name} at [{idx}] must be >= {min_x}, got {x_val}")
        if min_y is not None and y_val < min_y:
            raise ValueError(f"Curve {y_name} at [{idx}] must be >= {min_y}, got {y_val}")
        if prev_x is not None:
            valid_order = x_val > prev_x if strict_x else x_val >= prev_x
            if not valid_order:
                raise ValueError(
                    f"Curve {x_name} must be monotonically increasing at [{idx}]: "
                    f"{prev_x} -> {x_val}"
                )
        prev_x = x_val
    return points


def require_burn_time(value: tuple[float, float]) -> tuple[float, float]:
    """Validate finite non-negative burn window (start_s, end_s) with end_s > start_s."""
    t_start, t_end = value
    if not (math.isfinite(t_start) and math.isfinite(t_end)) or t_start < 0.0 or t_end <= t_start:
        raise ValueError(f"burn_time_s must satisfy 0 <= start < end, got {value!r}")
    return value
