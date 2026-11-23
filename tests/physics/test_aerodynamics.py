"""Analytical drag build-up: physical invariants and calibration against the .ork oracle."""

from __future__ import annotations

from pathlib import Path

import pytest

from hefesto.adapters import parse_ork_file
from hefesto.domain import (
    DragCurveTable,
    FinComponent,
    FinSetSpec,
    NoseConeKind,
    SurfaceFinish,
)
from hefesto.physics import (
    DEFAULT_MACH_GRID,
    base_area_m2,
    base_drag_coefficient,
    compute_analytical_drag_curves,
    plume_area_fraction,
    pressure_drag_cd,
    reference_area_m2,
    skin_friction_drag_cd,
    total_length_m,
)
from hefesto.services import load_rocket_spec

REPO_ROOT = Path(__file__).resolve().parents[2]
ORK_ASSET = REPO_ROOT / "data" / "assets" / "openrocket" / "hefesto_1.41.ork"
CALIBRATION_MACH = (0.1, 0.3, 0.5, 0.7, 0.9, 0.95)
CALIBRATION_TOLERANCE = 0.04
GRID_STEP = 0.025


def _interpolate(mach: float, mach_axis: list[float], values: list[float]) -> float:
    """Linear interpolation with constant extrapolation, mirroring the RocketPy Function."""
    if mach <= mach_axis[0]:
        return values[0]
    for index in range(1, len(mach_axis)):
        if mach <= mach_axis[index]:
            span = mach_axis[index] - mach_axis[index - 1]
            if span <= 0.0:
                return values[index]
            weight = (mach - mach_axis[index - 1]) / span
            return values[index - 1] + weight * (values[index] - values[index - 1])
    return values[-1]


def _total_cd(rocket, mach: float, *, powered: bool) -> float:
    table = compute_analytical_drag_curves(rocket)
    values = table.cd_power_on if powered else table.cd_power_off
    return _interpolate(mach, table.mach, values)


@pytest.fixture(scope="module")
def hefesto_rocket():
    return load_rocket_spec("hefesto_1.4")


@pytest.fixture(scope="module")
def curves(hefesto_rocket):
    return compute_analytical_drag_curves(hefesto_rocket)


@pytest.fixture(scope="module")
def ork_table():
    parsed = parse_ork_file(ORK_ASSET)
    assert parsed.drag_table is not None
    return parsed.drag_table


def test_reference_geometry_matches_openrocket_airframe(hefesto_rocket) -> None:
    assert total_length_m(hefesto_rocket) == pytest.approx(0.45 + 2.195, rel=1e-12)
    assert reference_area_m2(hefesto_rocket) == pytest.approx(3.141592653589793 * 0.079**2)
    # Base area adds the four fin trailing edges on top of the airframe base.
    fin_base = 4 * 0.004 * 0.14
    assert base_area_m2(hefesto_rocket) == pytest.approx(
        reference_area_m2(hefesto_rocket) + fin_base, rel=1e-12
    )


def test_analytical_curves_cover_the_default_mach_envelope(curves: DragCurveTable) -> None:
    assert curves.source == "analytical"
    assert tuple(curves.mach) == DEFAULT_MACH_GRID
    assert curves.mach[0] == 0.0
    assert curves.mach[-1] == pytest.approx(3.0)
    assert len(curves.cd_power_off) == len(curves.mach)
    assert all(cd > 0.0 for cd in curves.cd_power_off + curves.cd_power_on)
    assert curves.to_specs()[0].points[0][0] == curves.mach[0]


def test_drag_is_monotonic_and_power_off_exceeds_power_on(curves: DragCurveTable) -> None:
    mach = list(curves.mach)
    off = list(curves.cd_power_off)
    on = list(curves.cd_power_on)
    for lower, upper in zip(CALIBRATION_MACH[:-1], CALIBRATION_MACH[1:], strict=True):
        assert _interpolate(upper, mach, off) > _interpolate(lower, mach, off)
    for idx, mach_value in enumerate(mach):
        assert off[idx] > on[idx], f"power_off must exceed power_on at Mach {mach_value}"


