"""Isolated OpenMotor (motorlib/uilib) simulation runner with Qt/Matplotlib guards."""

from __future__ import annotations

import contextlib
import copy
import importlib
import io
import logging
import math
import sys
import types
import warnings
from collections.abc import Generator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import matplotlib
import numpy as np

from hefesto.adapters.openmotor.validator import (
    OverrideInput,
    apply_overrides_to_props,
    extract_grains_from_props,
)
from hefesto.domain import BallisticsResult, GrainSpec

AlertLevelLiteral = Literal["error", "warning", "message"]


@dataclass(frozen=True)
class OpenMotorAlert:
    """Structured simulation alert normalized from motorlib SimAlert.description."""

    level: AlertLevelLiteral
    category: str
    description: str
    location: str | None = None


class OpenMotorSimulationError(RuntimeError):
    """Raised when motorlib fails or emits a blocking ERROR alert."""

    def __init__(self, message: str, alerts: tuple[OpenMotorAlert, ...] = ()) -> None:
        super().__init__(message)
        self.alerts = alerts


@dataclass(frozen=True)
class OpenMotorSimulationResult:
    """Full OpenMotor execution bundle with domain BallisticsResult and non-blocking alerts."""

    ballistics: BallisticsResult
    alerts: tuple[OpenMotorAlert, ...]

    @property
    def warnings(self) -> tuple[OpenMotorAlert, ...]:
        return tuple(alert for alert in self.alerts if alert.level == "warning")


@dataclass(frozen=True)
class _OpenMotorRuntime:
    motor_cls: Any
    load_file: Any
    motor_file_type: Any
    error_level: Any
    warning_level: Any
    message_level: Any


_RUNTIME_CACHE: list[_OpenMotorRuntime] = []


