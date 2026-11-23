"""Typed drag-curve facade tests: preview_rocket_drag_curves and import_rasaero_drag_csv."""

from __future__ import annotations

import pytest

from hefesto.domain import DragCurveSpec, DragCurveTable, RocketSpec, SurfaceFinish
from hefesto.services import (
    import_rasaero_drag_csv,
    interpolate_drag_curve,
    list_rasaero_csv_angles,
    load_rocket_spec,
    preview_rocket_drag_curves,
)

# Typical RASAero II aerodynamic export: 3 Mach x 2 alpha rows.
RASAERO_CSV = """RASAero II - Aerodynamic Data
Mach Number,Angle of Attack (alpha),CD Power-Off,CD Power-On,CN,CM
0.30,0.00,0.4940,0.4900,0.000,0.000
0.30,2.00,0.5130,0.5090,0.041,0.012
0.70,0.00,0.5580,0.5540,0.000,0.000
0.70,2.00,0.5770,0.5730,0.047,0.015
1.20,0.00,0.6120,0.6060,0.000,0.000
1.20,2.00,0.6330,0.6270,0.052,0.019
"""

SINGLE_ALPHA_CSV = """Mach Number,Angle of Attack (alpha),CD Power-Off,CD Power-On
0.20,0.00,0.4700,0.4660
0.90,0.00,0.5810,0.5730
"""


def test_preview_rocket_drag_curves_legacy_csv_matches_loaded_assets() -> None:
    rocket = load_rocket_spec("hefesto_v1")

    table = preview_rocket_drag_curves(rocket)

    assert table.source == "legacy_csv"
    assert table.mach == [mach for mach, _ in rocket.power_off_drag.points]
    assert table.cd_power_off == [cd for _, cd in rocket.power_off_drag.points]
    assert table.cd_power_on == [cd for _, cd in rocket.power_on_drag.points]
    assert table.mach[0] == pytest.approx(0.01)
    assert table.mach[-1] == pytest.approx(25.0)


def test_preview_rocket_drag_curves_analytical_tracks_finish_and_geometry() -> None:
    rocket = load_rocket_spec("hefesto_1.4")
    assert rocket.drag_source == "analytical"

    smooth = preview_rocket_drag_curves(
        rocket.model_copy(update={"surface_finish": SurfaceFinish.SMOOTH})
    )
    unfinished = preview_rocket_drag_curves(
        rocket.model_copy(update={"surface_finish": SurfaceFinish.UNFINISHED})
    )
    shorter_nose = preview_rocket_drag_curves(
        rocket.model_copy(
            update={"nose_cone": rocket.nose_cone.model_copy(update={"length_m": 0.30})}
        )
    )

    assert smooth.source == "analytical"
    assert smooth.mach[0] == pytest.approx(0.0)
    assert smooth.mach[-1] == pytest.approx(3.0)
    index = smooth.mach.index(0.8)
    # Rougher skin and a blunter body must both raise the axial Cd.
    assert unfinished.cd_power_off[index] > smooth.cd_power_off[index]
    assert shorter_nose.cd_power_off[index] > smooth.cd_power_off[index]
    # The powered phase shields the base, so it never drags more than power-off.
    assert smooth.cd_power_on[index] < smooth.cd_power_off[index]


def test_preview_rocket_drag_curves_materializes_in_memory_sources() -> None:
    rocket = load_rocket_spec("hefesto_v1")
    table = DragCurveTable(
        mach=[0.0, 0.5, 1.0],
        cd_power_off=[0.4, 0.5, 0.9],
        cd_power_on=[0.38, 0.48, 0.88],
        source="ork_sim",
    )
    power_off_drag, power_on_drag = table.to_specs()

    ork_rocket = rocket.model_copy(
        update={
            "drag_source": "ork_sim",
            "power_off_drag": power_off_drag,
            "power_on_drag": power_on_drag,
        }
    )
    preview = preview_rocket_drag_curves(ork_rocket)
    assert preview.source == "ork_sim"
    assert preview.mach == [0.0, 0.5, 1.0]
    assert preview.cd_power_off == [0.4, 0.5, 0.9]
    assert preview.cd_power_on == [0.38, 0.48, 0.88]

    imported = import_rasaero_drag_csv(rocket, RASAERO_CSV, "l.cs")
    preview = preview_rocket_drag_curves(imported)
    assert preview.source == "rasaero_csv"
    assert preview.mach == [0.3, 0.7, 1.2]
    assert preview.cd_power_off == [0.494, 0.558, 0.612]
    assert preview.cd_power_on == [0.49, 0.554, 0.606]


