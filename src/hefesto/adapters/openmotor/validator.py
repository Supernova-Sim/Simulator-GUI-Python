"""Strict whitelist, type, enum, and range validation for OpenMotor .ric configurations."""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from hefesto.domain import GrainInhibition, GrainSpec, MotorOverride

# Match motorlib.constants reference bounds so silent clamping/ignoring never passes.
_MAX_REF_DIAMETER_M = 6.6
_MAX_REF_LENGTH_M = 24.6
_INHIBITED_ENDS_VALUES: tuple[str, ...] = ("Neither", "Top", "Bottom", "Both")
_DXF_UNIT_VALUES: tuple[str, ...] = ("m", "cm", "mm", "in", "ft")

OverrideValue = float | int | str
OverrideInput = Sequence[MotorOverride] | Mapping[str, OverrideValue]
PropValue = float | int | str | bool | list[object]


class PropertyKind(StrEnum):
    """Supported motorlib PropertyCollection data types."""

    FLOAT = "float"
    INT = "int"
    ENUM = "enum"
    BOOL = "bool"
    STRING = "string"
    POLYGON = "polygon"


@dataclass(frozen=True)
class PropertyConstraint:
    """Validation specification mirroring a single motorlib Property object."""

    kind: PropertyKind
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: tuple[str, ...] = ()

    def validate(self, value: object, *, path: str) -> PropValue:
        """Validate and normalize a value against this property constraint."""
        if self.kind == PropertyKind.FLOAT:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Expected finite float for '{path}', got {value!r}")
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError(f"Expected finite float for '{path}', got {value!r}")
            if self.min_value is not None and numeric < self.min_value:
                raise ValueError(
                    f"Value {numeric} for '{path}' below minimum {self.min_value}"
                )
            if self.max_value is not None and numeric > self.max_value:
                raise ValueError(
                    f"Value {numeric} for '{path}' above maximum {self.max_value}"
                )
            return numeric

        if self.kind == PropertyKind.INT:
            if isinstance(value, bool):
                raise ValueError(f"Expected integer for '{path}', got boolean {value!r}")
            if isinstance(value, int):
                int_val = value
            elif isinstance(value, float) and math.isfinite(value) and value.is_integer():
                int_val = int(value)
            else:
                raise ValueError(f"Expected integer for '{path}', got {value!r}")
            if self.min_value is not None and int_val < self.min_value:
                raise ValueError(
                    f"Value {int_val} for '{path}' below minimum {self.min_value}"
                )
            if self.max_value is not None and int_val > self.max_value:
                raise ValueError(
                    f"Value {int_val} for '{path}' above maximum {self.max_value}"
                )
            return int_val

        if self.kind == PropertyKind.ENUM:
            if not isinstance(value, str) or value not in self.allowed_values:
                raise ValueError(
                    f"Invalid enum value {value!r} for '{path}'; allowed={self.allowed_values}"
                )
            return value

        if self.kind == PropertyKind.BOOL:
            if not isinstance(value, bool):
                raise ValueError(f"Expected bool for '{path}', got {value!r}")
            return value

        if self.kind == PropertyKind.STRING:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Expected non-empty string for '{path}', got {value!r}")
            return value

        if self.kind == PropertyKind.POLYGON:
            if not isinstance(value, (list, tuple)):
                raise ValueError(f"Expected polygon list for '{path}', got {type(value).__name__}")
            return _validate_polygons(value, path=path)

        raise ValueError(f"Unsupported property kind {self.kind!r} for '{path}'")


def _validate_polygons(raw: Sequence[object], *, path: str) -> list[object]:
    normalized: list[object] = []
    for poly_idx, poly in enumerate(raw):
        if not isinstance(poly, (list, tuple)):
            raise ValueError(f"Polygon [{poly_idx}] for '{path}' must be a sequence")
        pts: list[list[float]] = []
        for pt_idx, pt in enumerate(poly):
            if not isinstance(pt, (list, tuple)) or len(pt) != 2:
                raise ValueError(
                    f"Point [{pt_idx}] in polygon [{poly_idx}] for '{path}' must be a 2-tuple"
                )
            x_raw, y_raw = pt
            if (
                isinstance(x_raw, bool)
                or isinstance(y_raw, bool)
                or not isinstance(x_raw, (int, float))
                or not isinstance(y_raw, (int, float))
                or not (math.isfinite(float(x_raw)) and math.isfinite(float(y_raw)))
            ):
                raise ValueError(
                    f"Non-finite vertex in polygon [{poly_idx}][{pt_idx}] for '{path}': {pt!r}"
                )
            pts.append([float(x_raw), float(y_raw)])
        normalized.append(pts)
    return normalized