@contextlib.contextmanager
def isolated_uilib_guard() -> Generator[None]:
    """Isolate uilib/PyQt6 side effects: block Qt backends, suppress logs, restore hooks."""
    orig_use = matplotlib.use
    orig_excepthook = sys.excepthook
    uilib_logger = logging.getLogger("uilib")
    orig_log_level = uilib_logger.level

    def _non_qt_use(backend: Any = None, *args: Any, **kwargs: Any) -> Any:
        if backend is not None and "qt" in str(backend).lower():
            return None
        return orig_use(backend, *args, **kwargs)

    matplotlib.use = _non_qt_use
    uilib_logger.setLevel(logging.ERROR)

    try:
        with (
            warnings.catch_warnings(),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            warnings.simplefilter("ignore", RuntimeWarning)
            yield
    finally:
        matplotlib.use = orig_use
        sys.excepthook = orig_excepthook
        uilib_logger.setLevel(orig_log_level)


class _SilentUilibLogger:
    def __init__(self) -> None:
        self.buffer: list[str] = []
        self._file: None = None

    def log(self, _message: object) -> None:
        return None

    def warn(self, _message: object) -> None:
        return None

    def error(self, _message: object) -> None:
        return None

    def _write(self, _level: object, _content: object) -> None:
        return None


def _silence_uilib_file_logger(uilib_logger_mod: Any) -> None:
    logger_obj = getattr(uilib_logger_mod, "logger", None)
    if logger_obj is None:
        return
    log_file = getattr(logger_obj, "_file", None)
    if log_file is not None:
        with contextlib.suppress(OSError):
            log_file.close()
        logger_obj._file = None
    logger_obj._write = lambda _level, _content: None


class _SilentUilibLoggerModule(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("uilib.logger")
        self.Logger = _SilentUilibLogger
        self.logger = _SilentUilibLogger()
        self.exceptHook = sys.excepthook


def _ensure_silent_uilib_logger() -> None:
    if "uilib.logger" in sys.modules:
        _silence_uilib_file_logger(sys.modules["uilib.logger"])
        return
    # Pre-register a silent logger before uilib.fileIO loads uilib.logger
    # so openMotor.log is never created or written on disk.
    importlib.import_module("uilib")
    sys.modules["uilib.logger"] = _SilentUilibLoggerModule()


def _load_openmotor_runtime() -> _OpenMotorRuntime:
    if _RUNTIME_CACHE:
        return _RUNTIME_CACHE[0]

    with isolated_uilib_guard():
        _ensure_silent_uilib_logger()
        from motorlib.motor import Motor
        from motorlib.simResult import SimAlertLevel
        from uilib.fileIO import fileTypes, loadFile

    runtime = _OpenMotorRuntime(
        motor_cls=Motor,
        load_file=loadFile,
        motor_file_type=fileTypes.MOTOR,
        error_level=SimAlertLevel.ERROR,
        warning_level=SimAlertLevel.WARNING,
        message_level=SimAlertLevel.MESSAGE,
    )
    _RUNTIME_CACHE.append(runtime)
    return runtime


def _normalize_alert_level(raw_level: Any) -> AlertLevelLiteral:
    name = getattr(raw_level, "name", None)
    if isinstance(name, str):
        lowered = name.lower()
        if lowered in {"error", "warning", "message"}:
            return lowered  # type: ignore[return-value]
    if raw_level == 1:
        return "error"
    if raw_level == 2:
        return "warning"
    return "message"


def _normalize_alert_category(raw_type: Any) -> str:
    name = getattr(raw_type, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip().lower()
    return str(raw_type).strip().lower() or "unknown"


def extract_sim_alerts(sim_result: object) -> tuple[OpenMotorAlert, ...]:
    """Extract alerts from motorlib SimulationResult using SimAlert.description."""
    raw_alerts = getattr(sim_result, "alerts", ()) or ()
    extracted: list[OpenMotorAlert] = []
    for alert in raw_alerts:
        # motorlib SimAlert stores text in .description (there is no .message attribute).
        raw_desc = getattr(alert, "description", None)
        description = (
            raw_desc.strip() if isinstance(raw_desc, str) and raw_desc.strip() else str(alert)
        )
        location_raw = getattr(alert, "location", None)
        location = str(location_raw) if location_raw is not None else None
        extracted.append(
            OpenMotorAlert(
                level=_normalize_alert_level(getattr(alert, "level", None)),
                category=_normalize_alert_category(getattr(alert, "type", "unknown")),
                description=description,
                location=location,
            )
        )
    return tuple(extracted)


def _peak_channel_2d(data: Sequence[Any]) -> float:
    if not data:
        return 0.0
    first = data[0]
    if isinstance(first, (list, tuple)):
        return max(float(val) for row in data for val in row)
    return max(float(val) for val in data)


def load_ric_props(
    ric_path: Path | str,
    overrides: OverrideInput = (),
) -> dict[str, object]:
    """Load a .ric file via isolated uilib.fileIO, validate whitelist, and apply overrides."""
    path = Path(ric_path)
    if not path.is_file():
        raise FileNotFoundError(f"OpenMotor .ric file not found: {path}")

    runtime = _load_openmotor_runtime()
    with (
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        raw_props = runtime.load_file(str(path), runtime.motor_file_type)

    if not isinstance(raw_props, dict):
        raise ValueError(f"Loaded .ric payload from {path} is not a dict")
    return apply_overrides_to_props(raw_props, overrides)


def _compute_fallback_inner_radii(
    motor_obj: Any,
    props: dict[str, object],
) -> tuple[float, ...]:
    motor_grains = getattr(motor_obj, "grains", ()) or ()
    raw_grains = props.get("grains")
    if not isinstance(raw_grains, list) or len(motor_grains) != len(raw_grains):
        return ()

    radii: list[float] = []
    for raw_grain, sim_grain in zip(raw_grains, motor_grains, strict=True):
        diameter = 0.0
        if isinstance(raw_grain, dict) and isinstance(raw_grain.get("properties"), dict):
            diameter = float(raw_grain["properties"].get("diameter", 0.0))
        outer_r = diameter / 2.0
        port_area = None
        get_port_area = getattr(sim_grain, "getPortArea", None)
        if callable(get_port_area):
            with contextlib.suppress(Exception):
                port_area = get_port_area(0)
        if port_area is not None and float(port_area) > 0.0:
            eq_r = math.sqrt(float(port_area) / math.pi)
            if outer_r > 0.0 and eq_r >= outer_r:
                eq_r = max(0.0, outer_r * (1.0 - 1e-9))
            radii.append(eq_r)
        else:
            radii.append(0.0)
    return tuple(radii)


def _compute_port_to_throat_ratios(
    grains: Sequence[GrainSpec],
    motor_obj: Any,
    props: dict[str, object],
    throat_radius_m: float,
) -> tuple[float | None, float | None]:
    raw_grains = props.get("grains")
    motor_grains = getattr(motor_obj, "grains", ()) or ()
    throat_area = math.pi * (throat_radius_m**2)
    ratios: list[float | None] = []

    for idx, grain in enumerate(grains):
        grain_type = ""
        if isinstance(raw_grains, list) and idx < len(raw_grains):
            entry = raw_grains[idx]
            if isinstance(entry, dict):
                grain_type = str(entry.get("type", ""))

        if grain_type == "BATES" and grain.inner_radius_m > 0.0:
            ratios.append((grain.inner_radius_m / throat_radius_m) ** 2)
            continue

        ratio: float | None = None
        if idx < len(motor_grains):
            get_port_area = getattr(motor_grains[idx], "getPortArea", None)
            if callable(get_port_area):
                port_area = get_port_area(0)
                if port_area is not None and float(port_area) > 0.0 and throat_area > 0.0:
                    ratio = float(port_area) / throat_area
        ratios.append(ratio)

    aft_ratio = ratios[-1] if ratios else None
    valid_ratios = [r for r in ratios if r is not None]
    min_ratio = min(valid_ratios) if valid_ratios else None
    return aft_ratio, min_ratio


def simulate_ric_detailed(
    ric_path: Path | str,
    overrides: OverrideInput = (),
    *,
    motor_name: str | None = None,
) -> OpenMotorSimulationResult:
    """Run an OpenMotor .ric simulation and return BallisticsResult plus non-blocking alerts."""
    path = Path(ric_path)
    props = load_ric_props(path, overrides)
    runtime = _load_openmotor_runtime()

    # Pass a fresh deepcopy because Motor(props) mutates/consumes the incoming dict.
    motor_props = copy.deepcopy(props)
    with (
        warnings.catch_warnings(),
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        warnings.simplefilter("ignore", RuntimeWarning)
        motor_obj = runtime.motor_cls(motor_props)
        sim = motor_obj.runSimulation()

    alerts = extract_sim_alerts(sim)
    error_alerts = tuple(alert for alert in alerts if alert.level == "error")
    # motorlib sets sim.success=True before final checks, so also reject ERROR alerts.
    if not bool(getattr(sim, "success", False)) or error_alerts:
        selected = error_alerts or alerts
        details = "; ".join(
            f"{a.location}: {a.description}" if a.location else a.description for a in selected
        ) or "Unknown OpenMotor simulation failure"
        raise OpenMotorSimulationError(
            f"OpenMotor simulation failed for '{motor_name or path.stem}': {details}",
            alerts=alerts,
        )

    channels = sim.channels
    time_data = [float(v) for v in channels["time"].getData()]
    force_data = [max(0.0, float(v)) for v in channels["force"].getData()]
    pressure_data = [float(v) for v in channels["pressure"].getData()]
    kn_data = [float(v) for v in channels["kn"].getData()]

    mass_t0 = channels["mass"].getData()[0]
    propellant_mass_kg = (
        float(sum(mass_t0)) if isinstance(mass_t0, (list, tuple)) else float(mass_t0)
    )
    peak_mass_flux = _peak_channel_2d(channels["massFlux"].getData())

    try:
        raw_isp = float(sim.getISP())
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        delivered_isp_s = None
    else:
        delivered_isp_s = raw_isp if math.isfinite(raw_isp) and raw_isp >= 0.0 else None

    fallback_radii = _compute_fallback_inner_radii(motor_obj, props)
    grains = extract_grains_from_props(props, fallback_inner_radii_m=fallback_radii)

    propellant_map = props["propellant"]
    nozzle_map = props["nozzle"]
    assert isinstance(propellant_map, dict)
    assert isinstance(nozzle_map, dict)

    propellant_density = float(propellant_map["density"])
    throat_radius_m = float(nozzle_map["throat"]) / 2.0
    nozzle_exit_radius_m = float(nozzle_map["exit"]) / 2.0
    aft_ratio, min_ratio = _compute_port_to_throat_ratios(
        grains, motor_obj, props, throat_radius_m
    )

    thrust_curve = tuple(zip(time_data, force_data, strict=True))
    pressure_curve = tuple(zip(time_data, pressure_data, strict=True))
    kn_curve = tuple(zip(time_data, kn_data, strict=True))

    ballistics = BallisticsResult(
        motor_name=motor_name or path.stem,
        grains=grains,
        propellant_density_kg_m3=propellant_density,
        throat_radius_m=throat_radius_m,
        nozzle_exit_radius_m=nozzle_exit_radius_m,
        burn_time_s=(time_data[0], time_data[-1]),
        total_impulse_ns=float(np.trapezoid(force_data, time_data)),
        max_thrust_n=max(force_data),
        propellant_mass_kg=propellant_mass_kg,
        peak_chamber_pressure_pa=max(pressure_data),
        peak_kn=max(kn_data),
        peak_mass_flux_kg_m2_s=peak_mass_flux,
        delivered_isp_s=delivered_isp_s,
        aft_port_to_throat_ratio=aft_ratio,
        min_port_to_throat_ratio=min_ratio,
        thrust_curve=thrust_curve,
        pressure_curve=pressure_curve,
        kn_curve=kn_curve,
    )
    return OpenMotorSimulationResult(ballistics=ballistics, alerts=alerts)


def run_openmotor_ric(
    ric_path: Path | str,
    overrides: OverrideInput = (),
    *,
    motor_name: str | None = None,
) -> BallisticsResult:
    """Load, validate, and run an OpenMotor .ric simulation, returning BallisticsResult."""
    return simulate_ric_detailed(ric_path, overrides, motor_name=motor_name).ballistics


__all__ = [
    "AlertLevelLiteral",
    "OpenMotorAlert",
    "OpenMotorSimulationError",
    "OpenMotorSimulationResult",
    "extract_sim_alerts",
    "isolated_uilib_guard",
    "load_ric_props",
    "run_openmotor_ric",
    "simulate_ric_detailed",
]
