"""TDD tests for Hefesto aerodynamic drag protocol and tabulated CSV drag model."""

from __future__ import annotations

from pathlib import Path

import pytest

from hefesto.adapters.aerodynamics import DatabaseDragModel, DragModelProtocol
from hefesto.domain import (
    DragCurveSpec,
    FinSetSpec,
    GrainSpec,
    MotorCasingSpec,
    MotorSpec,
    NoseConeSpec,
    NozzleSpec,
    PointMassComponent,
    RailButtonsSpec,
    RocketSpec,
)
from hefesto.storage import load_drag_curve

REPO_ROOT = Path(__file__).resolve().parents[2]
POWER_OFF_CSV = REPO_ROOT / "data" / "assets" / "drag" / "power_off.csv"
POWER_ON_CSV = REPO_ROOT / "data" / "assets" / "drag" / "power_on.csv"


def _load_real_drag_specs() -> tuple[DragCurveSpec, DragCurveSpec]:
    return (
        load_drag_curve(POWER_OFF_CSV, asset_name="power_off.csv"),
        load_drag_curve(POWER_ON_CSV, asset_name="power_on.csv"),
    )


def _sample_rocket(power_off: DragCurveSpec, power_on: DragCurveSpec) -> RocketSpec:
    return RocketSpec(
        name="Hefesto V1",
        radius_m=0.079,
        center_of_mass_without_motor_m=1.2333,
        inertia_kg_m2=(12.297744243637531, 12.297744243637531, 0.08243211389076663),
        motor_position_m=2.78,
        components=(PointMassComponent(name="Avionics", mass_kg=0.7, position_m=0.701),),
        nose_cone=NoseConeSpec(length_m=0.45, position_m=0.0),
        fins=FinSetSpec(
            name="Main Fins",
            count=4,
            position_m=2.57,
            shape_points_m=((0.0, 0.0), (0.07, 0.12), (0.21, 0.14), (0.18, 0.0)),
        ),
        rail_buttons=RailButtonsSpec(
            upper_button_position_m=1.39,
            lower_button_position_m=2.30,
        ),
        power_off_drag=power_off,
        power_on_drag=power_on,
        motor=MotorSpec(
            name="Medusa KNSB A",
            grains=(GrainSpec(length_m=0.16, outer_radius_m=0.049345, inner_radius_m=0.0195),),
            grain_separation_m=0.01,
            grains_center_of_mass_m=0.54,
            propellant_density_kg_m3=1841.0,
            nozzle=NozzleSpec(throat_radius_m=0.017, exit_radius_m=0.039),
            casing=MotorCasingSpec(
                inner_radius_m=0.05395,
                wall_thickness_m=0.003175,
                length_m=1.10,
                internal_clearance_m=0.04,
                yield_strength_pa=145_000_000.0,
                dry_mass_kg=7.5,
                dry_inertia_kg_m2=(0.76, 0.76, 0.023),
                center_of_dry_mass_m=0.55,
            ),
            burn_time_s=(0.0, 3.9),
            thrust_curve=((0.0, 0.0), (1.0, 3000.0), (3.9, 0.0)),
        ),
    )


def test_drag_model_protocol_is_runtime_checkable() -> None:
    class ConstantDragStub:
        def power_off_cd(self, mach: float) -> float:
            return 0.5 + 0.0 * mach

        def power_on_cd(self, mach: float) -> float:
            return 0.45 + 0.0 * mach

        def power_off_curve(self) -> list[tuple[float, float]]:
            return [(0.0, 0.5), (2.0, 0.5)]

        def power_on_curve(self) -> list[tuple[float, float]]:
            return [(0.0, 0.45), (2.0, 0.45)]

    stub = ConstantDragStub()
    assert isinstance(stub, DragModelProtocol)

    power_off, power_on = _load_real_drag_specs()
    model = DatabaseDragModel(power_off=power_off, power_on=power_on)
    assert isinstance(model, DragModelProtocol)