def _f(min_val: float, max_val: float) -> PropertyConstraint:
    return PropertyConstraint(PropertyKind.FLOAT, min_value=min_val, max_value=max_val)


def _i(min_val: int, max_val: int) -> PropertyConstraint:
    return PropertyConstraint(
        PropertyKind.INT, min_value=float(min_val), max_value=float(max_val)
    )


def _e(values: tuple[str, ...]) -> PropertyConstraint:
    return PropertyConstraint(PropertyKind.ENUM, allowed_values=values)


CONFIG_PROPERTY_CONSTRAINTS: dict[str, PropertyConstraint] = {
    "maxPressure": _f(0.0, 7e7),
    "maxMassFlux": _f(0.0, 1e4),
    "maxMachNumber": _f(0.0, 100.0),
    "minPortThroat": _f(1.0, 4.0),
    "flowSeparationWarnPercent": _f(0.0, 1.0),
    "burnoutWebThres": _f(2.54e-5, 3.175e-3),
    "burnoutThrustThres": _f(0.01, 10.0),
    "timestep": _f(0.0001, 0.1),
    "ambPressure": _f(0.0001, 102000.0),
    "mapDim": _i(250, 2000),
    "sepPressureRatio": _f(0.001, 1.0),
}

NOZZLE_PROPERTY_CONSTRAINTS: dict[str, PropertyConstraint] = {
    "throat": _f(0.0, _MAX_REF_DIAMETER_M),
    "exit": _f(0.0, _MAX_REF_DIAMETER_M),
    "efficiency": _f(0.0, 2.0),
    "divAngle": _f(0.0, 90.0),
    "convAngle": _f(0.0, 90.0),
    "throatLength": _f(0.0, _MAX_REF_LENGTH_M / 10.0),
    "slagCoeff": _f(0.0, 1e6),
    "erosionCoeff": _f(0.0, 1e6),
}

PROPELLANT_PROPERTY_CONSTRAINTS: dict[str, PropertyConstraint] = {
    "name": PropertyConstraint(PropertyKind.STRING),
    "density": _f(1.0, 10000.0),
}

PROPELLANT_TAB_PROPERTY_CONSTRAINTS: dict[str, PropertyConstraint] = {
    "minPressure": _f(0.0, 7e7),
    "maxPressure": _f(0.0, 7e7),
    "a": _f(1e-8, 2.0),
    "n": _f(-0.99, 0.99),
    "k": _f(1.0 + 1e-6, 10.0),
    "t": _f(1.0, 10000.0),
    "m": _f(1e-6, 100.0),
}

_BASE_GRAIN_CONSTRAINTS: dict[str, PropertyConstraint] = {
    "diameter": _f(0.0, _MAX_REF_DIAMETER_M),
    "length": _f(0.0, _MAX_REF_LENGTH_M),
}

_PERFORATED_GRAIN_CONSTRAINTS: dict[str, PropertyConstraint] = {
    **_BASE_GRAIN_CONSTRAINTS,
    "inhibitedEnds": _e(_INHIBITED_ENDS_VALUES),
}

