"""Deterministic tests for pure-stdlib OpenRocket (.ork) ZIP/XML parser."""

from __future__ import annotations

import io
import math
import zipfile

import pytest

from hefesto.adapters.openrocket import OrkParseError, parse_ork_bytes
from hefesto.domain import (
    FinComponent,
    NoseConeKind,
    PointMassComponent,
    TubeComponent,
)

SAMPLE_ORK_XML = """<?xml version='1.0' encoding='utf-8'?>
<openrocket version="1.9" creator="OpenRocket 23.09">
  <rocket>
    <name>Supernova Test Rocket</name>
    <subcomponents>
      <stage>
        <name>Sustainer</name>
        <subcomponents>
          <nosecone>
            <name>Ogiva Principal</name>
            <shape>ogive</shape>
            <length>0.45</length>
            <thickness>0.003</thickness>
            <aftradius>auto</aftradius>
          </nosecone>
          <bodytube>
            <name>Corpo Principal</name>
            <length>1.0</length>
            <thickness>0.002</thickness>
            <radius>0.079</radius>
            <material type="bulk" density="1850.0">Fibra</material>
            <subcomponents>
              <tubecoupler>
                <name>Coupler</name>
                <axialoffset method="bottom">0.10</axialoffset>
                <length>0.20</length>
                <outerradius>auto</outerradius>
                <thickness>0.002</thickness>
                <material type="bulk" density="2700.0">Aluminio</material>
              </tubecoupler>
              <centeringring>
                <name>Anel</name>
                <instancecount>2</instancecount>
                <instanceseparation>0.40</instanceseparation>
                <axialoffset method="top">0.20</axialoffset>
                <length>0.006</length>
                <outerradius>auto</outerradius>
                <innerradius>0.049</innerradius>
              </centeringring>
              <innertube>
                <name>Motor Mount</name>
                <axialoffset method="bottom">0.0</axialoffset>
                <length>0.60</length>
                <outerradius>0.049</outerradius>
                <thickness>0.002</thickness>
                <motormount>
                  <ignitionevent>automatic</ignitionevent>
                </motormount>
              </innertube>
              <masscomponent>
                <name>Avionica</name>
                <axialoffset method="top">0.10</axialoffset>
                <length>0.10</length>
                <mass>0.8</mass>
              </masscomponent>
              <freeformfinset>
                <name>Aletas Freeform</name>
                <fincount>4</fincount>
                <cant>0.0</cant>
                <thickness>0.004</thickness>
                <axialoffset method="bottom">0.0</axialoffset>
                <finpoints>
                  <point x="0.0" y="0.0"/>
                  <point x="0.10" y="0.12"/>
                  <point x="0.25" y="0.12"/>
                  <point x="0.30" y="0.0"/>
                </finpoints>
              </freeformfinset>
              <parachute>
                <name>Paraquedas Principal</name>
                <diameter>1.5</diameter>
                <cd>0.8</cd>
                <deployevent>apogee</deployevent>
                <deploydelay>1.0</deploydelay>
              </parachute>
              <railbutton>
                <name>Rail Button</name>
                <instancecount>2</instancecount>
                <instanceseparation>0.50</instanceseparation>
                <axialoffset method="top">0.15</axialoffset>
                <length>0.01</length>
              </railbutton>
            </subcomponents>
          </bodytube>
          <transition>
            <name>Boattail</name>
            <length>0.10</length>
          </transition>
          <bodytube>
            <name>Cauda</name>
            <axialoffset method="after">0.0</axialoffset>
            <length>0.50</length>
            <thickness>0.002</thickness>
            <radius>auto</radius>
            <overridemass>1.5</overridemass>
            <subcomponents>
              <trapezoidfinset>
                <name>Aletas Trap</name>
                <fincount>3</fincount>
                <axialoffset method="top">0.10</axialoffset>
                <rootchord>0.20</rootchord>
                <tipchord>0.10</tipchord>
                <height>0.10</height>
                <sweeplength>0.05</sweeplength>
                <thickness>0.003</thickness>
              </trapezoidfinset>
            </subcomponents>
          </bodytube>
        </subcomponents>
      </stage>
    </subcomponents>
  </rocket>
  <simulations>
    <simulation>
      <flightdata>
        <branch>
          <datapoint>0.0,0.0,0.0</datapoint>
          <datapoint>0.1,0.5,10.0</datapoint>
        </branch>
      </flightdata>
    </simulation>
  </simulations>
</openrocket>
"""


