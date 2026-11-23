"""Pure-stdlib OpenRocket (.ork) ZIP/XML parser into typed Hefesto domain models."""

from __future__ import annotations

import hashlib
import io
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from hefesto.domain import (
    DragCurveTable,
    FinComponent,
    FinSetSpec,
    NoseConeKind,
    NoseConeSpec,
    OrkImportWarning,
    OrkParsedDesign,
    ParachuteSpec,
    PointMassComponent,
    RailButtonsSpec,
    RocketComponent,
    SurfaceFinish,
    TubeComponent,
)

_DEFAULT_TUBE_DENSITY_KG_M3 = 1850.0
_DEFAULT_RING_DENSITY_KG_M3 = 650.0
_DEFAULT_FIN_DENSITY_KG_M3 = 1850.0
_DEFAULT_FIN_THICKNESS_M = 0.003
_DEFAULT_RAIL_BUTTON_OUTER_DIAMETER_M = 0.04
_DEFAULT_RAIL_BUTTON_HEIGHT_M = 0.02
_DEFAULT_RAIL_BUTTON_DENSITY_KG_M3 = 1050.0

# OpenRocket finish levels collapsed onto the four-level Hefesto surface-finish scale.
_SURFACE_FINISH_BY_ORK: dict[str, SurfaceFinish] = {
    "polished": SurfaceFinish.SMOOTH,
    "smooth": SurfaceFinish.SMOOTH,
    "normal": SurfaceFinish.REGULAR,
    "rough": SurfaceFinish.ROUGH,
    "unfinished": SurfaceFinish.UNFINISHED,
}
_DRAG_TABLE_MACH_STEP = 0.01
_DRAG_TABLE_MIN_DATAPOINTS = 8
# The rest state (v ~ 0) has a degenerate Reynolds number and an unphysical Cd.
_DRAG_TABLE_MIN_MACH = 0.02

_UNSUPPORTED_COMPONENT_TAGS = frozenset(
    {
        "transition",
        "ellipticalfinset",
        "tubefinset",
        "podset",
        "shockcord",
        "streamer",
        "launchlug",
        "engineblock",
        "phantom",
    }
)


class OrkParseError(ValueError):
    """Raised when an OpenRocket (.ork) archive or XML payload is invalid or unsafe."""


def _validate_zip_member_name(member_name: str) -> None:
    if "\x00" in member_name:
        raise OrkParseError(f"Zip entry contains null byte: {member_name!r}")
    normalized = member_name.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized:
        raise OrkParseError(f"Unsafe absolute or drive path in .ork archive: {member_name!r}")
    if ".." in PurePosixPath(normalized).parts:
        raise OrkParseError(f"Zip slip path traversal detected in .ork archive: {member_name!r}")


def _extract_xml_and_rse(raw_bytes: bytes) -> tuple[bytes, tuple[str, ...]]:
    if not raw_bytes:
        raise OrkParseError("Arquivo .ork vazio.")

    if zipfile.is_zipfile(io.BytesIO(raw_bytes)):
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as archive:
                infos = archive.infolist()
                for info in infos:
                    _validate_zip_member_name(info.filename)

                rse_names = tuple(
                    sorted(
                        info.filename
                        for info in infos
                        if not info.is_dir() and info.filename.lower().endswith(".rse")
                    )
                )

                ork_candidates = [
                    info.filename
                    for info in infos
                    if not info.is_dir() and info.filename.lower() == "rocket.ork"
                ]
                if not ork_candidates:
                    ork_candidates = [
                        info.filename
                        for info in infos
                        if not info.is_dir() and info.filename.lower().endswith(".ork")
                    ]
                if not ork_candidates:
                    raise OrkParseError(
                        "Arquivo ZIP .ork não contém 'rocket.ork' nem arquivo XML .ork interno."
                    )

                xml_bytes = archive.read(ork_candidates[0])
                return xml_bytes, rse_names
        except zipfile.BadZipFile as exc:
            raise OrkParseError(f"Arquivo ZIP .ork corrompido: {exc}") from exc

    return raw_bytes, ()


def _parse_ork_dimension(
    elem: ET.Element,
    tag: str,
    default: float | None = None,
) -> tuple[bool, float | None]:
    """Parse an OpenRocket dimension tag supporting '0.079', 'auto', and 'auto 0.079'."""
    child = elem.find(tag)
    if child is None or child.text is None:
        return False, default
    raw = child.text.strip()
    if not raw:
        return False, default
    parts = raw.split()
    if parts[0].lower() == "auto":
        if len(parts) == 1:
            return True, None
        if len(parts) == 2:
            try:
                val = float(parts[1])
            except ValueError as exc:
                raise OrkParseError(f"Valor numérico inválido em <{tag}>: {raw!r}") from exc
            if not math.isfinite(val):
                raise OrkParseError(f"Valor não finito em <{tag}>: {raw!r}")
            return True, val
        raise OrkParseError(f"Valor numérico inválido em <{tag}>: {raw!r}")
    try:
        val = float(raw)
    except ValueError as exc:
        raise OrkParseError(f"Valor numérico inválido em <{tag}>: {raw!r}") from exc
    if not math.isfinite(val):
        raise OrkParseError(f"Valor não finito em <{tag}>: {raw!r}")
    return False, val


def _float_text(elem: ET.Element, tag: str, default: float | None = None) -> float | None:
    _, value = _parse_ork_dimension(elem, tag, default)
    return value


def _resolve_ork_radius(
    elem: ET.Element,
    tags: tuple[str, ...],
    *,
    inherited_radius_m: float | None,
    comp_name: str,
    warnings: list[OrkImportWarning],
    fallback_radius_m: float | None = None,
    allow_zero: bool = False,
) -> float | None:
    """Resolve explicit or 'auto [value]' radius with parent inheritance and warning fallback."""
    min_val = 0.0 if allow_zero else 1e-9
    for tag in tags:
        if elem.find(tag) is None:
            continue
        is_auto, explicit_val = _parse_ork_dimension(elem, tag, None)
        if not is_auto:
            if explicit_val is not None and explicit_val >= min_val:
                return explicit_val
            continue
        if inherited_radius_m is not None and inherited_radius_m >= min_val:
            return inherited_radius_m
        if explicit_val is not None and explicit_val >= min_val:
            return explicit_val
        warnings.append(
            OrkImportWarning(
                severity="warning",
                component_name=comp_name,
                message=(
                    f"Dimensão <{tag}> em modo 'auto' sem componente pai nem valor numérico; "
                    "aplicado fallback."
                ),
            )
        )
        return fallback_radius_m
    return fallback_radius_m