GRAIN_PROPERTY_CONSTRAINTS: dict[str, dict[str, PropertyConstraint]] = {
    "BATES": {
        **_PERFORATED_GRAIN_CONSTRAINTS,
        "coreDiameter": _f(0.0, 5.0),
    },
    "End Burner": dict(_BASE_GRAIN_CONSTRAINTS),
    "Finocyl": {
        **_PERFORATED_GRAIN_CONSTRAINTS,
        "numFins": _i(0, 64),
        "finWidth": _f(0.0, _MAX_REF_DIAMETER_M),
        "finLength": _f(0.0, _MAX_REF_DIAMETER_M),
        "coreDiameter": _f(0.0, _MAX_REF_DIAMETER_M),
        "invertedFins": PropertyConstraint(PropertyKind.BOOL),
    },
    "Moon Burner": {
        **_PERFORATED_GRAIN_CONSTRAINTS,
        "coreOffset": _f(0.0, _MAX_REF_DIAMETER_M),
        "coreDiameter": _f(0.0, _MAX_REF_DIAMETER_M),
    },
    "Star Grain": {
        **_PERFORATED_GRAIN_CONSTRAINTS,
        "numPoints": _i(0, 64),
        "pointLength": _f(0.0, _MAX_REF_DIAMETER_M),
        "pointWidth": _f(0.0, _MAX_REF_DIAMETER_M),
    },
    "X Core": {
        **_PERFORATED_GRAIN_CONSTRAINTS,
        "slotWidth": _f(0.0, _MAX_REF_DIAMETER_M),
        "slotLength": _f(0.0, _MAX_REF_DIAMETER_M),
    },
    "C Grain": {
        **_PERFORATED_GRAIN_CONSTRAINTS,
        "slotWidth": _f(0.0, _MAX_REF_DIAMETER_M),
        "slotOffset": _f(-_MAX_REF_DIAMETER_M, _MAX_REF_DIAMETER_M),
    },
    "D Grain": {
        **_PERFORATED_GRAIN_CONSTRAINTS,
        "slotOffset": _f(-_MAX_REF_DIAMETER_M, _MAX_REF_DIAMETER_M),
    },
    "Rod and Tube": {
        **_PERFORATED_GRAIN_CONSTRAINTS,
        "coreDiameter": _f(0.0, _MAX_REF_DIAMETER_M),
        "rodDiameter": _f(0.0, _MAX_REF_DIAMETER_M),
        "supportDiameter": _f(0.0, _MAX_REF_DIAMETER_M),
    },
    "Conical": {
        **_PERFORATED_GRAIN_CONSTRAINTS,
        "forwardCoreDiameter": _f(0.0, _MAX_REF_DIAMETER_M),
        "aftCoreDiameter": _f(0.0, _MAX_REF_DIAMETER_M),
    },
    "Custom Grain": {
        **_PERFORATED_GRAIN_CONSTRAINTS,
        "points": PropertyConstraint(PropertyKind.POLYGON),
        "dxfUnit": _e(_DXF_UNIT_VALUES),
    },
}

_STANDALONE_GRAIN_CONSTRAINTS: dict[str, PropertyConstraint] = {
    prop_name: constraint
    for grain_map in reversed(list(GRAIN_PROPERTY_CONSTRAINTS.values()))
    for prop_name, constraint in grain_map.items()
}


def _split_override_path(path: str) -> list[str]:
    stripped = path.strip()
    if not stripped or stripped != path:
        raise ValueError(f"Override path must not be blank or padded: {path!r}")
    parts = stripped.split(".")
    if any(not part for part in parts):
        raise ValueError(f"Override path contains empty segment: {path!r}")
    return parts


def _parse_selector(token: str, *, length: int | None, path: str, label: str) -> int | None:
    if token == "*":
        if length is not None and length == 0:
            raise ValueError(f"Wildcard '{path}' has empty '{label}' list")
        return None
    if token.isdigit():
        idx = int(token)
        if length is not None and not (0 <= idx < length):
            raise ValueError(
                f"Index {idx} out of bounds for '{label}' (len={length}) in '{path}'"
            )
        return idx
    raise ValueError(f"Invalid selector {token!r} in '{path}'; expected '*' or non-negative int")


def normalize_overrides(overrides: OverrideInput) -> tuple[MotorOverride, ...]:
    """Convert override inputs to MotorOverride items ordered wildcard-first, index-second."""
    if isinstance(overrides, Mapping):
        items = [MotorOverride(path=key, value=val) for key, val in overrides.items()]
    else:
        items = list(overrides)

    ordered = sorted(
        enumerate(items),
        key=lambda entry: (
            1 if any(part.isdigit() for part in _split_override_path(entry[1].path)) else 0,
            entry[0],
        ),
    )
    return tuple(entry[1] for entry in ordered)


