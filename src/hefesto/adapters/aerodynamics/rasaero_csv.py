"""RASAero II CSV drag export parser (Mach x alpha axial-force tables)."""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path

from hefesto.domain import DragCurveTable

_MACH_HEADERS = ("mach number", "mach")
_ALPHA_HEADERS = ("angle of attack (alpha)", "angle of attack", "alpha")
_CD_POWER_OFF_HEADERS = ("cd power-off", "cd power off", "cd", "ca power-off", "ca power off")
_CD_POWER_ON_HEADERS = ("cd power-on", "cd power on", "cd", "ca power-on", "ca power on")
_HEADER_SCAN_LIMIT = 40
_ALPHA_KEY_DECIMALS = 9
_AXIAL_ALPHA = 0.0


def _normalize_header(cell: str) -> str:
    return " ".join(cell.replace("\ufeff", "").strip().casefold().split())


def _find_column(headers: list[str], candidates: tuple[str, ...], label: str) -> int:
    for candidate in candidates:
        if candidate in headers:
            return headers.index(candidate)
    raise ValueError(
        f"RASAero CSV missing {label} column; accepted headers: "
        f"{', '.join(repr(name) for name in candidates)}"
    )


def _parse_cell(token: str, *, label: str, source_name: str, lineno: int) -> float:
    try:
        value = float(token)
    except ValueError as exc:
        raise ValueError(
            f"{source_name}:{lineno}: invalid numeric {label}: {token!r}"
        ) from exc
    if not math.isfinite(value):
        raise ValueError(f"{source_name}:{lineno}: {label} must be finite, got {token!r}")
    return value


def parse_rasaero_csv_text(text: str, *, source_name: str = "<rasaero_csv>") -> DragCurveTable:
    """Parse a RASAero II aerodynamic CSV export into a Mach-indexed DragCurveTable."""
    rows = list(csv.reader(io.StringIO(text)))
    header_index = -1
    headers: list[str] = []
    for index, row in enumerate(rows[:_HEADER_SCAN_LIMIT]):
        normalized = [_normalize_header(cell) for cell in row]
        if any(name in normalized for name in _MACH_HEADERS) and any(
            name in normalized for name in _ALPHA_HEADERS
        ):
            header_index = index
            headers = normalized
            break
    if header_index < 0:
        raise ValueError(
            f"{source_name}: no RASAero header row with 'Mach Number' and "
            f"'Angle of Attack (alpha)' found in the first {_HEADER_SCAN_LIMIT} lines"
        )

    mach_index = _find_column(headers, _MACH_HEADERS, "Mach Number")
    alpha_index = _find_column(headers, _ALPHA_HEADERS, "Angle of Attack (alpha)")
    cd_off_index = _find_column(headers, _CD_POWER_OFF_HEADERS, "CD Power-Off")
    cd_on_index = _find_column(headers, _CD_POWER_ON_HEADERS, "CD Power-On")

    samples: list[tuple[float, float, float, float]] = []
    for lineno, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        cells = [cell.strip() for cell in row]
        if not any(cells) or cells[0].startswith("#"):
            continue
        if len(cells) <= max(mach_index, alpha_index, cd_off_index, cd_on_index):
            raise ValueError(
                f"{source_name}:{lineno}: expected at least "
                f"{max(mach_index, alpha_index, cd_off_index, cd_on_index) + 1} columns, "
                f"got {len(cells)}"
            )
        mach = _parse_cell(cells[mach_index], label="Mach", source_name=source_name, lineno=lineno)
        alpha = _parse_cell(
            cells[alpha_index], label="alpha", source_name=source_name, lineno=lineno
        )
        cd_off = _parse_cell(
            cells[cd_off_index], label="CD Power-Off", source_name=source_name, lineno=lineno
        )
        cd_on = _parse_cell(
            cells[cd_on_index], label="CD Power-On", source_name=source_name, lineno=lineno
        )
        if mach < 0.0:
            raise ValueError(f"{source_name}:{lineno}: Mach must be >= 0, got {mach!r}")
        if cd_off < 0.0 or cd_on < 0.0:
            raise ValueError(
                f"{source_name}:{lineno}: CD values must be >= 0, got {(cd_off, cd_on)!r}"
            )
        samples.append((mach, alpha, cd_off, cd_on))

    if not samples:
        raise ValueError(f"{source_name}: RASAero CSV contains no data rows")

    rows_by_alpha: dict[float, list[tuple[float, float, float]]] = {}
    for mach, alpha, cd_off, cd_on in samples:
        key = round(alpha, _ALPHA_KEY_DECIMALS)
        rows_by_alpha.setdefault(key, []).append((mach, cd_off, cd_on))

    alphas = sorted(rows_by_alpha)
    axial = [value for value in alphas if abs(value - _AXIAL_ALPHA) <= 1e-9]
    if not axial:
        raise ValueError(
            f"{source_name}: no alpha = 0 rows found (alpha values: {alphas[:8]!r}); "
            "the axial drag curve is required"
        )

    mach_axis: tuple[float, ...] | None = None
    grid_off: list[list[float]] = []
    grid_on: list[list[float]] = []
    for alpha in alphas:
        entries = sorted(rows_by_alpha[alpha])
        mach_values = tuple(entry[0] for entry in entries)
        if len(set(mach_values)) != len(mach_values):
            raise ValueError(f"{source_name}: duplicated Mach value for alpha={alpha}")
        if mach_axis is None:
            mach_axis = mach_values
        elif mach_values != mach_axis:
            raise ValueError(
                f"{source_name}: alpha={alpha} does not share the same Mach grid; "
                "a rectangular RASAero table is required"
            )
        grid_off.append([entry[1] for entry in entries])
        grid_on.append([entry[2] for entry in entries])

    assert mach_axis is not None
    axial_index = alphas.index(axial[0])
    include_grid = len(alphas) > 1
    return DragCurveTable(
        mach=list(mach_axis),
        cd_power_off=list(grid_off[axial_index]),
        cd_power_on=list(grid_on[axial_index]),
        source="rasaero_csv",
        alpha_deg=list(alphas) if include_grid else [],
        cd_alpha_power_off=[list(row) for row in grid_off] if include_grid else [],
        cd_alpha_power_on=[list(row) for row in grid_on] if include_grid else [],
    )


def parse_rasaero_csv_file(path: Path) -> DragCurveTable:
    """Read a RASAero II CSV export from disk into a DragCurveTable."""
    if not path.is_file():
        raise FileNotFoundError(f"RASAero CSV file not found: {path}")
    return parse_rasaero_csv_text(
        path.read_text(encoding="utf-8-sig"), source_name=path.name
    )


__all__ = ["parse_rasaero_csv_file", "parse_rasaero_csv_text"]