def _component_name(elem: ET.Element, fallback: str) -> str:
    raw = elem.findtext("name")
    if raw is not None and raw.strip():
        return raw.strip()
    return fallback


def _material_density(
    elem: ET.Element,
    default_density: float,
    comp_name: str,
    warnings: list[OrkImportWarning],
) -> float:
    mat = elem.find("material")
    if mat is not None:
        raw_density = mat.attrib.get("density")
        if raw_density is not None:
            try:
                val = float(raw_density)
                if math.isfinite(val) and val > 0.0:
                    return val
            except ValueError:
                pass
    warnings.append(
        OrkImportWarning(
            severity="info",
            component_name=comp_name,
            message=(
                "Densidade de material ausente; aplicada densidade padrão "
                f"{default_density:.1f} kg/m³."
            ),
        )
    )
    return default_density


def _read_axial_offset(elem: ET.Element, default_method: str) -> tuple[str, float]:
    axial = elem.find("axialoffset")
    if axial is not None:
        method = axial.attrib.get("method", default_method).strip().lower()
        raw = (axial.text or "0.0").strip()
        return method, float(raw) if raw else 0.0
    pos = elem.find("position")
    if pos is not None:
        method = pos.attrib.get("type", default_method).strip().lower()
        raw = (pos.text or "0.0").strip()
        return method, float(raw) if raw else 0.0
    return default_method, 0.0


def _resolve_start_m(
    *,
    method: str,
    offset_m: float,
    comp_length_m: float,
    cursor_m: float,
    parent_start_m: float,
    parent_length_m: float,
    is_sequential: bool,
) -> float:
    if method == "absolute":
        start = offset_m
    elif method == "top":
        start = parent_start_m + offset_m
    elif method == "middle":
        start = parent_start_m + (parent_length_m / 2.0) + offset_m - (comp_length_m / 2.0)
    elif method == "bottom":
        start = parent_start_m + parent_length_m + offset_m - comp_length_m
    elif method == "after":
        start = cursor_m + offset_m if is_sequential else parent_start_m + offset_m
    else:
        start = cursor_m if is_sequential else parent_start_m + offset_m
    return max(0.0, start)


def _read_instances(elem: ET.Element) -> tuple[int, float]:
    raw_count = _float_text(elem, "instancecount", 1.0)
    count = max(1, round(raw_count if raw_count is not None else 1.0))
    sep = _float_text(elem, "instanceseparation", 0.0) or 0.0
    return count, sep


def _first_positive_dimension(elem: ET.Element, tags: tuple[str, ...], default: float) -> float:
    """Return the first positive numeric value among tags, tolerating 'auto' and absence."""
    for tag in tags:
        if elem.find(tag) is None:
            continue
        _, value = _parse_ork_dimension(elem, tag, None)
        if value is not None and value > 0.0:
            return value
    return default


@dataclass(frozen=True)
class _RailButtonGeometry:
    """Rail button height, lumped mass, and CG offset from its forward face."""

    height_m: float
    mass_kg: float
    cg_from_start_m: float


def _read_rail_button_geometry(
    elem: ET.Element,
    comp_name: str,
    warnings: list[OrkImportWarning],
) -> _RailButtonGeometry:
    """Derive rail button volume/CG with OpenRocket's bobbin profile (flange + shank + base)."""
    outer_d = _first_positive_dimension(
        elem, ("outerdiameter",), _DEFAULT_RAIL_BUTTON_OUTER_DIAMETER_M
    )
    inner_d = _first_positive_dimension(elem, ("innerdiameter",), 0.0)
    height_m = _first_positive_dimension(
        elem, ("height", "length"), _DEFAULT_RAIL_BUTTON_HEIGHT_M
    )
    base_h = _first_positive_dimension(elem, ("baseheight",), 0.0)
    flange_h = _first_positive_dimension(elem, ("flangeheight",), 0.0)
    screw_h = _first_positive_dimension(elem, ("screwheight",), 0.0)
    if base_h + flange_h <= 0.0:
        # OpenRocket heights absent: degenerate profile is a solid standoff cylinder.
        base_h = height_m
    inner_h = max(0.0, height_m - base_h - flange_h)
    r_out = outer_d / 2.0
    r_in = inner_d / 2.0
    volume_m3 = math.pi * (
        r_out**2 * (flange_h + base_h) + r_in**2 * inner_h + (2.0 / 3.0) * r_out**2 * screw_h
    )
    density = _material_density(elem, _DEFAULT_RAIL_BUTTON_DENSITY_KG_M3, comp_name, warnings)
    # Section weights are volumes/pi; ORK CG sections: base, shank, flange, screw tip.
    sections = (
        (r_out**2 * base_h, base_h / 2.0),
        (r_in**2 * inner_h, base_h + inner_h / 2.0),
        (r_out**2 * flange_h, height_m - flange_h / 2.0),
        ((2.0 / 3.0) * r_out**2 * screw_h, height_m + 4.0 * screw_h / (3.0 * math.pi)),
    )
    weight_sum = sum(weight for weight, _ in sections)
    cg_from_start_m = (
        sum(weight * station for weight, station in sections) / weight_sum
        if weight_sum > 0.0
        else height_m / 2.0
    )
    return _RailButtonGeometry(
        height_m=height_m,
        mass_kg=volume_m3 * density,
        cg_from_start_m=cg_from_start_m,
    )


def _read_motor_mount_station(
    mount: ET.Element,
    *,
    comp_start_m: float,
    comp_length_m: float,
) -> tuple[float, bool]:
    """Return (motor nozzle station, mount carries a <motor>) for one <motormount>."""
    overhang_m = _float_text(mount, "overhang", 0.0) or 0.0
    has_motor = mount.find("motor") is not None
    return max(0.0, comp_start_m + comp_length_m + overhang_m), has_motor