def validate_override(
    override: MotorOverride,
    *,
    grain_types: Sequence[str] | None = None,
    tab_count: int | None = None,
) -> PropValue:
    """Validate a MotorOverride against the OpenMotor whitelist, types, enums, and bounds."""
    parts = _split_override_path(override.path)
    section = parts[0]

    if section == "config" and len(parts) == 2:
        constraint = CONFIG_PROPERTY_CONSTRAINTS.get(parts[1])
        if constraint is None:
            raise ValueError(f"Unknown OpenMotor config property '{override.path}'")
        return constraint.validate(override.value, path=override.path)

    if section == "nozzle" and len(parts) == 2:
        constraint = NOZZLE_PROPERTY_CONSTRAINTS.get(parts[1])
        if constraint is None:
            raise ValueError(f"Unknown OpenMotor nozzle property '{override.path}'")
        return constraint.validate(override.value, path=override.path)

    if section == "propellant" and len(parts) == 2:
        constraint = PROPELLANT_PROPERTY_CONSTRAINTS.get(parts[1])
        if constraint is None:
            raise ValueError(f"Unknown OpenMotor propellant property '{override.path}'")
        return constraint.validate(override.value, path=override.path)

    if section == "propellant" and len(parts) == 4 and parts[1] == "tabs":
        _parse_selector(parts[2], length=tab_count, path=override.path, label="propellant.tabs")
        constraint = PROPELLANT_TAB_PROPERTY_CONSTRAINTS.get(parts[3])
        if constraint is None:
            raise ValueError(f"Unknown OpenMotor propellant tab property '{override.path}'")
        return constraint.validate(override.value, path=override.path)

    if section == "grains" and len(parts) == 4 and parts[2] == "properties":
        idx = _parse_selector(
            parts[1],
            length=len(grain_types) if grain_types is not None else None,
            path=override.path,
            label="grains",
        )
        prop_name = parts[3]
        if grain_types is None:
            constraint = _STANDALONE_GRAIN_CONSTRAINTS.get(prop_name)
            if constraint is None:
                raise ValueError(f"Unknown OpenMotor grain property '{override.path}'")
            return constraint.validate(override.value, path=override.path)

        target_types = grain_types if idx is None else (grain_types[idx],)
        validated: PropValue | None = None
        for grain_type in target_types:
            grain_specs = GRAIN_PROPERTY_CONSTRAINTS.get(grain_type)
            if grain_specs is None:
                raise ValueError(f"Unsupported OpenMotor grain type {grain_type!r}")
            constraint = grain_specs.get(prop_name)
            if constraint is None:
                raise ValueError(
                    f"Property {prop_name!r} is not supported on grain type {grain_type!r} "
                    f"('{override.path}')"
                )
            validated = constraint.validate(override.value, path=override.path)
        assert validated is not None
        return validated

    raise ValueError(f"Override path '{override.path}' is not in the OpenMotor whitelist")


def _as_str_mapping(obj: object, *, label: str) -> dict[str, object]:
    if not isinstance(obj, Mapping):
        raise ValueError(f"Expected mapping for {label}, got {type(obj).__name__}")
    out: dict[str, object] = {}
    for key, val in obj.items():
        if not isinstance(key, str):
            raise ValueError(f"Expected string keys in {label}, got {key!r}")
        out[key] = val
    return out


def _as_list(obj: object, *, label: str) -> list[object]:
    if not isinstance(obj, list):
        raise ValueError(f"Expected list for {label}, got {type(obj).__name__}")
    return obj


def _validate_section_props(
    section_map: Mapping[str, object],
    constraints: Mapping[str, PropertyConstraint],
    *,
    section_name: str,
    required_keys: tuple[str, ...] = (),
) -> None:
    for req in required_keys:
        if req not in section_map:
            raise ValueError(f"Missing required key '{section_name}.{req}' in .ric payload")
    for key, val in section_map.items():
        constraint = constraints.get(key)
        if constraint is None:
            raise ValueError(f"Unknown key '{section_name}.{key}' in .ric payload")
        constraint.validate(val, path=f"{section_name}.{key}")


