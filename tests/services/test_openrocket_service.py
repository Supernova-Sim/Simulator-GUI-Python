"""Tests for OpenRocket import service, SHA-256 cache, and catalog export."""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

import pytest

from hefesto.services import (
    DEFAULT_ROCKET_ID,
    import_and_save_ork_rocket,
    list_ork_assets,
    list_rockets,
    load_rocket_preset,
    load_rocket_spec,
    preview_ork_import,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

SIMPLE_ORK_XML = """<?xml version='1.0' encoding='utf-8'?>
<openrocket version="1.9">
  <rocket>
    <name>Hefesto Ork Demo</name>
    <subcomponents>
      <stage>
        <name>Sustainer</name>
        <subcomponents>
          <nosecone>
            <name>Ogiva</name>
            <shape>lvhaack</shape>
            <length>0.40</length>
            <aftradius>0.075</aftradius>
          </nosecone>
          <bodytube>
            <name>Tubo Principal</name>
            <length>1.20</length>
            <thickness>0.002</thickness>
            <radius>0.075</radius>
            <material type="bulk" density="1850.0">Fibra</material>
            <subcomponents>
              <trapezoidfinset>
                <name>Aletas</name>
                <fincount>4</fincount>
                <axialoffset method="bottom">0.0</axialoffset>
                <rootchord>0.25</rootchord>
                <tipchord>0.10</tipchord>
                <height>0.12</height>
                <sweeplength>0.08</sweeplength>
                <thickness>0.003</thickness>
              </trapezoidfinset>
              <railbutton>
                <name>RB</name>
                <instancecount>2</instancecount>
                <instanceseparation>0.60</instanceseparation>
                <axialoffset method="top">0.20</axialoffset>
              </railbutton>
              <parachute>
                <name>Main</name>
                <diameter>1.8</diameter>
                <cd>0.8</cd>
                <deployevent>apogee</deployevent>
              </parachute>
            </subcomponents>
          </bodytube>
        </subcomponents>
      </stage>
    </subcomponents>
  </rocket>
</openrocket>
"""


def _make_ork_bytes(xml_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("rocket.ork", xml_text.encode("utf-8"))
    return buf.getvalue()


def _setup_isolated_repo(tmp_path: Path) -> Path:
    (tmp_path / "data" / "assets" / "motors").mkdir(parents=True)
    (tmp_path / "data" / "assets" / "drag").mkdir(parents=True)
    (tmp_path / "data" / "catalog" / "motors").mkdir(parents=True)
    (tmp_path / "data" / "catalog" / "rockets").mkdir(parents=True)

    for rel in ("motors/medusa_knsb_a.eng", "motors/medusa_knsb_a.ric"):
        shutil.copy2(REPO_ROOT / "data" / "assets" / rel, tmp_path / "data" / "assets" / rel)
    for rel in ("drag/power_off.csv", "drag/power_on.csv"):
        shutil.copy2(REPO_ROOT / "data" / "assets" / rel, tmp_path / "data" / "assets" / rel)
    shutil.copy2(
        REPO_ROOT / "data" / "catalog" / "motors" / "medusa_knsb_a.json",
        tmp_path / "data" / "catalog" / "motors" / "medusa_knsb_a.json",
    )
    return tmp_path


def test_preview_ork_import_uses_hash_cache_and_binds_catalog_drag(tmp_path: Path) -> None:
    repo = _setup_isolated_repo(tmp_path)
    ork_bytes = _make_ork_bytes(SIMPLE_ORK_XML)

    first = preview_ork_import(
        ork_bytes,
        base_motor_id="medusa_knsb_a",
        power_off_drag_asset="power_off.csv",
        power_on_drag_asset="power_on.csv",
        repo_root=repo,
    )
    assert first.from_cache is False
    assert first.calculated_dry_mass_kg > 0.0
    assert first.center_of_mass_without_motor_m > 0.0
    # .ork imports default to the analytical geometry model (no CSV-backed curves).
    assert first.drag_source == "analytical"
    assert first.rocket_spec.drag_source == "analytical"
    assert first.rocket_spec.power_off_drag.asset_name is None
    assert first.rocket_spec.power_on_drag.asset_name is None
    assert any("analytical" in w.message for w in first.warnings)
    assert any("power_off.csv" in w.message for w in first.warnings)

    second = preview_ork_import(
        ork_bytes,
        base_motor_id="medusa_knsb_a",
        power_off_drag_asset="power_off.csv",
        power_on_drag_asset="power_on.csv",
        repo_root=repo,
    )
    assert second.from_cache is True
    assert second.calculated_dry_mass_kg == pytest.approx(first.calculated_dry_mass_kg)


def test_import_and_save_ork_rocket_persists_and_blocks_golden_master(tmp_path: Path) -> None:
    repo = _setup_isolated_repo(tmp_path)
    ork_bytes = _make_ork_bytes(SIMPLE_ORK_XML)

    with pytest.raises(ValueError, match="Golden Master"):
        import_and_save_ork_rocket(
            ork_bytes,
            rocket_id=DEFAULT_ROCKET_ID,
            base_motor_id="medusa_knsb_a",
            power_off_drag_asset="power_off.csv",
            power_on_drag_asset="power_on.csv",
            repo_root=repo,
        )

    summary = import_and_save_ork_rocket(
        ork_bytes,
        rocket_id="ork_demo_v1",
        base_motor_id="medusa_knsb_a",
        power_off_drag_asset="power_off.csv",
        power_on_drag_asset="power_on.csv",
        rocket_name="Ork Demo Custom",
        repo_root=repo,
    )
    assert summary.rocket_id == "ork_demo_v1"
    assert "ork_demo_v1" in list_rockets(repo_root=repo)
    assert "ork_demo_v1.ork" in list_ork_assets(repo_root=repo)

    reloaded_preset = load_rocket_preset("ork_demo_v1", repo_root=repo)
    assert reloaded_preset.name == "Ork Demo Custom"
    reloaded_spec = load_rocket_spec("ork_demo_v1", repo_root=repo)
    assert reloaded_spec.radius_m == pytest.approx(0.075)
    # Nose shell lives on the nose spec (never duplicated as a loose component).
    assert reloaded_spec.nose_cone.shell is not None
    assert reloaded_spec.nose_cone.shell.name == "Ogiva (casca)"
    assert not any(c.name == "Ogiva (casca)" for c in reloaded_spec.components)


def test_catalog_nose_shell_is_counted_exactly_once_per_preset() -> None:
    from hefesto.physics import derive_dry_mass

    # Golden Master keeps its measured nose mass as a component, no derived shell.
    v1 = load_rocket_spec("hefesto_v1")
    assert v1.nose_cone.shell is None
    assert derive_dry_mass(v1) == pytest.approx(18.85049031412732, rel=1e-12)

    # 1.41 predates the shell-on-nose pipeline: same mass, legacy representation.
    legacy = load_rocket_spec("hefesto_1.41")
    assert legacy.nose_cone.shell is None
    assert any(c.name == "Coifa (casca)" for c in legacy.components)
    assert derive_dry_mass(legacy) == pytest.approx(15.721961000306269, rel=1e-12)

    # Re-imported 1.4 carries the shell on the nose spec only (OpenRocket: 15.758719 kg).
    imported = load_rocket_spec("hefesto_1.4")
    assert imported.nose_cone.shell is not None
    assert not any(c.name == "Coifa (casca)" for c in imported.components)
    assert derive_dry_mass(imported) == pytest.approx(15.769610321481428, rel=1e-12)
    assert imported.motor_position_m == pytest.approx(2.625)
    assert imported.rail_buttons.radius_m == pytest.approx(0.02)


FLIGHTDATA_ORK_XML = """<?xml version='1.0' encoding='utf-8'?>
<openrocket version="1.9">
  <rocket>
    <name>Ork Flightdata Demo</name>
    <subcomponents>
      <stage>
        <name>Sustainer</name>
        <subcomponents>
          <nosecone>
            <name>Ogiva</name>
            <shape>lvhaack</shape>
            <length>0.40</length>
            <aftradius>0.075</aftradius>
          </nosecone>
          <bodytube>
            <name>Tubo Principal</name>
            <length>1.20</length>
            <thickness>0.002</thickness>
            <radius>0.075</radius>
            <material type="bulk" density="1850.0">Fibra</material>
            <subcomponents>
              <trapezoidfinset>
                <name>Aletas</name>
                <fincount>4</fincount>
                <axialoffset method="bottom">0.0</axialoffset>
                <rootchord>0.25</rootchord>
                <tipchord>0.10</tipchord>
                <height>0.12</height>
                <sweeplength>0.08</sweeplength>
                <thickness>0.003</thickness>
              </trapezoidfinset>
            </subcomponents>
          </bodytube>
        </subcomponents>
      </stage>
    </subcomponents>
  </rocket>
  <simulations>
    <simulation status="uptodate">
      <flightdata>
        <databranch types="time,altitude,mach_number,drag_coeff,thrust_force">
          <event time="5.0" type="apogee"/>
          <datapoint>0.10,10.0,0.10,0.61,900.0</datapoint>
          <datapoint>0.20,40.0,0.20,0.62,1000.0</datapoint>
          <datapoint>0.30,90.0,0.30,0.63,1100.0</datapoint>
          <datapoint>0.40,160.0,0.40,0.64,1200.0</datapoint>
          <datapoint>0.50,250.0,0.50,0.65,1300.0</datapoint>
          <datapoint>1.00,310.0,0.50,0.71,0.0</datapoint>
          <datapoint>2.00,340.0,0.40,0.72,0.0</datapoint>
          <datapoint>3.00,350.0,0.30,0.73,0.0</datapoint>
          <datapoint>4.00,345.0,0.20,0.74,0.0</datapoint>
          <datapoint>5.00,320.0,0.10,0.75,0.0</datapoint>
          <datapoint>6.00,300.0,0.10,40.0,0.0</datapoint>
          <datapoint>7.00,250.0,0.10,40.0,0.0</datapoint>
        </databranch>
      </flightdata>
    </simulation>
  </simulations>
</openrocket>
"""


def test_parse_ork_extracts_ork_sim_drag_table(tmp_path: Path) -> None:
    from hefesto.adapters.openrocket import parse_ork_bytes

    parsed = parse_ork_bytes(_make_ork_bytes(FLIGHTDATA_ORK_XML))
    table = parsed.drag_table
    assert table is not None
    assert table.source == "ork_sim"
    assert table.mach[-1] == pytest.approx(0.5)
    assert table.cd_power_off[round(0.3 / 0.01)] == pytest.approx(0.73)
    assert table.cd_power_on[round(0.3 / 0.01)] == pytest.approx(0.63)
    # The post-apogee chute samples are excluded from the coasting curve.
    assert max(table.cd_power_off) < 1.0


def test_import_and_save_ork_rocket_persists_ork_sim_drag_table(tmp_path: Path) -> None:
    repo = _setup_isolated_repo(tmp_path)
    ork_bytes = _make_ork_bytes(FLIGHTDATA_ORK_XML)

    summary = import_and_save_ork_rocket(
        ork_bytes,
        rocket_id="ork_sim_demo",
        base_motor_id="medusa_knsb_a",
        power_off_drag_asset="power_off.csv",
        power_on_drag_asset="power_on.csv",
        drag_source="ork_sim",
        repo_root=repo,
    )
    assert summary.drag_source == "ork_sim"
    assert summary.drag_table is not None

    reloaded = load_rocket_preset("ork_sim_demo", repo_root=repo)
    assert reloaded.drag_source == "ork_sim"
    assert reloaded.drag_table is not None
    assert reloaded.drag_table.source == "ork_sim"

    spec = load_rocket_spec("ork_sim_demo", repo_root=repo)
    assert spec.drag_source == "ork_sim"
    assert spec.power_off_drag.asset_name is None
    assert spec.power_off_drag.points[round(0.3 / 0.01)][1] == pytest.approx(0.73)


def test_preview_ork_import_rejects_ork_sim_without_flightdata(tmp_path: Path) -> None:
    repo = _setup_isolated_repo(tmp_path)
    with pytest.raises(ValueError, match="flightdata"):
        preview_ork_import(
            _make_ork_bytes(SIMPLE_ORK_XML),
            base_motor_id="medusa_knsb_a",
            power_off_drag_asset="power_off.csv",
            power_on_drag_asset="power_on.csv",
            drag_source="ork_sim",
            repo_root=repo,
        )