def _check_overrides(
    elem: ET.Element,
    comp_name: str,
    warnings: list[OrkImportWarning],
) -> bool:
    found = False
    for tag in (
        "overridemass",
        "overridecg",
        "overridesubcomponentsmass",
        "overridesubcomponentscg",
    ):
        child = elem.find(tag)
        if child is None or child.text is None:
            continue
        text = child.text.strip().lower()
        if not text or text == "false":
            continue
        found = True
        warnings.append(
            OrkImportWarning(
                severity="warning",
                component_name=comp_name,
                message=(
                    f"Override OpenRocket detectado (<{tag}>{child.text.strip()}</{tag}>). "
                    "Confira massa/CG calculados na aba Configuração."
                ),
            )
        )
    return found


def _map_nose_shape(
    elem: ET.Element,
    comp_name: str,
    warnings: list[OrkImportWarning],
) -> tuple[NoseConeKind, float | None, float | None]:
    """Return (kind, power, haack C) preserving the OpenRocket shape parameter."""
    raw_shape = (elem.findtext("shape") or "ogive").strip().lower()
    shape_param = _float_text(elem, "shapeparameter", None)
    if raw_shape == "ogive":
        return NoseConeKind.OGIVE, None, None
    if raw_shape == "conical":
        return NoseConeKind.CONICAL, None, None
    if raw_shape == "power":
        power = shape_param if shape_param is not None and shape_param > 0.0 else 0.5
        return NoseConeKind.POWERSERIES, power, None
    if raw_shape in {"haack", "lvhaack"}:
        # OpenRocket's Haack series: C=0 is Von Karman, C=1/3 is LV-Haack.
        default_c = 1.0 / 3.0 if raw_shape == "lvhaack" else 0.0
        c_param = shape_param if shape_param is not None else default_c
        if abs(c_param) < 1e-9:
            return NoseConeKind.VON_KARMAN, None, c_param
        if abs(c_param - 1.0 / 3.0) <= 1e-3:
            return NoseConeKind.LV_HAACK, None, c_param
        warnings.append(
            OrkImportWarning(
                severity="warning",
                component_name=comp_name,
                message=(
                    f"Parâmetro Haack C={c_param:g} preservado na geometria analítica; "
                    "RocketPy voa o perfil LV-Haack (C=1/3) mais próximo."
                ),
            )
        )
        return NoseConeKind.LV_HAACK, None, c_param

    warnings.append(
        OrkImportWarning(
            severity="warning",
            component_name=comp_name,
            message=(
                f"Formato de ogiva '{raw_shape}' não possui mapeamento direto; "
                "aplicado fallback 'ogive'."
            ),
        )
    )
    return NoseConeKind.OGIVE, None, None


def _read_mass_cg_override(
    elem: ET.Element,
) -> tuple[float | None, float | None]:
    """Return (overridemass kg, overridecg m from component front) when present."""
    raw_mass = _float_text(elem, "overridemass", None)
    mass_kg = raw_mass if raw_mass is not None and raw_mass > 0.0 else None
    raw_cg = _float_text(elem, "overridecg", None)
    cg_from_front_m = max(0.0, raw_cg) if raw_cg is not None else None
    return mass_kg, cg_from_front_m


def _build_fin_specs(
    elem: ET.Element,
    *,
    start_m: float,
    parent_outer_radius_m: float,
    warnings: list[OrkImportWarning],
) -> tuple[FinSetSpec, FinComponent]:
    tag = elem.tag.lower()
    comp_name = _component_name(elem, "Fins")
    fincount = max(1, round(_float_text(elem, "fincount", 3.0) or 3.0))
    cant_deg = _float_text(elem, "cant", 0.0) or 0.0
    cant_deg = max(-45.0, min(45.0, cant_deg))
    thickness_m = (
        _float_text(elem, "thickness", _DEFAULT_FIN_THICKNESS_M) or _DEFAULT_FIN_THICKNESS_M
    )
    if thickness_m <= 0.0:
        thickness_m = _DEFAULT_FIN_THICKNESS_M
    density = _material_density(elem, _DEFAULT_FIN_DENSITY_KG_M3, comp_name, warnings)

    root_chord: float | None = None
    tip_chord: float | None = None
    span: float | None = None
    sweep: float | None = None

    if tag == "trapezoidfinset":
        root_chord = max(0.01, _float_text(elem, "rootchord", 0.15) or 0.15)
        tip_chord = max(0.0, _float_text(elem, "tipchord", 0.08) or 0.08)
        span = max(0.005, _float_text(elem, "height", 0.10) or 0.10)
        sweep = _float_text(elem, "sweeplength", 0.0) or 0.0
        shape_points: tuple[tuple[float, float], ...] = (
            (0.0, 0.0),
            (sweep, span),
            (sweep + tip_chord, span),
            (root_chord, 0.0),
        )
    else:
        raw_pts: list[tuple[float, float]] = []
        finpoints = elem.find("finpoints")
        if finpoints is not None:
            for pt in finpoints.findall("point"):
                x_val = float(pt.attrib.get("x", "0.0"))
                y_val = float(pt.attrib.get("y", "0.0"))
                if math.isfinite(x_val) and math.isfinite(y_val):
                    raw_pts.append((x_val, y_val))
        if len(raw_pts) < 3:
            warnings.append(
                OrkImportWarning(
                    severity="warning",
                    component_name=comp_name,
                    message=(
                        "Freeform finset com menos de 3 pontos válidos; "
                        "aplicado polígono fallback."
                    ),
                )
            )
            shape_points = ((0.0, 0.0), (0.04, 0.08), (0.12, 0.08), (0.15, 0.0))
        else:
            shape_points = tuple(raw_pts)

    fin_set = FinSetSpec(
        name=comp_name,
        count=fincount,
        position_m=start_m,
        shape_points_m=shape_points,
        cant_angle_deg=cant_deg,
        radius_m=parent_outer_radius_m,
        root_chord_m=root_chord,
        tip_chord_m=tip_chord,
        span_m=span,
        sweep_length_m=sweep,
    )
    fin_comp = FinComponent(
        name=comp_name,
        count=fincount,
        shape_points_m=shape_points,
        thickness_m=thickness_m,
        density_kg_m3=density,
        position_m=start_m,
    )
    return fin_set, fin_comp


