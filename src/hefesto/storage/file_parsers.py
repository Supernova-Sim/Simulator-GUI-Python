"""In-memory RASP .eng thrust curve and .csv drag curve parsers without RocketPy NaN bugs."""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path

from hefesto.domain import DragCurveSpec


def _parse_finite_non_negative(token: str, *, label: str, source_name: str, lineno: int) -> float:
    try:
        value = float(token)
    except ValueError as exc:
        raise ValueError(
            f"{source_name}:{lineno}: invalid numeric {label}: {token!r}"
        ) from exc
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(
            f"{source_name}:{lineno}: {label} must be finite and >= 0, got {value!r}"
        )
    return value


def parse_eng_text(
    text: str,
    *,
    prepend_zero_origin: bool = True,
    source_name: str = "<eng>",
) -> list[tuple[float, float]]:
    """Parse RASP .eng content into finite (time_s, thrust_n) pairs without duplicate t=0."""
    header_found = False
    points: list[tuple[float, float]] = []
    prev_time: float | None = None

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        # Strip RASP ';' comments before whitespace check to tolerate comment-only/blank lines.
        cleaned = raw_line.split(";", 1)[0].strip()
        if not cleaned:
            continue

        tokens = cleaned.split()
        if not header_found:
            if len(tokens) < 3:
                raise ValueError(
                    f"{source_name}:{lineno}: expected RASP header line before data points, "
                    f"got {cleaned!r}"
                )
            header_found = True
            continue

        if len(tokens) != 2:
            raise ValueError(
                f"{source_name}:{lineno}: expected 2 tokens (time thrust), got {len(tokens)}"
            )

        time_s = _parse_finite_non_negative(
            tokens[0], label="time_s", source_name=source_name, lineno=lineno
        )
        thrust_n = _parse_finite_non_negative(
            tokens[1], label="thrust_n", source_name=source_name, lineno=lineno
        )
        if prev_time is not None and time_s <= prev_time:
            raise ValueError(
                f"{source_name}:{lineno}: time_s must strictly increase "
                f"({prev_time} -> {time_s})"
            )
        prev_time = time_s
        points.append((time_s, thrust_n))

    if not header_found:
        raise ValueError(f"{source_name}: empty .eng file (missing RASP header)")
    if not points:
        raise ValueError(f"{source_name}: .eng file contains no thrust points")

    # Prepend (0, 0) only when the file omits t=0; duplicating t=0 causes NaN in RocketPy.
    if prepend_zero_origin and points[0][0] > 0.0:
        points.insert(0, (0.0, 0.0))

    if len(points) < 2:
        raise ValueError(
            f"{source_name}: thrust curve requires at least 2 points, got {len(points)}"
        )
    return points


def parse_eng_file(
    path: Path,
    *,
    prepend_zero_origin: bool = True,
) -> list[tuple[float, float]]:
    """Read and parse a RASP .eng file into an in-memory list of (time_s, thrust_n) tuples."""
    if not path.is_file():
        raise FileNotFoundError(f"Thrust curve .eng file not found: {path}")
    return parse_eng_text(
        path.read_text(encoding="utf-8"),
        prepend_zero_origin=prepend_zero_origin,
        source_name=path.name,
    )


def _row_looks_like_text_header(col_x: str, col_y: str) -> bool:
    for cell in (col_x, col_y):
        try:
            float(cell)
        except ValueError:
            return True
    return False


def parse_csv_text(text: str, *, source_name: str = "<csv>") -> list[tuple[float, float]]:
    """Parse two-column CSV curve text into strictly increasing finite (x, y) pairs."""
    points: list[tuple[float, float]] = []
    prev_x: float | None = None
    saw_data_or_header = False

    reader = csv.reader(io.StringIO(text))
    for lineno, row in enumerate(reader, start=1):
        cells = [cell.strip() for cell in row]
        if not cells or all(cell == "" for cell in cells):
            continue
        if cells[0].startswith("#"):
            continue
        if len(cells) != 2 or not cells[0] or not cells[1]:
            raise ValueError(
                f"{source_name}:{lineno}: expected 2 non-empty CSV columns, got {row!r}"
            )

        if not saw_data_or_header:
            saw_data_or_header = True
            if _row_looks_like_text_header(cells[0], cells[1]):
                continue

        x_val = _parse_finite_non_negative(
            cells[0], label="x", source_name=source_name, lineno=lineno
        )
        y_val = _parse_finite_non_negative(
            cells[1], label="y", source_name=source_name, lineno=lineno
        )
        if prev_x is not None and x_val <= prev_x:
            raise ValueError(
                f"{source_name}:{lineno}: abscissa must strictly increase ({prev_x} -> {x_val})"
            )
        prev_x = x_val
        points.append((x_val, y_val))

    if len(points) < 2:
        raise ValueError(f"{source_name}: CSV curve requires at least 2 points, got {len(points)}")
    return points


def parse_csv_curve(path: Path) -> list[tuple[float, float]]:
    """Read and parse a two-column CSV curve into an in-memory list of (x, y) tuples."""
    if not path.is_file():
        raise FileNotFoundError(f"CSV curve file not found: {path}")
    return parse_csv_text(path.read_text(encoding="utf-8"), source_name=path.name)


def load_drag_curve(path: Path, *, asset_name: str | None = None) -> DragCurveSpec:
    """Parse a drag CSV file into a validated DragCurveSpec domain model."""
    points = parse_csv_curve(path)
    return DragCurveSpec(points=tuple(points), asset_name=asset_name)


__all__ = [
    "load_drag_curve",
    "parse_csv_curve",
    "parse_csv_text",
    "parse_eng_file",
    "parse_eng_text",
]
