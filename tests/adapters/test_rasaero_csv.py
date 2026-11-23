"""RASAero II CSV drag export parsing and RocketPy drag-source dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from hefesto.adapters import (
    build_rocket,
    parse_rasaero_csv_file,
    parse_rasaero_csv_text,
)

# Typical export of RASAero II's aerodynamic window (l.cs) for the Hefesto airframe.
RASAERO_CSV = """RASAero II - Aerodynamic Data
Configuration: Hefesto v1.2
Mach Number,Angle of Attack (alpha),CD Power-Off,CD Power-On,CN,CM
0.30,0.00,0.4940,0.4900,0.000,0.000
0.30,2.00,0.5130,0.5090,0.041,0.012
0.30,4.00,0.5480,0.5440,0.083,0.026
0.50,0.00,0.5190,0.5150,0.000,0.000
0.50,2.00,0.5380,0.5340,0.043,0.013
0.50,4.00,0.5740,0.5700,0.088,0.028
0.70,0.00,0.5580,0.5540,0.000,0.000
0.70,2.00,0.5770,0.5730,0.047,0.015
0.70,4.00,0.6140,0.6100,0.095,0.031
"""


def test_parse_rasaero_export_extracts_axial_curve_and_alpha_grid() -> None:
    table = parse_rasaero_csv_text(RASAERO_CSV, source_name="l.cs")

    assert table.source == "rasaero_csv"
    assert table.mach == [0.3, 0.5, 0.7]
    assert table.cd_power_off == [0.494, 0.519, 0.558]
    assert table.cd_power_on == [0.49, 0.515, 0.554]
    assert table.alpha_deg == [0.0, 2.0, 4.0]
    assert table.cd_alpha_power_off[2] == [0.548, 0.574, 0.614]
    assert table.cd_alpha_power_on[1] == [0.509, 0.534, 0.573]

    power_off_spec, power_on_spec = table.to_specs()
    assert power_off_spec.points == ((0.3, 0.494), (0.5, 0.519), (0.7, 0.558))
    assert power_on_spec.asset_name is None


def test_parse_rasaero_file_accepts_bom_and_crlf(tmp_path: Path) -> None:
    target = tmp_path / "l.cs"
    target.write_text("\ufeff" + RASAERO_CSV.replace("\n", "\r\n"), encoding="utf-8")
    table = parse_rasaero_csv_file(target)
    assert table.mach == [0.3, 0.5, 0.7]
    assert table.source == "rasaero_csv"


def test_parse_rasaero_falls_back_to_generic_cd_headers() -> None:
    text = (
        "Mach Number,Angle of Attack (alpha),CD\n"
        "0.20,0.00,0.4700\n"
        "0.40,0.00,0.5050\n"
    )
    table = parse_rasaero_csv_text(text)
    assert table.cd_power_off == [0.47, 0.505]
    assert table.cd_power_on == [0.47, 0.505]
    assert table.alpha_deg == []


def test_parse_rasaero_accepts_axial_force_headers() -> None:
    text = (
        "Mach Number,Angle of Attack (alpha),CA Power-Off,CA Power-On\n"
        "0.30,0.00,0.4940,0.4900\n"
        "0.60,0.00,0.5368,0.5330\n"
    )
    table = parse_rasaero_csv_text(text)
    assert table.cd_power_off == [0.494, 0.5368]
    assert table.cd_power_on == [0.49, 0.533]


@pytest.mark.parametrize(
    ("csv_text", "match"),
    [
        ("Mach Number,Angle of Attack (alpha),CD Power-Off,CD Power-On\n", "no data rows"),
        (
            "Mach Number,Angle of Attack (alpha),CD Power-Off,CD Power-On\n"
            "0.30,2.00,0.50,0.49\n",
            "alpha = 0",
        ),
        (
            "Mach Number,Angle of Attack (alpha),CD Power-Off,CD Power-On\n"
            "0.30,0.00,0.50,0.49\n"
            "0.30,2.00,0.52,0.51\n"
            "0.50,0.00,0.52,0.51\n",
            "same Mach grid",
        ),
        (
            "Mach,Alpha,CN\n0.30,0.00,0.1\n0.50,0.00,0.2\n",
            "CD Power-Off",
        ),
        ("nothing but text\n", "no RASAero header row"),
        (
            "Mach Number,Angle of Attack (alpha),CD Power-Off,CD Power-On\n"
            "0.30,0.00,abc,0.49\n",
            "invalid numeric CD Power-Off",
        ),
    ],
)
def test_parse_rasaero_rejects_malformed_exports(csv_text: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        parse_rasaero_csv_text(csv_text)


def test_rocket_builder_dispatches_rasaero_and_rejects_stale_csv_assets() -> None:
    from hefesto.services import load_rocket_spec

    rocket = load_rocket_spec("hefesto_1.4")
    table = parse_rasaero_csv_text(RASAERO_CSV, source_name="l.cs")
    power_off_drag, power_on_drag = table.to_specs()
    rasaero_rocket = rocket.model_copy(
        update={
            "drag_source": "rasaero_csv",
            "power_off_drag": power_off_drag,
            "power_on_drag": power_on_drag,
        }
    )
    built = build_rocket(rasaero_rocket)
    assert built.power_off_drag(0.5) == pytest.approx(0.519, rel=1e-9)
    assert built.power_on_drag(0.7) == pytest.approx(0.554, rel=1e-9)

    legacy = load_rocket_spec("hefesto_v1")
    stale = legacy.model_copy(update={"drag_source": "ork_sim"})
    with pytest.raises(ValueError, match="requires in-memory curves"):
        build_rocket(stale)


def test_build_rocket_spec_honors_rasaero_csv_preset_source(tmp_path: Path) -> None:
    from hefesto.services import (
        build_rocket_spec,
        load_motor_spec,
        load_rocket_preset,
    )

    drag_dir = tmp_path / "data" / "assets" / "drag"
    drag_dir.mkdir(parents=True)
    (drag_dir / "l.cs").write_text(RASAERO_CSV, encoding="utf-8")

    preset = load_rocket_preset("hefesto_v1").model_copy(
        update={"drag_source": "rasaero_csv", "power_off_drag_asset": "l.cs"}
    )
    motor = load_motor_spec("medusa_knsb_a")
    rocket = build_rocket_spec(preset, motor=motor, repo_root=tmp_path)

    assert rocket.drag_source == "rasaero_csv"
    assert rocket.power_off_drag.asset_name is None
    assert rocket.power_off_drag.points == ((0.3, 0.494), (0.5, 0.519), (0.7, 0.558))
    assert rocket.power_on_drag.points == ((0.3, 0.49), (0.5, 0.515), (0.7, 0.554))
    built = build_rocket(rocket, motor=None)
    assert built.power_off_drag(0.6) == pytest.approx(0.5385, rel=1e-9)
