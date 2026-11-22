"""TDD tests for Hefesto OpenMotor (.ric) validator, isolated runtime guard, and runner."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import matplotlib
import pytest

from hefesto.adapters.openmotor import (
    OpenMotorAlert,
    OpenMotorSimulationError,
    OpenMotorSimulationResult,
    apply_overrides_to_props,
    extract_sim_alerts,
    isolated_uilib_guard,
    load_ric_props,
    normalize_overrides,
    run_openmotor_ric,
    simulate_ric_detailed,
    validate_override,
    validate_ric_dict,
)
from hefesto.domain import (
    BallisticsResult,
    GrainInhibition,
    GrainSpec,
    MotorCasingSpec,
    MotorOverride,
)
from hefesto.physics.safety import evaluate_motor_safety

REPO_ROOT = Path(__file__).resolve().parents[2]
MOTORS_DIR = REPO_ROOT / "data" / "assets" / "motors"
GOLDEN_PATH = REPO_ROOT / "tests" / "golden" / "hefesto_baseline.json"


def _medusa_casing() -> MotorCasingSpec:
    return MotorCasingSpec(
        inner_radius_m=0.05395,
        wall_thickness_m=0.003175,
        length_m=1.10,
        internal_clearance_m=0.04,
        yield_strength_pa=145_000_000.0,
        dry_mass_kg=7.5,
        dry_inertia_kg_m2=(0.7678260027343752, 0.7678260027343752, 0.023152005468749997),
        center_of_dry_mass_m=0.55,
    )


def _sample_ric_dict() -> dict[str, object]:
    return {
        "config": {
            "ambPressure": 101325.0,
            "burnoutThrustThres": 0.1,
            "burnoutWebThres": 2.54e-5,
            "flowSeparationWarnPercent": 0.05,
            "mapDim": 1000,
            "maxMachNumber": 0.7,
            "maxMassFlux": 1406.4697609,
            "maxPressure": 8_000_000.0,
            "minPortThroat": 2.0,
            "sepPressureRatio": 0.4,
            "timestep": 0.03,
        },
        "grains": [
            {
                "type": "BATES",
                "properties": {
                    "diameter": 0.09869,
                    "length": 0.16,
                    "coreDiameter": 0.039,
                    "inhibitedEnds": "Neither",
                },
            },
            {
                "type": "BATES",
                "properties": {
                    "diameter": 0.09869,
                    "length": 0.16,
                    "coreDiameter": 0.054,
                    "inhibitedEnds": "Neither",
                },
            },
        ],
        "nozzle": {
            "throat": 0.034,
            "exit": 0.078,
            "efficiency": 0.85,
            "divAngle": 15.0,
            "convAngle": 45.0,
            "throatLength": 0.005,
            "slagCoeff": 0.0,
            "erosionCoeff": 0.0,
        },
        "propellant": {
            "name": "Nakka - KNSB (2)",
            "density": 1841.0,
            "tabs": [
                {
                    "minPressure": 1503110.0,
                    "maxPressure": 3792250.0,
                    "a": 0.00952812118,
                    "n": -0.0145,
                    "k": 1.1361,
                    "t": 1520.0,
                    "m": 39.9,
                }
            ],
        },
    }


def test_run_openmotor_ric_matches_all_golden_baselines() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    baselines = golden["openmotor_baselines"]

    for motor_key, expected in baselines.items():
        ric_path = MOTORS_DIR / expected["motor_asset"]
        result = run_openmotor_ric(ric_path, motor_name=motor_key)
        assert isinstance(result, BallisticsResult)
        assert result.motor_name == motor_key
        assert len(result.grains) == expected["grain_count"]
        assert all(isinstance(g, GrainSpec) for g in result.grains)

        if "grain_lengths_m" in expected:
            assert [g.length_m for g in result.grains] == pytest.approx(expected["grain_lengths_m"])
            assert [g.outer_radius_m for g in result.grains] == pytest.approx(
                expected["grain_outer_radii_m"]
            )
            assert [g.inner_radius_m for g in result.grains] == pytest.approx(
                expected["grain_inner_radii_m"]
            )
            assert result.propellant_density_kg_m3 == pytest.approx(
                expected["propellant_density_kg_m3"]
            )
            assert result.throat_radius_m == pytest.approx(expected["throat_radius_m"])
            assert result.nozzle_exit_radius_m == pytest.approx(expected["nozzle_exit_radius_m"])
            assert result.aft_port_to_throat_ratio == pytest.approx(
                expected["aft_port_to_throat_ratio"], rel=1e-12
            )
            assert result.min_port_to_throat_ratio == pytest.approx(
                expected["min_port_to_throat_ratio"], rel=1e-12
            )

        assert result.burn_time_s == pytest.approx(tuple(expected["burn_time_s"]), rel=1e-12)
        assert result.total_impulse_ns == pytest.approx(expected["total_impulse_ns"], rel=1e-12)
        assert result.max_thrust_n == pytest.approx(expected["max_thrust_n"], rel=1e-12)
        assert result.propellant_mass_kg == pytest.approx(expected["propellant_mass_kg"], rel=1e-12)
        assert result.peak_chamber_pressure_pa == pytest.approx(
            expected["peak_chamber_pressure_pa"], rel=1e-12
        )
        assert result.peak_kn == pytest.approx(expected["peak_kn"], rel=1e-12)
        assert result.peak_mass_flux_kg_m2_s == pytest.approx(
            expected["peak_mass_flux_kg_m2_s"], rel=1e-12
        )
        assert result.delivered_isp_s == pytest.approx(expected["delivered_isp_s"], rel=1e-12)

        assert len(result.thrust_curve) > 10
        assert len(result.pressure_curve) == len(result.thrust_curve)
        assert len(result.kn_curve) == len(result.thrust_curve)
        assert [t for t, _ in result.pressure_curve] == pytest.approx(
            [t for t, _ in result.thrust_curve]
        )
        assert [t for t, _ in result.kn_curve] == pytest.approx([t for t, _ in result.thrust_curve])
        assert max(p for _, p in result.pressure_curve) == pytest.approx(
            result.peak_chamber_pressure_pa
        )
        assert max(k for _, k in result.kn_curve) == pytest.approx(result.peak_kn)

        # BallisticsResult must support Pydantic JSON roundtrip cleanly.
        assert BallisticsResult.model_validate_json(result.model_dump_json()) == result

    # Safety integration check on Medusa KNSB A baseline.
    medusa = run_openmotor_ric(MOTORS_DIR / "medusa_knsb_a.ric", motor_name="Medusa KNSB A")
    safety = evaluate_motor_safety(medusa, _medusa_casing())
    assert safety.all_passed is True


def test_run_openmotor_ric_applies_overrides_and_changes_ballistics() -> None:
    ric_path = MOTORS_DIR / "medusa_knsb_a.ric"
    base = run_openmotor_ric(ric_path, motor_name="base")

    widened = run_openmotor_ric(
        ric_path,
        overrides=(MotorOverride(path="nozzle.throat", value=0.036),),
        motor_name="widened_throat",
    )
    assert widened.throat_radius_m == pytest.approx(0.018)
    assert widened.peak_chamber_pressure_pa < base.peak_chamber_pressure_pa
    assert widened.peak_kn < base.peak_kn

    inhibited = run_openmotor_ric(
        ric_path,
        overrides=(
            MotorOverride(path="grains.0.properties.inhibitedEnds", value="Neither"),
            MotorOverride(path="grains.*.properties.inhibitedEnds", value="Both"),
        ),
        motor_name="inhibited_ends",
    )
    assert inhibited.grains[0].inhibited_ends == GrainInhibition.NEITHER
    assert inhibited.grains[1].inhibited_ends == GrainInhibition.BOTH
    assert inhibited.peak_chamber_pressure_pa > base.peak_chamber_pressure_pa


def test_validator_enforces_whitelist_ranges_enums_and_wildcard_precedence() -> None:
    base_props = _sample_ric_dict()
    snapshot = copy.deepcopy(base_props)

    # Index override placed BEFORE wildcard must still win because wildcards apply first.
    overrides = (
        MotorOverride(path="grains.0.properties.coreDiameter", value=0.045),
        MotorOverride(path="grains.*.properties.coreDiameter", value=0.041),
        MotorOverride(path="grains.*.properties.length", value=0.15),
        MotorOverride(path="config.mapDim", value=500),
    )
    updated = apply_overrides_to_props(base_props, overrides)

    # Original props must remain completely unmutated (deepcopy invariant).
    assert base_props == snapshot

    updated_grains = updated["grains"]
    updated_config = updated["config"]
    assert isinstance(updated_grains, list)
    assert isinstance(updated_config, dict)
    assert updated_grains[0]["properties"]["coreDiameter"] == pytest.approx(0.045)
    assert updated_grains[1]["properties"]["coreDiameter"] == pytest.approx(0.041)
    assert updated_grains[0]["properties"]["length"] == pytest.approx(0.15)
    assert updated_grains[1]["properties"]["length"] == pytest.approx(0.15)
    assert updated_config["mapDim"] == 500
    assert type(updated_config["mapDim"]) is int

    # Wildcard ordering helper check
    ordered = normalize_overrides(overrides)
    assert ordered[0].path == "grains.*.properties.coreDiameter"
    assert ordered[-1].path == "grains.0.properties.coreDiameter"

    # Standalone validate_override accepts valid paths & rejects unknown keys / silent bounds.
    assert validate_override(MotorOverride(path="nozzle.throat", value=0.034)) == pytest.approx(
        0.034
    )

    bad_overrides = [
        MotorOverride(path="nozzle.throatt", value=0.034),
        MotorOverride(path="nozzle.throatDiameter", value=0.034),
        MotorOverride(path="grains.0.properties.core_diameter", value=0.04),
        MotorOverride(path="config.igniterPressure", value=1000.0),
        MotorOverride(path="grains.0.type", value="Finocyl"),
        MotorOverride(path="nozzle..throat", value=0.034),
        MotorOverride(path="unknown.field", value=1.0),
        MotorOverride(path="nozzle.throat", value=99.0),
        MotorOverride(path="nozzle.throat", value=-0.01),
        MotorOverride(path="config.timestep", value=0.5),
        MotorOverride(path="config.timestep", value=1e-5),
        MotorOverride(path="config.ambPressure", value=200_000.0),
        MotorOverride(path="config.burnoutWebThres", value=0.01),
        MotorOverride(path="config.mapDim", value=100),
        MotorOverride(path="config.mapDim", value=1000.5),
        MotorOverride(path="config.mapDim", value=True),
        MotorOverride(path="propellant.tabs.0.k", value=1.0),
        MotorOverride(path="propellant.tabs.0.n", value=1.2),
        MotorOverride(path="grains.0.properties.inhibitedEnds", value="All"),
        MotorOverride(path="grains.0.properties.inhibitedEnds", value="neither"),
        MotorOverride(path="grains.99.properties.length", value=0.16),
        MotorOverride(path="propellant.tabs.5.a", value=0.01),
        MotorOverride(path="propellant.name", value="   "),
    ]
    for bad in bad_overrides:
        with pytest.raises(ValueError):
            apply_overrides_to_props(base_props, (bad,))

    with pytest.raises(ValueError):
        apply_overrides_to_props(base_props, {"nozzle.throat": float("nan")})

    nan_props = copy.deepcopy(base_props)
    nan_nozzle = nan_props["nozzle"]
    assert isinstance(nan_nozzle, dict)
    nan_nozzle["throat"] = float("nan")
    with pytest.raises(ValueError, match="finite float"):
        validate_ric_dict(nan_props)

    # Tab minPressure >= maxPressure after override must be rejected.
    with pytest.raises(ValueError, match="minPressure"):
        apply_overrides_to_props(
            base_props, (MotorOverride(path="propellant.tabs.0.minPressure", value=4_000_000.0),)
        )

    # End Burner validation: allowed only at index 0 and has no inhibitedEnds.
    end_burner_props = copy.deepcopy(base_props)
    base_grains = base_props["grains"]
    assert isinstance(base_grains, list)
    end_burner_props["grains"] = [
        {"type": "End Burner", "properties": {"diameter": 0.098, "length": 0.16}},
        copy.deepcopy(base_grains[0]),
    ]
    validate_ric_dict(end_burner_props)
    with pytest.raises(ValueError, match="inhibitedEnds"):
        apply_overrides_to_props(
            end_burner_props,
            (MotorOverride(path="grains.*.properties.inhibitedEnds", value="Both"),),
        )

    bad_end_burner = copy.deepcopy(base_props)
    bad_grains = bad_end_burner["grains"]
    assert isinstance(bad_grains, list)
    bad_grains[1] = {
        "type": "End Burner",
        "properties": {"diameter": 0.098, "length": 0.16},
    }
    with pytest.raises(ValueError, match="index 0"):
        validate_ric_dict(bad_end_burner)


def test_runner_deepcopies_props_passed_to_motor_constructor() -> None:
    ric_path = MOTORS_DIR / "medusa_knsb_a.ric"
    loaded_before = load_ric_props(ric_path)
    loaded_nozzle = loaded_before["nozzle"]
    assert isinstance(loaded_nozzle, dict)
    expected_throat = float(loaded_nozzle["throat"])  # type: ignore[arg-type]

    # Simulate motorlib mutating the dictionary passed into Motor(props).
    from motorlib.motor import Motor as RealMotor

    captured_caller_dict = copy.deepcopy(loaded_before)
    seen_inside_motor: list[float] = []

    class MutatingMotorSpy:
        def __init__(self, prop_dict: dict[str, object]) -> None:
            self._inner = RealMotor(copy.deepcopy(prop_dict))
            # Mutate the incoming dictionary aggressively like motorlib internals could.
            nozzle = prop_dict["nozzle"]
            assert isinstance(nozzle, dict)
            seen_inside_motor.append(float(nozzle["throat"]))
            nozzle["throat"] = 999.0
            prop_dict["grains"] = []

        def runSimulation(self):
            return self._inner.runSimulation()

    with patch("hefesto.adapters.openmotor.runner._load_openmotor_runtime") as mock_rt:
        from motorlib.simResult import SimAlertLevel
        from uilib.fileIO import fileTypes

        mock_rt.return_value = SimpleNamespace(
            motor_cls=MutatingMotorSpy,
            load_file=lambda _path, _ftype: captured_caller_dict,
            motor_file_type=fileTypes.MOTOR,
            error_level=SimAlertLevel.ERROR,
            warning_level=SimAlertLevel.WARNING,
            message_level=SimAlertLevel.MESSAGE,
        )
        result = run_openmotor_ric(ric_path, motor_name="spy")

    captured_nozzle = captured_caller_dict["nozzle"]
    captured_grains = captured_caller_dict["grains"]
    assert isinstance(captured_nozzle, dict)
    assert isinstance(captured_grains, list)
    assert seen_inside_motor == [expected_throat]
    assert captured_nozzle["throat"] == expected_throat
    assert len(captured_grains) == 6
    assert result.throat_radius_m == pytest.approx(expected_throat / 2.0)


def test_alerts_extracted_via_description_and_post_integration_errors_raise() -> None:
    ric_path = MOTORS_DIR / "medusa_knsb_a.ric"

    # 1) Pre-integration ERROR (sim.success=False): nozzle.throat = 0 -> .description surfaced.
    with pytest.raises(OpenMotorSimulationError, match="Throat diameter must not be 0"):
        run_openmotor_ric(ric_path, overrides=(MotorOverride(path="nozzle.throat", value=0.0),))

    # 2) Post-integration WARNING (non-blocking): maxPressure lowered below peak pressure.
    detailed = simulate_ric_detailed(
        ric_path,
        overrides=(MotorOverride(path="config.maxPressure", value=1_000_000.0),),
        motor_name="warning_case",
    )
    assert isinstance(detailed, OpenMotorSimulationResult)
    assert detailed.ballistics.peak_chamber_pressure_pa > 1_000_000.0
    assert any("Max pressure exceeded configured limit" in w.description for w in detailed.warnings)

    # 3) Post-integration ERROR where motorlib leaves sim.success=True!
    #    Also tests alert.description extraction (no .message attribute) & getISP() failure -> None.
    fake_error_alert = SimpleNamespace(
        level=SimpleNamespace(name="ERROR", value=1),
        type=SimpleNamespace(name="VALUE", value=3),
        description=(
            "Motor did not generate thrust. Check Kn, chamber pressure and expansion ratio."
        ),
        location="Motor",
    )
    fake_sim_with_error = SimpleNamespace(success=True, alerts=[fake_error_alert])
    extracted = extract_sim_alerts(fake_sim_with_error)
    assert extracted == (
        OpenMotorAlert(
            level="error",
            category="value",
            description=(
                "Motor did not generate thrust. Check Kn, chamber pressure and expansion ratio."
            ),
            location="Motor",
        ),
    )

    class PostErrorMotor:
        def __init__(self, _props: dict[str, object]) -> None:
            pass

        def runSimulation(self):
            return fake_sim_with_error

    with patch("hefesto.adapters.openmotor.runner._load_openmotor_runtime") as mock_rt:
        from motorlib.simResult import SimAlertLevel
        from uilib.fileIO import fileTypes

        mock_rt.return_value = SimpleNamespace(
            motor_cls=PostErrorMotor,
            load_file=lambda _path, _ftype: _sample_ric_dict(),
            motor_file_type=fileTypes.MOTOR,
            error_level=SimAlertLevel.ERROR,
            warning_level=SimAlertLevel.WARNING,
            message_level=SimAlertLevel.MESSAGE,
        )
        with pytest.raises(OpenMotorSimulationError, match="Motor did not generate thrust"):
            run_openmotor_ric(ric_path, motor_name="post_error")

    # 4) sim.getISP() raising ZeroDivisionError maps to delivered_isp_s=None (no NaN in Pydantic).
    from motorlib.motor import Motor as RealMotor

    class BrokenIspMotor:
        def __init__(self, props: dict[str, object]) -> None:
            self._inner = RealMotor(props)

        def runSimulation(self):
            sim = self._inner.runSimulation()

            def _boom():
                raise ZeroDivisionError("zero propellant mass")

            sim.getISP = _boom
            return sim

    with patch("hefesto.adapters.openmotor.runner._load_openmotor_runtime") as mock_rt:
        from motorlib.simResult import SimAlertLevel
        from uilib.fileIO import fileTypes

        mock_rt.return_value = SimpleNamespace(
            motor_cls=BrokenIspMotor,
            load_file=lambda _path, _ftype: _sample_ric_dict(),
            motor_file_type=fileTypes.MOTOR,
            error_level=SimAlertLevel.ERROR,
            warning_level=SimAlertLevel.WARNING,
            message_level=SimAlertLevel.MESSAGE,
        )
        no_isp_res = run_openmotor_ric(ric_path, motor_name="broken_isp")
    assert no_isp_res.delivered_isp_s is None


def test_qt_mpl_excepthook_and_uilib_logger_isolation_guard(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    orig_use = matplotlib.use
    orig_hook = sys.excepthook
    used_backends: list[object] = []

    def fake_use(backend=None, *args, **kwargs):
        used_backends.append(backend)

    def custom_hook(exctype, value, tb):
        return None

    matplotlib.use = fake_use  # type: ignore[assignment]
    sys.excepthook = custom_hook
    try:
        with pytest.raises(RuntimeError, match="boom"):
            with isolated_uilib_guard():
                # Qt backends must be blocked silently while non-Qt backends pass through.
                matplotlib.use("Qt5Agg")
                matplotlib.use("QtAgg")
                matplotlib.use("Agg")
                sys.excepthook = lambda *_args: None
                raise RuntimeError("boom")

        assert used_backends == ["Agg"]
        assert matplotlib.use is fake_use
        assert sys.excepthook is custom_hook
    finally:
        matplotlib.use = orig_use
        sys.excepthook = orig_hook

    # Real runtime load and .ric read must preserve the active backend and emit no logs.
    backend_before = matplotlib.get_backend()
    load_ric_props(MOTORS_DIR / "medusa_knsb_a.ric")
    captured = capsys.readouterr()
    assert "[LOG]" not in captured.out
    assert "[LOG]" not in captured.err
    assert matplotlib.get_backend() == backend_before
    assert matplotlib.use is orig_use
    assert sys.excepthook is orig_hook

    import uilib.logger as uilib_logger

    assert uilib_logger.logger._file is None

    # Fresh headless subprocess verification: Agg backend stays Agg and no openMotor.log is created.
    env = {
        key: val
        for key, val in os.environ.items()
        if key not in {"DISPLAY", "WAYLAND_DISPLAY"}
    }
    env["XDG_STATE_HOME"] = str(tmp_path)
    env["XDG_DATA_HOME"] = str(tmp_path)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import matplotlib, sys; "
                "hook = sys.excepthook; "
                "from hefesto.adapters.openmotor import load_ric_props; "
                f"load_ric_props({str(MOTORS_DIR / 'medusa_knsb_a.ric')!r}); "
                "assert matplotlib.get_backend().lower() == 'agg'; "
                "assert sys.excepthook is hook"
            ),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "[LOG]" not in proc.stdout
    assert "[LOG]" not in proc.stderr
    assert list(tmp_path.rglob("openMotor.log")) == []

    with pytest.raises(FileNotFoundError):
        run_openmotor_ric(MOTORS_DIR / "does_not_exist.ric")