def validate_ric_dict(props: Mapping[str, object]) -> None:
    """Validate an OpenMotor .ric payload against known sections, keys, types, and ranges."""
    root = _as_str_mapping(props, label="ric")

    if "config" in root:
        config_map = _as_str_mapping(root["config"], label="config")
        _validate_section_props(config_map, CONFIG_PROPERTY_CONSTRAINTS, section_name="config")

    nozzle_map = _as_str_mapping(root.get("nozzle"), label="nozzle")
    _validate_section_props(
        nozzle_map,
        NOZZLE_PROPERTY_CONSTRAINTS,
        section_name="nozzle",
        required_keys=("throat", "exit"),
    )

    prop_map = _as_str_mapping(root.get("propellant"), label="propellant")
    for key in prop_map:
        if key not in {"name", "density", "tabs"}:
            raise ValueError(f"Unknown key 'propellant.{key}' in .ric payload")
    if "density" not in prop_map:
        raise ValueError("Missing required key 'propellant.density' in .ric payload")
    PROPELLANT_PROPERTY_CONSTRAINTS["density"].validate(
        prop_map["density"], path="propellant.density"
    )
    if "name" in prop_map and prop_map["name"] is not None:
        PROPELLANT_PROPERTY_CONSTRAINTS["name"].validate(prop_map["name"], path="propellant.name")

    tabs = _as_list(prop_map.get("tabs"), label="propellant.tabs")
    if not tabs:
        raise ValueError("OpenMotor .ric payload requires at least one propellant tab")
    required_tab_keys = ("a", "n", "k", "t", "m", "minPressure", "maxPressure")
    for tab_idx, raw_tab in enumerate(tabs):
        tab_map = _as_str_mapping(raw_tab, label=f"propellant.tabs[{tab_idx}]")
        _validate_section_props(
            tab_map,
            PROPELLANT_TAB_PROPERTY_CONSTRAINTS,
            section_name=f"propellant.tabs.{tab_idx}",
            required_keys=required_tab_keys,
        )
        min_p = float(tab_map["minPressure"])  # type: ignore[arg-type]
        max_p = float(tab_map["maxPressure"])  # type: ignore[arg-type]
        if min_p >= max_p:
            raise ValueError(
                f"propellant.tabs.{tab_idx}: minPressure ({min_p}) must be < maxPressure ({max_p})"
            )

    grains = _as_list(root.get("grains"), label="grains")
    if not grains:
        raise ValueError("OpenMotor .ric payload must contain at least one grain")
    for idx, raw_grain in enumerate(grains):
        grain_map = _as_str_mapping(raw_grain, label=f"grains[{idx}]")
        grain_type_raw = grain_map.get("type")
        if not isinstance(grain_type_raw, str) or grain_type_raw not in GRAIN_PROPERTY_CONSTRAINTS:
            raise ValueError(f"Unsupported grain type at grains[{idx}]: {grain_type_raw!r}")
        if grain_type_raw == "End Burner" and idx != 0:
            raise ValueError(
                f"End Burner grain must be at index 0 (forward-most), found at index {idx}"
            )
        grain_props = _as_str_mapping(
            grain_map.get("properties"), label=f"grains[{idx}].properties"
        )
        req_keys: tuple[str, ...] = (
            ("diameter", "length", "coreDiameter")
            if grain_type_raw == "BATES"
            else ("diameter", "length")
        )
        _validate_section_props(
            grain_props,
            GRAIN_PROPERTY_CONSTRAINTS[grain_type_raw],
            section_name=f"grains.{idx}.properties",
            required_keys=req_keys,
        )


def _extract_grain_types(props: Mapping[str, object]) -> tuple[str, ...]:
    grains = _as_list(props.get("grains"), label="grains")
    types: list[str] = []
    for idx, raw_grain in enumerate(grains):
        grain_map = _as_str_mapping(raw_grain, label=f"grains[{idx}]")
        gtype = grain_map.get("type")
        if not isinstance(gtype, str):
            raise ValueError(f"Missing string grain type at grains[{idx}]")
        types.append(gtype)
    return tuple(types)


def _set_validated_path(
    props: dict[str, object],
    parts: list[str],
    value: PropValue,
) -> None:
    section = parts[0]
    if section in {"config", "nozzle"}:
        target = props.get(section)
        if not isinstance(target, dict):
            raise ValueError(f"Missing dict section '{section}' in .ric payload")
        target[parts[1]] = value
        return

    if section == "propellant" and len(parts) == 2:
        target = props.get("propellant")
        if not isinstance(target, dict):
            raise ValueError("Missing dict section 'propellant' in .ric payload")
        target[parts[1]] = value
        return

    if section == "propellant" and len(parts) == 4 and parts[1] == "tabs":
        prop_obj = props.get("propellant")
        if not isinstance(prop_obj, dict):
            raise ValueError("Missing dict section 'propellant' in .ric payload")
        tabs = prop_obj.get("tabs")
        if not isinstance(tabs, list):
            raise ValueError("Missing list 'propellant.tabs' in .ric payload")
        selector = parts[2]
        targets = tabs if selector == "*" else [tabs[int(selector)]]
        for tab in targets:
            if not isinstance(tab, dict):
                raise ValueError("Propellant tab entry must be a dict")
            tab[parts[3]] = value
        return

    if section == "grains" and len(parts) == 4 and parts[2] == "properties":
        grains = props.get("grains")
        if not isinstance(grains, list):
            raise ValueError("Missing list 'grains' in .ric payload")
        selector = parts[1]
        targets = grains if selector == "*" else [grains[int(selector)]]
        for grain in targets:
            if not isinstance(grain, dict) or not isinstance(grain.get("properties"), dict):
                raise ValueError("Grain entry must be a dict with 'properties'")
            grain["properties"][parts[3]] = value
        return

    raise ValueError(f"Unsupported override path segments: {parts!r}")


