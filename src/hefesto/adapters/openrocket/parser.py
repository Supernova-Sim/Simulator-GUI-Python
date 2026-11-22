"""Pure-stdlib OpenRocket (.ork) ZIP/XML parser into typed Hefesto domain models."""

from __future__ import annotations

import hashlib
import io
import math
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from hefesto.domain import (
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
    TubeComponent,
)

_DEFAULT_TUBE_DENSITY_KG_M3 = 1850.0
_DEFAULT_RING_DENSITY_KG_M3 = 650.0
_DEFAULT_FIN_DENSITY_KG_M3 = 1850.0
_DEFAULT_FIN_THICKNESS_M = 0.003

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
) -> tuple[NoseConeKind, float | None]:
    raw_shape = (elem.findtext("shape") or "ogive").strip().lower()
    shape_param = _float_text(elem, "shapeparameter", None)
    if raw_shape == "ogive":
        return NoseConeKind.OGIVE, None
    if raw_shape == "conical":
        return NoseConeKind.CONICAL, None
    if raw_shape == "power":
        power = shape_param if shape_param is not None and shape_param > 0.0 else 0.5
        return NoseConeKind.POWERSERIES, power
    if raw_shape == "haack":
        if shape_param is not None and abs(shape_param) < 1e-9:
            return NoseConeKind.VON_KARMAN, None
        return NoseConeKind.LV_HAACK, None
    if raw_shape == "lvhaack":
        return NoseConeKind.LV_HAACK, None

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
    return NoseConeKind.OGIVE, None


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
        if sub_elem is None:
            return

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
                kind, power = _map_nose_shape(child, comp_name, warnings)
                nose_cones.append(
                    NoseConeSpec(
                        name=comp_name,
                        length_m=length_m,
                        kind=kind,
                        position_m=start_m,
                        power=power,
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
                components.append(
                    TubeComponent(
                        name=comp_name,
                        outer_radius_m=outer_r,
                        wall_thickness_m=thickness_m,
                        length_m=length_m,
                        density_kg_m3=density,
                        position_m=start_m + length_m / 2.0,
                    )
                )
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
                        )
                    )
                    if tag == "innertube" and child.find("motormount") is not None:
                        detected_motor_mount_pos = inst_start + length_m
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
                length_m = max(0.0, _float_text(child, "length", 0.01) or 0.01)
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
                for idx in range(count):
                    rail_button_positions.append(max(0.0, base_start + idx * sep))

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
    if len(distinct_buttons) >= 2:
        rail_buttons = RailButtonsSpec(
            upper_button_position_m=distinct_buttons[0],
            lower_button_position_m=distinct_buttons[-1],
            radius_m=max_body_radius_m,
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
            radius_m=max_body_radius_m,
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