def _infer_stage_radius_m(stage_subcomponents: ET.Element | None) -> float:
    if stage_subcomponents is None:
        return 0.05
    for child in stage_subcomponents:
        tag = child.tag.lower()
        if tag == "bodytube":
            r = _float_text(child, "radius") or _float_text(child, "outerradius")
            if r is not None and r > 0.0:
                return r
        elif tag == "nosecone":
            r = _float_text(child, "aftradius") or _float_text(child, "radius")
            if r is not None and r > 0.0:
                return r
    return 0.05


def _read_surface_finish(rocket_elem: ET.Element) -> SurfaceFinish:
    """Map the dominant OpenRocket <finish> (airframe first, then nose) onto the domain scale."""
    for tag in ("bodytube", "nosecone"):
        for element in rocket_elem.iter(tag):
            raw = (element.findtext("finish") or "").strip().lower()
            if raw:
                return _SURFACE_FINISH_BY_ORK.get(raw, SurfaceFinish.REGULAR)
    return SurfaceFinish.REGULAR


def _interpolate_curve(mach: float, curve: list[tuple[float, float]]) -> float:
    """Linear interpolation over a strictly increasing curve with constant extrapolation."""
    if mach <= curve[0][0]:
        return curve[0][1]
    for (mach_lo, cd_lo), (mach_hi, cd_hi) in zip(curve, curve[1:], strict=False):
        if mach <= mach_hi:
            if mach_hi <= mach_lo:
                return cd_hi
            return cd_lo + (cd_hi - cd_lo) * (mach - mach_lo) / (mach_hi - mach_lo)
    return curve[-1][1]


def _phase_drag_curve(
    samples: list[tuple[float, float, float, float]],
    *,
    powered: bool,
) -> list[tuple[float, float]]:
    """Collapse one flight phase into a strictly increasing (mach, cd) curve."""
    points = sorted((mach, cd) for _time, mach, cd, thrust in samples if (thrust > 0.0) is powered)
    merged: list[tuple[float, float]] = []
    for mach, cd in points:
        if merged and abs(mach - merged[-1][0]) <= 1e-6:
            previous_mach, previous_cd = merged[-1]
            merged[-1] = (previous_mach, 0.5 * (previous_cd + cd))
        else:
            merged.append((mach, cd))
    return merged


def _flight_apogee_time(flightdata: ET.Element, databranch: ET.Element) -> float | None:
    """Return the OpenRocket apogee event time, else the time of maximum altitude."""
    for event in databranch.findall("event"):
        if (event.attrib.get("type") or "").strip().lower() == "apogee":
            try:
                return float(event.attrib.get("time", ""))
            except ValueError:
                break
    best_time: float | None = None
    best_altitude = -math.inf
    types = (databranch.attrib.get("types") or "").split(",")
    if "altitude" in types:
        alt_index = types.index("altitude")
        time_index = types.index("time") if "time" in types else None
        for datapoint in databranch.findall("datapoint"):
            values = _datapoint_values(datapoint)
            if values is None or alt_index >= len(values):
                continue
            altitude = values[alt_index]
            if not math.isfinite(altitude) or altitude < best_altitude:
                continue
            best_altitude = altitude
            if time_index is not None and time_index < len(values):
                best_time = values[time_index]
    return best_time


def _datapoint_values(datapoint: ET.Element) -> list[float] | None:
    if datapoint.text is None:
        return None
    try:
        return [float(token) for token in datapoint.text.split(",")]
    except ValueError:
        return None


def _extract_flight_drag_table(
    root: ET.Element,
    warnings: list[OrkImportWarning],
) -> DragCurveTable | None:
    """Extract power_off/power_on Cd(Mach) from embedded <flightdata> datapoints."""
    flightdatas = root.findall(".//flightdata")
    if len(flightdatas) > 1:
        warnings.append(
            OrkImportWarning(
                severity="info",
                component_name="Simulações Salvas (.ork)",
                message=(
                    f"Detectadas {len(flightdatas)} simulações de voo; a primeira com "
                    "datapoints Mach/CD foi usada como curva ork_sim."
                ),
            )
        )

    for flightdata in flightdatas:
        branches = [*flightdata.findall("databranch"), *flightdata.findall("branch")]
        for databranch in branches:
            types = [token.strip() for token in (databranch.attrib.get("types") or "").split(",")]
            datapoints = databranch.findall("datapoint")
            if len(datapoints) < _DRAG_TABLE_MIN_DATAPOINTS:
                continue
            if not {"mach_number", "drag_coeff", "thrust_force"}.issubset(types):
                continue

            mach_index = types.index("mach_number")
            cd_index = types.index("drag_coeff")
            thrust_index = types.index("thrust_force")
            time_index = types.index("time") if "time" in types else None
            apogee_time = _flight_apogee_time(flightdata, databranch)

            samples: list[tuple[float, float, float, float]] = []
            for position, datapoint in enumerate(datapoints):
                values = _datapoint_values(datapoint)
                if values is None or max(mach_index, cd_index, thrust_index) >= len(values):
                    continue
                mach = values[mach_index]
                cd = values[cd_index]
                thrust = values[thrust_index]
                if not all(math.isfinite(value) for value in (mach, cd, thrust)):
                    continue
                if mach < _DRAG_TABLE_MIN_MACH or cd < 0.0:
                    continue
                time_s = (
                    values[time_index]
                    if time_index is not None and time_index < len(values)
                    else float(position)
                )
                if not math.isfinite(time_s):
                    continue
                if apogee_time is not None and time_s > apogee_time + 1e-9:
                    continue
                samples.append((time_s, mach, cd, thrust))

            power_off = _phase_drag_curve(samples, powered=False)
            power_on = _phase_drag_curve(samples, powered=True)
            if len(power_off) < 2 or len(power_on) < 2:
                warnings.append(
                    OrkImportWarning(
                        severity="warning",
                        component_name="Aerodinâmica (Cd)",
                        message=(
                            "Datapoints de voo sem amostras das fases com e sem empuxo; "
                            "a curva ork_sim não foi extraída."
                        ),
                    )
                )
                continue

            max_mach = max(power_off[-1][0], power_on[-1][0])
            steps = round(max_mach / _DRAG_TABLE_MACH_STEP)
            grid = [round(index * _DRAG_TABLE_MACH_STEP, 10) for index in range(steps + 1)]
            return DragCurveTable(
                mach=grid,
                cd_power_off=[_interpolate_curve(mach, power_off) for mach in grid],
                cd_power_on=[_interpolate_curve(mach, power_on) for mach in grid],
                source="ork_sim",
            )

    return None