def test_database_drag_model_interpolates_and_clamps_real_curves() -> None:
    power_off, power_on = _load_real_drag_specs()
    model = DatabaseDragModel(power_off=power_off, power_on=power_on)

    off_curve = model.power_off_curve()
    on_curve = model.power_on_curve()
    assert isinstance(off_curve, list)
    assert isinstance(on_curve, list)
    assert len(off_curve) == 2500
    assert len(on_curve) == 2500

    # Mutating returned lists must not mutate internal model state.
    off_curve[0] = (999.0, 999.0)
    assert model.power_off_curve()[0] == pytest.approx((0.01, 0.453689802610909))

    # Exact grid lookup
    assert model.power_off_cd(0.01) == pytest.approx(0.453689802610909)
    assert model.power_off_cd(0.02) == pytest.approx(0.494775806032939)
    assert model.power_on_cd(0.01) == pytest.approx(power_on.points[0][1])

    # Midpoint linear interpolation
    expected_mid = 0.5 * (0.453689802610909 + 0.494775806032939)
    assert model.power_off_cd(0.015) == pytest.approx(expected_mid, rel=1e-12)

    # Constant endpoint clamping outside [min_mach, max_mach]
    assert model.power_off_cd(0.0) == pytest.approx(0.453689802610909)
    assert model.power_off_cd(30.0) == pytest.approx(power_off.points[-1][1])
    assert model.power_on_cd(0.0) == pytest.approx(power_on.points[0][1])
    assert model.power_on_cd(30.0) == pytest.approx(power_on.points[-1][1])


def test_database_drag_model_supports_scaling_and_rocket_factory() -> None:
    power_off, power_on = _load_real_drag_specs()
    rocket = _sample_rocket(power_off, power_on)
    base_model = DatabaseDragModel.from_rocket(rocket)
    scaled_model = base_model.scaled(1.25)

    assert base_model.drag_factor == 1.0
    assert scaled_model.drag_factor == 1.25
    assert scaled_model.power_off_cd(0.5) == pytest.approx(base_model.power_off_cd(0.5) * 1.25)
    assert scaled_model.power_on_cd(0.5) == pytest.approx(base_model.power_on_cd(0.5) * 1.25)

    scaled_off_curve = scaled_model.power_off_curve()
    base_off_curve = base_model.power_off_curve()
    assert scaled_off_curve[0] == pytest.approx(
        (base_off_curve[0][0], base_off_curve[0][1] * 1.25)
    )

    scaled_off_spec, scaled_on_spec = scaled_model.to_specs()
    assert isinstance(scaled_off_spec, DragCurveSpec)
    assert isinstance(scaled_on_spec, DragCurveSpec)
    assert scaled_off_spec.asset_name == "power_off.csv"
    assert scaled_on_spec.asset_name == "power_on.csv"
    assert scaled_off_spec.points[0][1] == pytest.approx(base_off_curve[0][1] * 1.25)


@pytest.mark.parametrize("bad_factor", [0.0, -0.5, float("nan"), float("inf"), True, False])
def test_database_drag_model_rejects_invalid_drag_factor(bad_factor: float | bool) -> None:
    power_off = DragCurveSpec(points=((0.0, 0.4), (1.0, 0.8)))
    power_on = DragCurveSpec(points=((0.0, 0.35), (1.0, 0.75)))
    with pytest.raises(ValueError):
        DatabaseDragModel(power_off=power_off, power_on=power_on, drag_factor=bad_factor)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_mach", [-0.01, float("nan"), float("inf"), True, False])
def test_database_drag_model_rejects_invalid_mach_queries(bad_mach: float | bool) -> None:
    power_off = DragCurveSpec(points=((0.0, 0.4), (1.0, 0.8)))
    power_on = DragCurveSpec(points=((0.0, 0.35), (1.0, 0.75)))
    model = DatabaseDragModel(power_off=power_off, power_on=power_on)
    with pytest.raises(ValueError):
        model.power_off_cd(bad_mach)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        model.power_on_cd(bad_mach)  # type: ignore[arg-type]


def test_aerodynamics_package_exports_expected_symbols() -> None:
    import hefesto.adapters.aerodynamics as aero_pkg

    assert set(aero_pkg.__all__) == {"DatabaseDragModel", "DragModelProtocol"}