def apply_overrides_to_props(
    props: Mapping[str, object],
    overrides: OverrideInput = (),
) -> dict[str, object]:
    """Return a deep-copied .ric payload with whitelist-validated overrides applied."""
    copied = copy.deepcopy(dict(props))
    validate_ric_dict(copied)

    ordered = normalize_overrides(overrides)
    if not ordered:
        return copied

    grain_types = _extract_grain_types(copied)
    propellant_map = _as_str_mapping(copied["propellant"], label="propellant")
    tab_count = len(_as_list(propellant_map["tabs"], label="propellant.tabs"))

    for override in ordered:
        validated_value = validate_override(
            override,
            grain_types=grain_types,
            tab_count=tab_count,
        )
        _set_validated_path(copied, _split_override_path(override.path), validated_value)

    validate_ric_dict(copied)
    return copied


def extract_grains_from_props(
    props: Mapping[str, object],
    *,
    fallback_inner_radii_m: Sequence[float] | None = None,
) -> tuple[GrainSpec, ...]:
    """Extract validated domain GrainSpec tuples from a validated OpenMotor .ric payload."""
    grains_raw = _as_list(props.get("grains"), label="grains")
    if not grains_raw:
        raise ValueError("OpenMotor .ric payload contains no grains")

    specs: list[GrainSpec] = []
    for idx, raw_grain in enumerate(grains_raw):
        grain_map = _as_str_mapping(raw_grain, label=f"grains[{idx}]")
        grain_type = str(grain_map.get("type", ""))
        p = _as_str_mapping(grain_map.get("properties"), label=f"grains[{idx}].properties")

        length_m = float(p["length"])  # type: ignore[arg-type]
        outer_radius_m = float(p["diameter"]) / 2.0  # type: ignore[arg-type]

        if grain_type == "End Burner":
            inner_radius_m = 0.0
            inhibited = GrainInhibition.NEITHER
        else:
            raw_inhibited = str(p.get("inhibitedEnds", "Neither")).strip().lower()
            inhibited = GrainInhibition(raw_inhibited)
            if "coreDiameter" in p:
                inner_radius_m = float(p["coreDiameter"]) / 2.0  # type: ignore[arg-type]
            elif "forwardCoreDiameter" in p and "aftCoreDiameter" in p:
                fwd = float(p["forwardCoreDiameter"])  # type: ignore[arg-type]
                aft = float(p["aftCoreDiameter"])  # type: ignore[arg-type]
                inner_radius_m = 0.25 * (fwd + aft)
            elif fallback_inner_radii_m is not None and idx < len(fallback_inner_radii_m):
                inner_radius_m = float(fallback_inner_radii_m[idx])
            else:
                inner_radius_m = 0.0

        specs.append(
            GrainSpec(
                length_m=length_m,
                outer_radius_m=outer_radius_m,
                inner_radius_m=inner_radius_m,
                inhibited_ends=inhibited,
            )
        )
    return tuple(specs)


__all__ = [
    "CONFIG_PROPERTY_CONSTRAINTS",
    "GRAIN_PROPERTY_CONSTRAINTS",
    "NOZZLE_PROPERTY_CONSTRAINTS",
    "PROPELLANT_PROPERTY_CONSTRAINTS",
    "PROPELLANT_TAB_PROPERTY_CONSTRAINTS",
    "OverrideInput",
    "OverrideValue",
    "PropertyConstraint",
    "PropertyKind",
    "apply_overrides_to_props",
    "extract_grains_from_props",
    "normalize_overrides",
    "validate_override",
    "validate_ric_dict",
]