def parse_ork_bytes(raw_bytes: bytes) -> OrkParsedDesign:
    """Parse OpenRocket (.ork) bytes (ZIP or plain XML) into an OrkParsedDesign."""
    source_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    xml_bytes, embedded_rse_names = _extract_xml_and_rse(raw_bytes)

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise OrkParseError(f"XML interno do .ork malformado: {exc}") from exc

    if root.tag.lower() != "openrocket":
        raise OrkParseError(f"Raiz XML inválida: esperado <openrocket>, obtido <{root.tag}>.")

    stored_datapoint_count = len(root.findall(".//datapoint"))
    rocket_elem = root.find("rocket")
    if rocket_elem is None:
        raise OrkParseError("Elemento <rocket> ausente no XML do OpenRocket.")

    rocket_name = _component_name(rocket_elem, "OpenRocket Imported")
    warnings: list[OrkImportWarning] = []
    if embedded_rse_names:
        warnings.append(
            OrkImportWarning(
                severity="info",
                component_name="Motores (.rse)",
                message=(
                    f"Detectadas {len(embedded_rse_names)} curva(s) .rse embutida(s): "
                    f"{', '.join(embedded_rse_names)}."
                ),
            )
        )

    components: list[RocketComponent] = []
    fin_sets: list[FinSetSpec] = []
    parachutes: list[ParachuteSpec] = []
    rail_button_positions: list[float] = []
    nose_cones: list[NoseConeSpec] = []
    nose_cone_meta: dict[str, float | None] = {
        "thickness_m": None,
        "density_kg_m3": None,
        "override_mass_kg": None,
        "override_cg_m": None,
    }
    detected_motor_mount_pos: float | None = None
    motor_mount_is_explicit = False
    has_overrides = _check_overrides(rocket_elem, rocket_name, warnings)

    rocket_sub = rocket_elem.find("subcomponents")
    stages = rocket_sub.findall("stage") if rocket_sub is not None else []
    if not stages:
        raise OrkParseError("Nenhum <stage> encontrado em <rocket><subcomponents>.")

    if len(stages) > 1:
        warnings.append(
            OrkImportWarning(
                severity="warning",
                component_name=rocket_name,
                message=(
                    f"Foguete possui {len(stages)} estágios; "
                    "apenas o primeiro estágio foi importado."
                ),
            )
        )

    primary_stage = stages[0]
    stage_sub = primary_stage.find("subcomponents")
    stage_radius_m = _infer_stage_radius_m(stage_sub)
    max_body_radius_m = stage_radius_m
    rail_button_radii_m: list[float] = []

    def walk_subcomponents(
        sub_elem: ET.Element | None,
        *,
        parent_start_m: float,
        parent_length_m: float,
        parent_outer_radius_m: float,
        parent_inner_radius_m: float,
        has_physical_parent: bool,
        is_sequential: bool,
    ) -> None:
        nonlocal detected_motor_mount_pos, has_overrides, max_body_radius_m
        nonlocal motor_mount_is_explicit
        if sub_elem is None:
            return

        def record_motor_mount(elem: ET.Element, start_m: float, length_m: float) -> None:
            """Record the mount station; a mount holding <motor> outranks loose mounts."""
            nonlocal detected_motor_mount_pos, motor_mount_is_explicit
            for mount in elem.findall("motormount"):
                station_m, carries_motor = _read_motor_mount_station(
                    mount, comp_start_m=start_m, comp_length_m=length_m
                )
                if carries_motor or not motor_mount_is_explicit:
                    detected_motor_mount_pos = station_m
                    motor_mount_is_explicit = carries_motor

        cursor_m = parent_start_m
        for child in sub_elem:
            tag = child.tag.lower()
            comp_name = _component_name(child, tag)
            if _check_overrides(child, comp_name, warnings):
                has_overrides = True

            default_method = "after" if is_sequential else "top"
            method, offset_m = _read_axial_offset(child, default_method)

            if tag == "nosecone":
                length_m = max(0.01, _float_text(child, "length", 0.30) or 0.30)
                aft_r = _resolve_ork_radius(
                    child,
                    ("aftradius", "radius"),
                    inherited_radius_m=parent_outer_radius_m if has_physical_parent else None,
                    comp_name=comp_name,
                    warnings=warnings,
                    fallback_radius_m=stage_radius_m,
                )
                if aft_r is None or aft_r <= 0.0:
                    aft_r = stage_radius_m
                max_body_radius_m = max(max_body_radius_m, aft_r)
                start_m = _resolve_start_m(
                    method=method,
                    offset_m=offset_m,
                    comp_length_m=length_m,
                    cursor_m=cursor_m,
                    parent_start_m=parent_start_m,
                    parent_length_m=parent_length_m,
                    is_sequential=is_sequential,
                )
                kind, power, haack_parameter = _map_nose_shape(child, comp_name, warnings)
                nose_cones.append(
                    NoseConeSpec(
                        name=comp_name,
                        length_m=length_m,
                        kind=kind,
                        position_m=start_m,
                        power=power,
                        haack_parameter=haack_parameter,
                        base_radius_m=aft_r,
                    )
                )
                thickness_m = max(0.0, _float_text(child, "thickness", 0.003) or 0.003)
                nose_density = _material_density(
                    child, _DEFAULT_TUBE_DENSITY_KG_M3, comp_name, warnings
                )
                if len(nose_cones) == 1:
                    nose_override_mass = _float_text(child, "overridemass", None)
                    nose_override_cg_local = _float_text(child, "overridecg", None)
                    nose_cone_meta["thickness_m"] = thickness_m
                    nose_cone_meta["density_kg_m3"] = nose_density
                    nose_cone_meta["override_mass_kg"] = (
                        nose_override_mass
                        if nose_override_mass is not None and nose_override_mass > 0.0
                        else None
                    )
                    nose_cone_meta["override_cg_m"] = (
                        max(0.0, start_m + nose_override_cg_local)
                        if nose_override_cg_local is not None
                        else None
                    )
                walk_subcomponents(
                    child.find("subcomponents"),
                    parent_start_m=start_m,
                    parent_length_m=length_m,
                    parent_outer_radius_m=aft_r,
                    parent_inner_radius_m=max(0.001, aft_r - thickness_m),
                    has_physical_parent=True,
                    is_sequential=False,
                )
                if is_sequential:
                    cursor_m = start_m + length_m

            elif tag == "bodytube":
                length_m = max(0.005, _float_text(child, "length", 0.20) or 0.20)
                outer_r = _resolve_ork_radius(
                    child,
                    ("radius", "outerradius"),
                    inherited_radius_m=parent_outer_radius_m if has_physical_parent else None,
                    comp_name=comp_name,
                    warnings=warnings,
                    fallback_radius_m=stage_radius_m,
                )
                if outer_r is None or outer_r <= 0.0:
                    outer_r = stage_radius_m
                max_body_radius_m = max(max_body_radius_m, outer_r)
                thickness_m = _float_text(child, "thickness", 0.002) or 0.002
                thickness_m = min(max(1e-4, thickness_m), outer_r)
                density = _material_density(child, _DEFAULT_TUBE_DENSITY_KG_M3, comp_name, warnings)
                start_m = _resolve_start_m(
                    method=method,
                    offset_m=offset_m,
                    comp_length_m=length_m,
                    cursor_m=cursor_m,
                    parent_start_m=parent_start_m,
                    parent_length_m=parent_length_m,
                    is_sequential=is_sequential,
                )
                mass_override_kg, cg_from_front_m = _read_mass_cg_override(child)
                components.append(
                    TubeComponent(
                        name=comp_name,
                        outer_radius_m=outer_r,
                        wall_thickness_m=thickness_m,
                        length_m=length_m,
                        density_kg_m3=density,
                        position_m=start_m + length_m / 2.0,
                        mass_override_kg=mass_override_kg,
                        cg_override_m=(
                            start_m + cg_from_front_m
                            if mass_override_kg is not None and cg_from_front_m is not None
                            else None
                        ),
                    )
                )
                record_motor_mount(child, start_m, length_m)
                walk_subcomponents(
                    child.find("subcomponents"),
                    parent_start_m=start_m,
                    parent_length_m=length_m,
                    parent_outer_radius_m=outer_r,
                    parent_inner_radius_m=max(0.001, outer_r - thickness_m),
                    has_physical_parent=True,
                    is_sequential=False,
                )
                if is_sequential:
                    cursor_m = start_m + length_m

            elif tag in {"tubecoupler", "innertube"}:
                length_m = max(0.005, _float_text(child, "length", 0.10) or 0.10)
                default_inner = (
                    parent_inner_radius_m
                    if tag == "tubecoupler"
                    else max(0.005, parent_inner_radius_m * 0.5)
                )
                outer_r = _resolve_ork_radius(
                    child,
                    ("outerradius",),
                    inherited_radius_m=(
                        parent_inner_radius_m
                        if (has_physical_parent and tag == "tubecoupler")
                        else None
                    ),
                    comp_name=comp_name,
                    warnings=warnings,
                    fallback_radius_m=default_inner,
                )
                if outer_r is None or outer_r <= 0.0:
                    outer_r = default_inner
                thickness_m = _float_text(child, "thickness", None)
                if thickness_m is None:
                    inner_r = _resolve_ork_radius(
                        child,
                        ("innerradius",),
                        inherited_radius_m=None,
                        comp_name=comp_name,
                        warnings=warnings,
                        fallback_radius_m=None,
                        allow_zero=True,
                    )
                    if inner_r is not None and 0.0 <= inner_r < outer_r:
                        thickness_m = outer_r - inner_r
                    else:
                        thickness_m = min(0.002, outer_r)
                thickness_m = min(max(1e-4, thickness_m), outer_r)
                density = _material_density(child, _DEFAULT_TUBE_DENSITY_KG_M3, comp_name, warnings)
                base_start = _resolve_start_m(
                    method=method,
                    offset_m=offset_m,
                    comp_length_m=length_m,
                    cursor_m=cursor_m,
                    parent_start_m=parent_start_m,
                    parent_length_m=parent_length_m,
                    is_sequential=False,
                )
                count, sep = _read_instances(child)
                mass_override_kg, cg_from_front_m = _read_mass_cg_override(child)
                for idx in range(count):
                    inst_start = max(0.0, base_start + idx * sep)
                    inst_name = comp_name if count == 1 else f"{comp_name} #{idx + 1}"
                    components.append(
                        TubeComponent(
                            name=inst_name,
                            outer_radius_m=outer_r,
                            wall_thickness_m=thickness_m,
                            length_m=length_m,
                            density_kg_m3=density,
                            position_m=inst_start + length_m / 2.0,
                            mass_override_kg=mass_override_kg,
                            cg_override_m=(
                                inst_start + cg_from_front_m
                                if mass_override_kg is not None
                                and cg_from_front_m is not None
                                else None
                            ),
                        )
                    )
                    record_motor_mount(child, inst_start, length_m)
                    walk_subcomponents(
                        child.find("subcomponents"),
                        parent_start_m=inst_start,
                        parent_length_m=length_m,
                        parent_outer_radius_m=outer_r,
                        parent_inner_radius_m=max(0.001, outer_r - thickness_m),
                        has_physical_parent=True,
                        is_sequential=False,
                    )

            elif tag in {"centeringring", "bulkhead"}:
                length_m = max(
                    0.001,
                    _float_text(child, "length") or _float_text(child, "thickness") or 0.005,
                )
                outer_r = _resolve_ork_radius(
                    child,
                    ("outerradius",),
                    inherited_radius_m=parent_inner_radius_m if has_physical_parent else None,
                    comp_name=comp_name,
                    warnings=warnings,
                    fallback_radius_m=parent_inner_radius_m,
                )
                if outer_r is None or outer_r <= 0.0:
                    outer_r = parent_inner_radius_m
                if tag == "bulkhead":
                    inner_r = 0.0
                else:
                    raw_inner = _resolve_ork_radius(
                        child,
                        ("innerradius",),
                        inherited_radius_m=None,
                        comp_name=comp_name,
                        warnings=warnings,
                        fallback_radius_m=None,
                        allow_zero=True,
                    )
                    inner_r = (
                        raw_inner
                        if raw_inner is not None and 0.0 <= raw_inner < outer_r
                        else max(0.0, outer_r * 0.5)
                    )
                wall_thickness = outer_r - inner_r
                if wall_thickness <= 1e-6:
                    wall_thickness = outer_r
                density = _material_density(child, _DEFAULT_RING_DENSITY_KG_M3, comp_name, warnings)
                base_start = _resolve_start_m(
                    method=method,
                    offset_m=offset_m,
                    comp_length_m=length_m,
                    cursor_m=cursor_m,
                    parent_start_m=parent_start_m,
                    parent_length_m=parent_length_m,
                    is_sequential=False,
                )
                count, sep = _read_instances(child)
                mass_override_kg, cg_from_front_m = _read_mass_cg_override(child)
                for idx in range(count):
                    inst_start = max(0.0, base_start + idx * sep)
                    inst_name = comp_name if count == 1 else f"{comp_name} #{idx + 1}"
                    components.append(
                        TubeComponent(
                            name=inst_name,
                            outer_radius_m=outer_r,
                            wall_thickness_m=wall_thickness,
                            length_m=length_m,
                            density_kg_m3=density,
                            position_m=inst_start + length_m / 2.0,
                            mass_override_kg=mass_override_kg,
                            cg_override_m=(
                                inst_start + cg_from_front_m
                                if mass_override_kg is not None
                                and cg_from_front_m is not None
                                else None
                            ),
                        )
                    )

            elif tag == "masscomponent":
                length_m = max(0.0, _float_text(child, "length", 0.02) or 0.02)
                mass_kg = _float_text(child, "mass") or _float_text(child, "packedmass") or 0.0
                base_start = _resolve_start_m(
                    method=method,
                    offset_m=offset_m,
                    comp_length_m=length_m,
                    cursor_m=cursor_m,
                    parent_start_m=parent_start_m,
                    parent_length_m=parent_length_m,
                    is_sequential=False,
                )
                if mass_kg <= 0.0:
                    warnings.append(
                        OrkImportWarning(
                            severity="warning",
                            component_name=comp_name,
                            message="MassComponent com massa <= 0 kg ignorado.",
                        )
                    )
                    continue
                count, sep = _read_instances(child)
                for idx in range(count):
                    inst_start = max(0.0, base_start + idx * sep)
                    inst_name = comp_name if count == 1 else f"{comp_name} #{idx + 1}"
                    components.append(
                        PointMassComponent(
                            name=inst_name,
                            mass_kg=mass_kg,
                            position_m=inst_start + length_m / 2.0,
                        )
                    )

            elif tag in {"trapezoidfinset", "freeformfinset"}:
                fin_len = _float_text(child, "rootchord", 0.15) or 0.15
                start_m = _resolve_start_m(
                    method=method,
                    offset_m=offset_m,
                    comp_length_m=fin_len,
                    cursor_m=cursor_m,
                    parent_start_m=parent_start_m,
                    parent_length_m=parent_length_m,
                    is_sequential=False,
                )
                fin_set, fin_comp = _build_fin_specs(
                    child,
                    start_m=start_m,
                    parent_outer_radius_m=parent_outer_radius_m,
                    warnings=warnings,
                )
                fin_sets.append(fin_set)
                components.append(fin_comp)

            elif tag == "parachute":
                diameter_m = max(0.05, _float_text(child, "diameter", 1.0) or 1.0)
                cd = max(0.05, _float_text(child, "cd", 0.8) or 0.8)
                cd_s_m2 = cd * math.pi * ((diameter_m / 2.0) ** 2)
                deploy_event = (child.findtext("deployevent") or "apogee").strip().lower()
                if deploy_event == "apogee":
                    trigger: str | float = "apogee"
                elif deploy_event == "altitude":
                    alt = _float_text(child, "deployaltitude", 300.0) or 300.0
                    trigger = alt if alt > 0.0 else 300.0
                else:
                    trigger = "apogee"
                    warnings.append(
                        OrkImportWarning(
                            severity="warning",
                            component_name=comp_name,
                            message=(
                                f"Evento de abertura '{deploy_event}' aproximado para 'apogee'."
                            ),
                        )
                    )
                lag_s = max(0.0, _float_text(child, "deploydelay", 0.0) or 0.0)
                parachutes.append(
                    ParachuteSpec(
                        name=comp_name,
                        cd_s_m2=cd_s_m2,
                        trigger="apogee" if trigger == "apogee" else float(trigger),
                        lag_s=lag_s,
                        radius_m=diameter_m / 2.0,
                    )
                )
                packed_len = max(0.0, _float_text(child, "packedlength", 0.0) or 0.0)
                chute_start_m = _resolve_start_m(
                    method=method,
                    offset_m=offset_m,
                    comp_length_m=packed_len,
                    cursor_m=cursor_m,
                    parent_start_m=parent_start_m,
                    parent_length_m=parent_length_m,
                    is_sequential=False,
                )
                chute_mass_kg = _float_text(child, "overridemass", None)
                if chute_mass_kg is None or chute_mass_kg <= 0.0:
                    mat = child.find("material")
                    surf_density = 0.0
                    if mat is not None and mat.attrib.get("density"):
                        try:
                            surf_density = max(0.0, float(mat.attrib["density"]))
                        except ValueError:
                            surf_density = 0.0
                    canopy_area = math.pi * ((diameter_m / 2.0) ** 2)
                    line_count = max(0.0, _float_text(child, "linecount", 0.0) or 0.0)
                    line_len = max(0.0, _float_text(child, "linelength", 0.0) or 0.0)
                    line_mat = child.find("linematerial")
                    line_density = 0.0
                    if line_mat is not None and line_mat.attrib.get("density"):
                        try:
                            line_density = max(0.0, float(line_mat.attrib["density"]))
                        except ValueError:
                            line_density = 0.0
                    computed_mass = (
                        surf_density * canopy_area + line_count * line_len * line_density
                    )
                    chute_mass_kg = computed_mass if computed_mass > 0.0 else None
                if chute_mass_kg is not None and chute_mass_kg > 0.0:
                    chute_override_cg = _float_text(child, "overridecg", None)
                    chute_cg_m = (
                        max(0.0, chute_start_m + chute_override_cg)
                        if chute_override_cg is not None
                        else max(0.0, chute_start_m + 0.5 * packed_len)
                    )
                    components.append(
                        PointMassComponent(
                            name=f"{comp_name} (paraquedas)",
                            mass_kg=chute_mass_kg,
                            position_m=chute_cg_m,
                        )
                    )

            elif tag == "railbutton":
                button = _read_rail_button_geometry(child, comp_name, warnings)
                rail_button_radii_m.append(
                    _first_positive_dimension(
                        child, ("outerdiameter",), _DEFAULT_RAIL_BUTTON_OUTER_DIAMETER_M
                    )
                    / 2.0
                )
                base_start = _resolve_start_m(
                    method=method,
                    offset_m=offset_m,
                    comp_length_m=button.height_m,
                    cursor_m=cursor_m,
                    parent_start_m=parent_start_m,
                    parent_length_m=parent_length_m,
                    is_sequential=False,
                )
                count, sep = _read_instances(child)
                for idx in range(count):
                    inst_start = max(0.0, base_start + idx * sep)
                    rail_button_positions.append(inst_start)
                    if button.mass_kg <= 0.0:
                        continue
                    components.append(
                        PointMassComponent(
                            name=comp_name if count == 1 else f"{comp_name} #{idx + 1}",
                            mass_kg=button.mass_kg,
                            position_m=inst_start + button.cg_from_start_m,
                        )
                    )

            elif tag in _UNSUPPORTED_COMPONENT_TAGS:
                warnings.append(
                    OrkImportWarning(
                        severity="warning",
                        component_name=comp_name,
                        message=(
                            f"Componente OpenRocket <{tag}> não possui mapeamento 1:1 no domínio "
                            "Hefesto e foi ignorado."
                        ),
                    )
                )
                if is_sequential:
                    length_m = max(0.0, _float_text(child, "length", 0.0) or 0.0)
                    start_m = _resolve_start_m(
                        method=method,
                        offset_m=offset_m,
                        comp_length_m=length_m,
                        cursor_m=cursor_m,
                        parent_start_m=parent_start_m,
                        parent_length_m=parent_length_m,
                        is_sequential=True,
                    )
                    cursor_m = start_m + length_m

    walk_subcomponents(
        stage_sub,
        parent_start_m=0.0,
        parent_length_m=0.0,
        parent_outer_radius_m=stage_radius_m,
        parent_inner_radius_m=max(0.001, stage_radius_m - 0.002),
        has_physical_parent=False,
        is_sequential=True,
    )

    if not nose_cones:
        warnings.append(
            OrkImportWarning(
                severity="warning",
                component_name="Ogiva",
                message="Nenhuma <nosecone> encontrada; aplicada ogiva padrão.",
            )
        )
        nose_cone = NoseConeSpec(
            name="Default Nose Cone",
            length_m=0.30,
            kind=NoseConeKind.OGIVE,
            position_m=0.0,
            base_radius_m=max_body_radius_m,
        )
    else:
        nose_cone = nose_cones[0]

    if not components:
        raise OrkParseError("Nenhum componente estrutural válido extraído do arquivo .ork.")

    if not fin_sets:
        warnings.append(
            OrkImportWarning(
                severity="warning",
                component_name="Aletas",
                message="Nenhum conjunto de aletas encontrado; aplicado conjunto mínimo padrão.",
            )
        )
        primary_fins = FinSetSpec(
            name="Default Fins",
            count=3,
            position_m=max(0.1, nose_cone.length_m),
            shape_points_m=((0.0, 0.0), (0.04, 0.08), (0.10, 0.08), (0.12, 0.0)),
            radius_m=max_body_radius_m,
        )
    else:
        primary_fins = fin_sets[0]
        if len(fin_sets) > 1:
            warnings.append(
                OrkImportWarning(
                    severity="warning",
                    component_name=primary_fins.name,
                    message=(
                        f"Detectados {len(fin_sets)} conjuntos de aletas; '{primary_fins.name}' "
                        "foi selecionado como conjunto aerodinâmico principal."
                    ),
                )
            )

    distinct_buttons = sorted(set(round(pos, 6) for pos in rail_button_positions))
    # Rail button radius is the standoff from the body surface (ORK outerdiameter/2), not R_body.
    button_radius_m = max(
        rail_button_radii_m, default=_DEFAULT_RAIL_BUTTON_OUTER_DIAMETER_M / 2.0
    )
    if len(distinct_buttons) >= 2:
        rail_buttons = RailButtonsSpec(
            upper_button_position_m=distinct_buttons[0],
            lower_button_position_m=distinct_buttons[-1],
            radius_m=button_radius_m,
        )
    else:
        upper_fallback = nose_cone.length_m + 0.1
        lower_fallback = upper_fallback + 0.5
        warnings.append(
            OrkImportWarning(
                severity="warning",
                component_name="Rail Buttons",
                message=(
                    "Menos de 2 rail buttons encontrados no .ork; aplicadas posições padrão "
                    f"({upper_fallback:.2f} m / {lower_fallback:.2f} m)."
                ),
            )
        )
        rail_buttons = RailButtonsSpec(
            upper_button_position_m=upper_fallback,
            lower_button_position_m=lower_fallback,
            radius_m=button_radius_m,
        )

    return OrkParsedDesign(
        rocket_name=rocket_name,
        source_sha256=source_sha256,
        radius_m=max_body_radius_m,
        nose_cone=nose_cone,
        nose_cone_wall_thickness_m=nose_cone_meta["thickness_m"],
        nose_cone_density_kg_m3=nose_cone_meta["density_kg_m3"],
        nose_cone_override_mass_kg=nose_cone_meta["override_mass_kg"],
        nose_cone_override_cg_m=nose_cone_meta["override_cg_m"],
        components=tuple(components),
        fins=primary_fins,
        rail_buttons=rail_buttons,
        parachutes=tuple(parachutes),
        detected_motor_mount_position_m=detected_motor_mount_pos,
        embedded_rse_names=embedded_rse_names,
        stored_datapoint_count=stored_datapoint_count,
        has_mass_or_cg_overrides=has_overrides,
        surface_finish=_read_surface_finish(rocket_elem),
        drag_table=_extract_flight_drag_table(root, warnings),
        warnings=tuple(warnings),
    )


def parse_ork_file(path: Path) -> OrkParsedDesign:
    """Read an OpenRocket (.ork) file from disk and parse it into OrkParsedDesign."""
    return parse_ork_bytes(path.read_bytes())


__all__ = [
    "OrkParseError",
    "parse_ork_bytes",
    "parse_ork_file",
]