def _build_ork_zip(xml_text: str, *, extra_files: dict[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("rocket.ork", xml_text.encode("utf-8"))
        if extra_files:
            for name, payload in extra_files.items():
                zf.writestr(name, payload)
    return buf.getvalue()


def test_parse_ork_zip_coordinates_inheritance_and_warnings() -> None:
    raw = _build_ork_zip(
        SAMPLE_ORK_XML,
        extra_files={"thrustcurves/mock.rse": b"<engine-database/>"},
    )
    parsed = parse_ork_bytes(raw)

    assert parsed.rocket_name == "Supernova Test Rocket"
    assert parsed.radius_m == pytest.approx(0.079)
    assert parsed.nose_cone.kind == NoseConeKind.OGIVE
    assert parsed.nose_cone.length_m == pytest.approx(0.45)
    assert parsed.nose_cone.base_radius_m == pytest.approx(0.079)
    assert parsed.embedded_rse_names == ("thrustcurves/mock.rse",)
    assert parsed.stored_datapoint_count == 2
    assert parsed.has_mass_or_cg_overrides is True

    tubes = {
        c.name: c
        for c in parsed.components
        if isinstance(c, TubeComponent)
    }
    assert tubes["Corpo Principal"].position_m == pytest.approx(0.95)
    assert tubes["Corpo Principal"].outer_radius_m == pytest.approx(0.079)

    # Coupler: parent ends at 1.45, offset=+0.10, length=0.20 => start=1.35, center=1.45
    assert tubes["Coupler"].outer_radius_m == pytest.approx(0.077)
    assert tubes["Coupler"].position_m == pytest.approx(1.45)

    # Centering rings: top=0.45+0.20=0.65, sep=0.40, len=0.006 => centers 0.653 and 1.053
    assert tubes["Anel #1"].position_m == pytest.approx(0.653)
    assert tubes["Anel #2"].position_m == pytest.approx(1.053)
    assert tubes["Anel #1"].outer_radius_m == pytest.approx(0.077)

    # Transition length=0.10 advances cursor from 1.45 to 1.55 => Cauda center = 1.55 + 0.25 = 1.80
    assert tubes["Cauda"].outer_radius_m == pytest.approx(0.079)
    assert tubes["Cauda"].position_m == pytest.approx(1.80)

    # Motor mount innertube ends at 1.45
    assert parsed.detected_motor_mount_position_m == pytest.approx(1.45)

    # Point masses: the masscomponent plus one lumped mass per rail button instance.
    masses = {c.name: c for c in parsed.components if isinstance(c, PointMassComponent)}
    assert set(masses) == {"Avionica", "Rail Button #1", "Rail Button #2"}
    assert masses["Avionica"].mass_kg == pytest.approx(0.8)
    assert masses["Avionica"].position_m == pytest.approx(0.60)
    # Solid standoff fallback (no ORK base/flange heights): pi*R^2*L*1050 with R=0.02, L=0.01.
    solid_button_kg = 1050.0 * math.pi * 0.02**2 * 0.01
    assert masses["Rail Button #1"].mass_kg == pytest.approx(solid_button_kg)
    assert masses["Rail Button #1"].position_m == pytest.approx(0.605)

    # Fins synchronized
    fin_comps = [c for c in parsed.components if isinstance(c, FinComponent)]
    assert len(fin_comps) == 2
    assert parsed.fins.name == fin_comps[0].name == "Aletas Freeform"
    assert parsed.fins.count == fin_comps[0].count == 4
    assert parsed.fins.shape_points_m == fin_comps[0].shape_points_m

    # Rail buttons: 0.45 + 0.15 = 0.60 and 0.60 + 0.50 = 1.10
    assert parsed.rail_buttons.upper_button_position_m == pytest.approx(0.60)
    assert parsed.rail_buttons.lower_button_position_m == pytest.approx(1.10)

    # Parachute
    assert len(parsed.parachutes) == 1
    assert parsed.parachutes[0].trigger == "apogee"
    assert parsed.parachutes[0].lag_s == pytest.approx(1.0)

    # Warnings emitted for transition, override, multiple finsets, etc.
    warning_msgs = [w.message for w in parsed.warnings]
    assert any("<transition>" in msg for msg in warning_msgs)
    assert any("overridemass" in msg for msg in warning_msgs)
    assert any("conjuntos de aletas" in msg for msg in warning_msgs)


def test_parse_ork_plain_xml_fallback() -> None:
    parsed = parse_ork_bytes(SAMPLE_ORK_XML.encode("utf-8"))
    assert parsed.rocket_name == "Supernova Test Rocket"
    assert parsed.embedded_rse_names == ()


def test_parse_ork_rejects_zip_slip() -> None:
    raw = _build_ork_zip(SAMPLE_ORK_XML, extra_files={"../escape.txt": b"bad"})
    with pytest.raises(OrkParseError, match="traversal"):
        parse_ork_bytes(raw)


def test_parse_ork_auto_with_numeric_fallback_and_parent_inheritance() -> None:
    xml_auto = """<?xml version='1.0' encoding='utf-8'?>
<openrocket version="1.9">
  <rocket>
    <name>Auto Radius Rocket</name>
    <subcomponents>
      <stage>
        <name>Sustainer</name>
        <subcomponents>
          <nosecone>
            <name>Ogiva Auto</name>
            <shape>ogive</shape>
            <length>0.40</length>
            <radius>auto 0.079</radius>
          </nosecone>
          <bodytube>
            <name>Corpo Auto</name>
            <length>1.00</length>
            <thickness>0.004</thickness>
            <radius>  AUTO   0.079 </radius>
            <subcomponents>
              <tubecoupler>
                <name>Coupler Filho Auto</name>
                <length>0.20</length>
                <outerradius>auto 0.099</outerradius>
              </tubecoupler>
              <centeringring>
                <name>Anel Auto</name>
                <thickness>0.005</thickness>
                <outerradius>auto 0.079</outerradius>
                <innerradius>auto 0.050</innerradius>
              </centeringring>
            </subcomponents>
          </bodytube>
          <bodytube>
            <name>Corpo Auto Sem Valor</name>
            <length>0.30</length>
            <thickness>0.002</thickness>
            <outerradius>auto</outerradius>
          </bodytube>
        </subcomponents>
      </stage>
    </subcomponents>
  </rocket>
</openrocket>
"""
    parsed = parse_ork_bytes(xml_auto.encode("utf-8"))
    assert parsed.radius_m == pytest.approx(0.079)
    assert parsed.nose_cone.base_radius_m == pytest.approx(0.079)

    tubes = {c.name: c for c in parsed.components if isinstance(c, TubeComponent)}
    assert tubes["Corpo Auto"].outer_radius_m == pytest.approx(0.079)
    # Parent inner radius = 0.079 - 0.004 = 0.075 takes precedence over 'auto 0.099'
    assert tubes["Coupler Filho Auto"].outer_radius_m == pytest.approx(0.075)
    assert tubes["Anel Auto"].outer_radius_m == pytest.approx(0.075)
    assert tubes["Anel Auto"].inner_radius_m == pytest.approx(0.050)
    assert tubes["Anel Auto"].wall_thickness_m == pytest.approx(0.025)
    assert tubes["Corpo Auto Sem Valor"].outer_radius_m == pytest.approx(0.079)
    assert any("modo 'auto'" in w.message for w in parsed.warnings)


def test_parse_ork_extracts_nose_metadata_and_parachute_masses() -> None:
    xml_masses = """<?xml version='1.0' encoding='utf-8'?>
<openrocket version="1.9">
  <rocket>
    <name>Mass Parity Rocket</name>
    <subcomponents>
      <stage>
        <name>Sustainer</name>
        <subcomponents>
          <nosecone>
            <name>Coifa</name>
            <shape>haack</shape>
            <length>0.45</length>
            <thickness>0.002</thickness>
            <aftradius>0.079</aftradius>
            <material type="bulk" density="1850.0">Fiberglass</material>
            <subcomponents>
              <parachute>
                <name>Paraquedas A</name>
                <axialoffset method="top">0.28</axialoffset>
                <packedlength>0.30</packedlength>
                <overridemass>0.65</overridemass>
                <diameter>3.8</diameter>
                <cd>1.5</cd>
                <deployevent>altitude</deployevent>
                <deployaltitude>450.0</deployaltitude>
              </parachute>
            </subcomponents>
          </nosecone>
          <bodytube>
            <name>Corpo</name>
            <length>0.50</length>
            <thickness>0.002</thickness>
            <radius>0.079</radius>
            <subcomponents>
              <trapezoidfinset>
                <name>Aletas</name>
                <fincount>4</fincount>
                <rootchord>0.20</rootchord>
                <tipchord>0.10</tipchord>
                <height>0.10</height>
                <sweeplength>0.05</sweeplength>
                <thickness>0.003</thickness>
              </trapezoidfinset>
            </subcomponents>
          </bodytube>
        </subcomponents>
      </stage>
    </subcomponents>
  </rocket>
</openrocket>
"""
    parsed = parse_ork_bytes(xml_masses.encode("utf-8"))
    assert parsed.nose_cone_wall_thickness_m == pytest.approx(0.002)
    assert parsed.nose_cone_density_kg_m3 == pytest.approx(1850.0)
    pm = {c.name: c for c in parsed.components if isinstance(c, PointMassComponent)}
    assert "Paraquedas A (paraquedas)" in pm
    assert pm["Paraquedas A (paraquedas)"].mass_kg == pytest.approx(0.65)
    assert pm["Paraquedas A (paraquedas)"].position_m == pytest.approx(0.43)


RAIL_BUTTON_ORK_XML = """<?xml version='1.0' encoding='utf-8'?>
<openrocket version="1.9">
  <rocket>
    <name>Rail Button Rocket</name>
    <subcomponents>
      <stage>
        <name>Sustainer</name>
        <subcomponents>
          <bodytube>
            <name>Corpo</name>
            <length>1.00</length>
            <thickness>0.002</thickness>
            <radius>0.079</radius>
            <subcomponents>
              <railbutton>
                <name>Botao</name>
                <instancecount>2</instancecount>
                <instanceseparation>-0.50</instanceseparation>
                <axialoffset method="bottom">-0.10</axialoffset>
                <outerdiameter>0.04</outerdiameter>
                <innerdiameter>0.013</innerdiameter>
                <height>0.027</height>
                <baseheight>0.006</baseheight>
                <flangeheight>0.011</flangeheight>
                <material type="bulk" density="1050.0">ABS</material>
              </railbutton>
            </subcomponents>
          </bodytube>
        </subcomponents>
      </stage>
    </subcomponents>
  </rocket>
</openrocket>
"""

MOTOR_MOUNT_BODYTUBE_XML = """<?xml version='1.0' encoding='utf-8'?>
<openrocket version="1.9">
  <rocket>
    <name>Motor Mount Rocket</name>
    <subcomponents>
      <stage>
        <name>Sustainer</name>
        <subcomponents>
          <bodytube>
            <name>Propulsao</name>
            <length>1.00</length>
            <thickness>0.002</thickness>
            <radius>0.079</radius>
            <motormount>
              <overhang>0.0</overhang>
            </motormount>
          </bodytube>
          <bodytube>
            <name>Aletas</name>
            <length>0.40</length>
            <thickness>0.002</thickness>
            <radius>0.079</radius>
            <motormount>
              <overhang>-0.02</overhang>
              <motor configid="cfg-1" />
            </motormount>
          </bodytube>
        </subcomponents>
      </stage>
    </subcomponents>
  </rocket>
</openrocket>
"""


def test_parse_ork_rail_button_mass_uses_bobbin_volume_and_standoff_radius() -> None:
    parsed = parse_ork_bytes(RAIL_BUTTON_ORK_XML.encode("utf-8"))

    # Standoff (ork outerdiameter/2), never the body radius.
    assert parsed.radius_m == pytest.approx(0.079)
    assert parsed.rail_buttons.radius_m == pytest.approx(0.02)
    # bottom -0.10 => start = 1.00 - 0.10 - 0.027; second instance separated by -0.50.
    assert parsed.rail_buttons.upper_button_position_m == pytest.approx(0.373)
    assert parsed.rail_buttons.lower_button_position_m == pytest.approx(0.873)

    per_button_kg = (
        1050.0
        * math.pi
        * (
            0.02**2 * (0.011 + 0.006)  # flange + base standoff discs
            + 0.0065**2 * (0.027 - 0.006 - 0.011)  # shank
        )
    )
    buttons = {
        c.name: c
        for c in parsed.components
        if isinstance(c, PointMassComponent) and c.name.startswith("Botao")
    }
    assert set(buttons) == {"Botao #1", "Botao #2"}
    for button in buttons.values():
        assert button.mass_kg == pytest.approx(per_button_kg)
    assert buttons["Botao #1"].position_m == pytest.approx(0.873 + 0.014738, rel=1e-5)
    assert buttons["Botao #2"].position_m == pytest.approx(0.373 + 0.014738, rel=1e-5)


def test_parse_ork_detects_motormount_inside_bodytube_and_prefers_motor_bearing_mount() -> None:
    parsed = parse_ork_bytes(MOTOR_MOUNT_BODYTUBE_XML.encode("utf-8"))

    # Aft ends are 1.00 (Propulsao) and 1.40 (Aletas); only the mount holding <motor>
    # defines the motor station, shifted forward by its -0.02 m overhang.
    assert parsed.detected_motor_mount_position_m == pytest.approx(1.38)