def test_preview_rocket_drag_curves_merges_mismatched_mach_grids() -> None:
    rocket = load_rocket_spec("hefesto_v1").model_copy(
        update={
            "power_off_drag": DragCurveSpec(points=((0.0, 0.4), (1.0, 0.8))),
            "power_on_drag": DragCurveSpec(points=((0.0, 0.3), (0.5, 0.5), (1.0, 0.7))),
        }
    )

    table = preview_rocket_drag_curves(rocket)

    assert table.mach == [0.0, 0.5, 1.0]
    assert table.cd_power_off == pytest.approx([0.4, 0.6, 0.8])
    assert table.cd_power_on == pytest.approx([0.3, 0.5, 0.7])


def test_interpolate_drag_curve_linear_with_constant_extrapolation() -> None:
    mach = [0.0, 0.5, 1.0]
    cd = [0.4, 0.5, 0.9]

    assert interpolate_drag_curve(mach, cd, 0.0) == pytest.approx(0.4)
    assert interpolate_drag_curve(mach, cd, 0.25) == pytest.approx(0.45)
    assert interpolate_drag_curve(mach, cd, 0.75) == pytest.approx(0.7)
    assert interpolate_drag_curve(mach, cd, -1.0) == pytest.approx(0.4)
    assert interpolate_drag_curve(mach, cd, 5.0) == pytest.approx(0.9)

    with pytest.raises(ValueError, match="at least 2 points"):
        interpolate_drag_curve([0.0], [0.4], 0.0)
    with pytest.raises(ValueError, match="matching mach/cd samples"):
        interpolate_drag_curve([0.0, 1.0], [0.4], 0.5)


def test_import_rasaero_drag_csv_installs_validated_curves() -> None:
    rocket = load_rocket_spec("hefesto_v1")

    imported = import_rasaero_drag_csv(rocket, RASAERO_CSV, "l.cs")

    assert isinstance(imported, RocketSpec)
    assert imported.drag_source == "rasaero_csv"
    assert imported.power_off_drag.points == ((0.3, 0.494), (0.7, 0.558), (1.2, 0.612))
    assert imported.power_on_drag.points == ((0.3, 0.49), (0.7, 0.554), (1.2, 0.606))
    # Computed sources must not carry CSV asset names, otherwise RocketPy rejects them.
    assert imported.power_off_drag.asset_name is None
    assert imported.power_on_drag.asset_name is None
    # The input spec is immutable and left untouched.
    assert rocket.drag_source == "legacy_csv"
    assert rocket.power_off_drag.asset_name == "power_off.csv"

    at_alpha = import_rasaero_drag_csv(rocket, RASAERO_CSV, "l.cs", alpha_deg=2.0)
    assert at_alpha.power_off_drag.points == ((0.3, 0.513), (0.7, 0.577), (1.2, 0.633))
    assert at_alpha.power_on_drag.points == ((0.3, 0.509), (0.7, 0.573), (1.2, 0.627))


def test_list_rasaero_csv_angles_reports_the_export_alpha_grid() -> None:
    assert list_rasaero_csv_angles(RASAERO_CSV, "l.cs") == (0.0, 2.0)
    assert list_rasaero_csv_angles(SINGLE_ALPHA_CSV) == ()

    with pytest.raises(ValueError, match="empty"):
        list_rasaero_csv_angles("   \n")


@pytest.mark.parametrize(
    ("csv_text", "alpha_deg", "match"),
    [
        ("", 0.0, "empty"),
        ("nothing but text\n", 0.0, "no RASAero header row"),
        (
            "Mach Number,Angle of Attack (alpha),CN\n0.30,0.00,0.1\n0.50,0.00,0.2\n",
            0.0,
            "CD Power-Off",
        ),
        (RASAERO_CSV, 1.0, "available angles"),
        (SINGLE_ALPHA_CSV, 2.0, "only alpha=0 rows"),
        (
            "Mach Number,Angle of Attack (alpha),CD Power-Off,CD Power-On\n"
            "0.30,0.00,-0.50,0.49\n",
            0.0,
            "CD values must be >= 0",
        ),
    ],
)
def test_import_rasaero_drag_csv_rejects_invalid_exports(
    csv_text: str,
    alpha_deg: float,
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        import_rasaero_drag_csv(load_rocket_spec("hefesto_v1"), csv_text, "l.cs", alpha_deg)