def test_power_on_relief_is_the_nozzle_plume_area(hefesto_rocket) -> None:
    plume = plume_area_fraction(hefesto_rocket)
    nozzle_area = 3.141592653589793 * hefesto_rocket.motor.nozzle.throat_radius_m**2
    assert plume == pytest.approx(nozzle_area / base_area_m2(hefesto_rocket), rel=1e-12)

    table = compute_analytical_drag_curves(hefesto_rocket)
    for mach in (0.1, 0.5, 0.9, 0.95):
        base_cd = base_drag_coefficient(hefesto_rocket, mach)
        off = _interpolate(mach, table.mach, table.cd_power_off)
        on = _interpolate(mach, table.mach, table.cd_power_on)
        assert off - on == pytest.approx(base_cd * plume, rel=1e-12)


def test_finish_roughness_monotonically_increases_skin_friction(hefesto_rocket) -> None:
    finishes = (
        SurfaceFinish.SMOOTH,
        SurfaceFinish.REGULAR,
        SurfaceFinish.ROUGH,
        SurfaceFinish.UNFINISHED,
    )
    for mach in (0.1, 0.3, 0.9):
        friction = [
            skin_friction_drag_cd(
                hefesto_rocket.model_copy(update={"surface_finish": finish}), mach
            )
            for finish in finishes
        ]
        assert friction == sorted(friction), f"friction must grow with roughness at M={mach}"
        assert len(set(friction)) == len(friction)
        total = [
            _total_cd(
                hefesto_rocket.model_copy(update={"surface_finish": finish}),
                mach,
                powered=False,
            )
            for finish in finishes
        ]
        assert total == sorted(total)


def test_larger_fins_and_blunter_nose_increase_drag(hefesto_rocket) -> None:
    scale = 1.25
    scaled_components = tuple(
        component.model_copy(
            update={
                "shape_points_m": tuple(
                    (x_m * scale, y_m * scale) for x_m, y_m in component.shape_points_m
                )
            }
        )
        if isinstance(component, FinComponent)
        else component
        for component in hefesto_rocket.components
    )
    scaled_fins = FinSetSpec(
        **hefesto_rocket.fins.model_dump(
            exclude={"shape_points_m"},
            mode="python",
        ),
        shape_points_m=tuple(
            (x_m * scale, y_m * scale) for x_m, y_m in hefesto_rocket.fins.shape_points_m
        ),
    )
    bigger = hefesto_rocket.model_copy(
        update={"components": scaled_components, "fins": scaled_fins}
    )
    assert _total_cd(bigger, 0.3, powered=False) > _total_cd(hefesto_rocket, 0.3, powered=False)

    conical = hefesto_rocket.model_copy(
        update={
            "nose_cone": hefesto_rocket.nose_cone.model_copy(
                update={"kind": NoseConeKind.CONICAL}
            )
        }
    )
    von_karman = hefesto_rocket.nose_cone.kind
    assert von_karman is NoseConeKind.VON_KARMAN
    assert pressure_drag_cd(conical, 0.3) > pressure_drag_cd(hefesto_rocket, 0.3)


@pytest.mark.parametrize("mach", CALIBRATION_MACH)
def test_analytical_curves_match_openrocket_datapoints(
    hefesto_rocket,
    curves: DragCurveTable,
    ork_table: DragCurveTable,
    mach: float,
) -> None:
    """Calibrate <= 4% against the 3.442 <datapoint> embedded in hefesto_1.41.ork."""
    ork_index = round(mach / 0.01)
    assert ork_table.mach[ork_index] == pytest.approx(mach, abs=1e-9)
    for powered, ork_values in (
        (False, ork_table.cd_power_off),
        (True, ork_table.cd_power_on),
    ):
        values = curves.cd_power_on if powered else curves.cd_power_off
        model = _interpolate(mach, curves.mach, values)
        oracle = ork_values[ork_index]
        relative_error = abs(model - oracle) / oracle
        assert relative_error <= CALIBRATION_TOLERANCE, (
            f"Mach {mach} power_on={powered}: model {model:.5f} vs ork {oracle:.5f} "
            f"({100 * relative_error:.2f}%)"
        )


def test_calibration_grid_step_is_fine_enough(curves: DragCurveTable) -> None:
    steps = [upper - lower for lower, upper in zip(curves.mach[:-1], curves.mach[1:], strict=True)]
    assert all(step == pytest.approx(GRID_STEP, rel=1e-9) for step in steps)
