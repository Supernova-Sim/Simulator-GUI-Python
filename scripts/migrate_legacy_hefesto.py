"""Migrate legacy Hefesto configurations into validated Pydantic JSON catalog presets."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

from hefesto.domain import (
    AssetCategory,
    EnvironmentSpec,
    Era5DatasetKind,
    FinComponent,
    FinSetSpec,
    GrainInhibition,
    GrainSpec,
    MotorCasingSpec,
    MotorPreset,
    MotorSpec,
    NetCdfVariableMap,
    NoseConeKind,
    NoseConeSpec,
    NozzleSpec,
    ParachuteSpec,
    PointMassComponent,
    RailButtonsSpec,
    RocketComponent,
    RocketPreset,
    SafetyLimits,
    TubeComponent,
)
from hefesto.physics import (
    compute_grain_stack_cg_m,
    compute_motor_casing_dry_inertia_kg_m2,
    derive_component_properties,
    validate_grain_casing_fit,
)
from hefesto.storage import (
    AssetStore,
    CatalogStore,
    parse_eng_file,
    resolve_storage_paths,
)

_LEGACY_COMPONENT_NAMES_EN: dict[str, str] = {
    "Modulo Avionica": "Avionics Module",
    "Modulo Payload": "Payload Module",
    "Modulo Propulsao": "Propulsion Module",
    "Modulo Aletas": "Fins Module",
    "Juncao Avionica/Payload": "Avionics/Payload Coupler",
    "Juncao Payload/Propulsao": "Payload/Propulsion Coupler",
    "Juncao Propulsao/Aletas": "Propulsion/Fins Coupler",
    "Fixador Superior 1": "Upper Retainer 1",
    "Fixador Inferior 1": "Lower Retainer 1",
    "Fixador Superior 2": "Upper Retainer 2",
    "Anel centralizador inf 1": "Lower Centering Ring 1",
    "Anel centralizador sup 1": "Upper Centering Ring 1",
    "Anel centralizador sup 2": "Upper Centering Ring 2",
    "Anel centralizador medio 2": "Middle Centering Ring 2",
    "Anel centralizador inf 2": "Lower Centering Ring 2",
    "Anteparo Recuperacao": "Recovery Bulkhead",
    "Anteparo Inferior": "Lower Bulkhead",
    "Paraquedas unreefed": "Unreefed Parachute",
    "Paraquedas reefed": "Reefed Parachute",
    "Sistemas de recuperacao": "Recovery System",
    "Avionica": "Avionics",
    "Satelite": "Payload",
    "Complemento de massa": "Ballast Mass",
    "Rail Button (conjunto)": "Rail Buttons Set",
    "Coifa": "Nose Cone Mass",
    "Aletas": "Main Fins",
}


def _ensure_repo_root_on_sys_path() -> None:
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def _translate_component_name(legacy_name: str) -> str:
    if legacy_name not in _LEGACY_COMPONENT_NAMES_EN:
        raise KeyError(f"Missing English translation for legacy component: {legacy_name!r}")
    return _LEGACY_COMPONENT_NAMES_EN[legacy_name]


def _build_safety_limits(limites: dict[str, float]) -> SafetyLimits:
    return SafetyLimits(
        min_case_safety_factor=float(limites["fs_min_carcaca"]),
        target_case_safety_factor=float(limites["fs_alvo_carcaca"]),
        max_chamber_pressure_pa=float(limites["p0_max"]),
        max_kn=float(limites["kn_max"]),
        max_mass_flux_kg_m2_s=float(limites["mass_flux_max"]),
        min_port_to_throat_ratio=float(limites["port_throat_min"]),
    )


def _convert_legacy_components(
    pecas: list[dict[str, Any]],
    aletas: dict[str, Any],
) -> tuple[RocketComponent, ...]:
    converted: list[RocketComponent] = []
    for raw in pecas:
        name = _translate_component_name(str(raw["nome"]))
        kind = str(raw["tipo"])
        if kind == "tubo":
            converted.append(
                TubeComponent(
                    name=name,
                    outer_radius_m=float(raw["raio"]),
                    wall_thickness_m=float(raw["espessura"]),
                    length_m=float(raw["comprimento"]),
                    density_kg_m3=float(raw["densidade"]),
                    position_m=float(raw["posicao"]),
                )
            )
        elif kind == "massa":
            converted.append(
                PointMassComponent(
                    name=name,
                    mass_kg=float(raw["massa"]),
                    position_m=float(raw["posicao"]),
                )
            )
        elif kind == "aletas":
            shape = tuple((float(x), float(y)) for x, y in raw["shape_points"])
            converted.append(
                FinComponent(
                    name=name,
                    count=int(raw["n"]),
                    shape_points_m=shape,
                    thickness_m=float(raw["espessura"]),
                    density_kg_m3=float(raw["densidade"]),
                    position_m=float(aletas["position"]),
                )
            )
        else:
            raise ValueError(f"Unsupported legacy component kind: {kind!r}")
    return tuple(converted)


def _build_rocket_preset(asset_store: AssetStore, dicionario: Any) -> RocketPreset:
    foguete = dicionario.FOGUETE
    coifa = dicionario.COIFA
    aletas = dicionario.ALETAS
    botoes = dicionario.BOTOES_TRILHO
    paraquedas = dicionario.PARAQUEDAS

    power_off_name = Path(foguete["power_off_drag"]).name
    power_on_name = Path(foguete["power_on_drag"]).name
    asset_store.resolve_asset(AssetCategory.DRAG, power_off_name)
    asset_store.resolve_asset(AssetCategory.DRAG, power_on_name)

    parachutes = tuple(
        ParachuteSpec(
            name=str(cfg["name"]),
            cd_s_m2=float(cfg["cd_s"]),
            trigger="apogee" if cfg["trigger"] == "apogee" else float(cfg["trigger"]),
            lag_s=float(cfg["lag"]),
            radius_m=float(cfg["radius"]),
        )
        for cfg in paraquedas.values()
    )
    inertia = tuple(float(val) for val in foguete["inertia"])
    return RocketPreset(
        name="hefesto_v1",
        radius_m=float(foguete["radius"]),
        center_of_mass_without_motor_m=float(foguete["center_of_mass_without_motor"]),
        inertia_kg_m2=(inertia[0], inertia[1], inertia[2]),
        motor_position_m=float(foguete["motor_position"]),
        components=_convert_legacy_components(dicionario.PECAS, aletas),
        nose_cone=NoseConeSpec(
            length_m=float(coifa["length"]),
            kind=NoseConeKind(str(coifa["kind"])),
            position_m=float(coifa["position"]),
            name="Nose Cone",
        ),
        fins=FinSetSpec(
            name="Main Fins",
            count=int(aletas["n"]),
            position_m=float(aletas["position"]),
            shape_points_m=tuple((float(x), float(y)) for x, y in aletas["shape_points"]),
            cant_angle_deg=float(aletas["cant_angle"]),
        ),
        rail_buttons=RailButtonsSpec(
            upper_button_position_m=float(botoes["upper_button_position"]),
            lower_button_position_m=float(botoes["lower_button_position"]),
            angular_position_deg=float(botoes["angular_position"]),
            radius_m=float(botoes["radius"]),
        ),
        parachutes=parachutes,
        power_off_drag_asset=power_off_name,
        power_on_drag_asset=power_on_name,
        motor_preset_name="medusa_knsb_a",
    )


def _extract_ric_spec(
    ric_path: Path,
    nozzle_position_m: float,
) -> tuple[tuple[GrainSpec, ...], NozzleSpec, str, float]:
    from backend.API.openmotor.nucleo.adaptador import carregar_ric

    props = carregar_ric(ric_path)
    grains = tuple(
        GrainSpec(
            length_m=float(item["properties"]["length"]),
            outer_radius_m=float(item["properties"]["diameter"]) / 2.0,
            inner_radius_m=float(item["properties"]["coreDiameter"]) / 2.0,
            inhibited_ends=GrainInhibition(str(item["properties"]["inhibitedEnds"]).lower()),
        )
        for item in props["grains"]
    )
    raw_nozzle = props["nozzle"]
    nozzle = NozzleSpec(
        throat_radius_m=float(raw_nozzle["throat"]) / 2.0,
        exit_radius_m=float(raw_nozzle["exit"]) / 2.0,
        position_m=nozzle_position_m,
        throat_length_m=float(raw_nozzle["throatLength"]),
        converging_angle_deg=float(raw_nozzle["convAngle"]),
        diverging_angle_deg=float(raw_nozzle["divAngle"]),
        efficiency=float(raw_nozzle["efficiency"]),
    )
    propellant_name = str(props["propellant"]["name"])
    propellant_density = float(props["propellant"]["density"])
    return grains, nozzle, propellant_name, propellant_density


def _read_eng_header_masses_and_dims(eng_path: Path) -> tuple[float, float, float, float]:
    for line in eng_path.read_text(encoding="utf-8").splitlines():
        cleaned = line.split(";", 1)[0].strip()
        if not cleaned:
            continue
        tokens = cleaned.split()
        diameter_m = float(tokens[1]) / 1000.0
        length_m = float(tokens[2]) / 1000.0
        prop_mass_kg = float(tokens[4])
        total_mass_kg = float(tokens[5])
        return diameter_m, length_m, prop_mass_kg, total_mass_kg
    raise ValueError(f"Missing RASP header in {eng_path}")


def _validate_motor_preset_fit(
    preset: MotorPreset, thrust_curve: list[tuple[float, float]]
) -> None:
    if not preset.fallback_grains or preset.nozzle is None:
        return
    if preset.propellant_density_kg_m3 is None or preset.burn_time_s is None:
        return
    motor_spec = MotorSpec(
        name=preset.name,
        grains=preset.fallback_grains,
        grain_separation_m=preset.grain_separation_m,
        grains_center_of_mass_m=preset.grains_center_of_mass_m,
        propellant_name=preset.propellant_name,
        propellant_density_kg_m3=preset.propellant_density_kg_m3,
        nozzle=preset.nozzle,
        casing=preset.casing,
        burn_time_s=preset.burn_time_s,
        thrust_curve=tuple(thrust_curve),
        motor_asset=preset.motor_asset,
        thrust_curve_asset=preset.thrust_curve_asset,
    )
    validate_grain_casing_fit(motor_spec)


def _build_motor_presets(
    asset_store: AssetStore,
    motor_cfg: dict[str, Any],
    limites: dict[str, float],
) -> tuple[MotorPreset, ...]:
    base_inertia = tuple(float(val) for val in motor_cfg["dry_inertia"])
    yield_strength_pa = float(limites["sigma_lim_carcaca"])
    base_casing = MotorCasingSpec(
        inner_radius_m=0.05395,
        wall_thickness_m=0.003175,
        length_m=1.10,
        internal_clearance_m=0.04,
        yield_strength_pa=yield_strength_pa,
        dry_mass_kg=float(motor_cfg["dry_mass"]),
        dry_inertia_kg_m2=(base_inertia[0], base_inertia[1], base_inertia[2]),
        center_of_dry_mass_m=float(motor_cfg["center_of_dry_mass_position"]),
    )
    grain_sep = float(motor_cfg["grain_separation"])
    nozzle_pos = float(motor_cfg["nozzle_position"])

    presets: list[MotorPreset] = []
    for preset_name, ric_asset, eng_asset in (
        ("medusa_knsb_a", "medusa_knsb_a.ric", "medusa_knsb_a.eng"),
        ("medusa_n2792_v1", "medusa_n2792_v1.ric", "medusa_n2792_v1.eng"),
        ("medusa_n3002_v2", "medusa_n3002_v2.ric", "medusa_n3002_v2.eng"),
    ):
        ric_path = asset_store.resolve_asset(AssetCategory.MOTORS, ric_asset)
        eng_path = asset_store.resolve_asset(AssetCategory.MOTORS, eng_asset)
        grains, nozzle, prop_name, prop_density = _extract_ric_spec(ric_path, nozzle_pos)
        curve = parse_eng_file(eng_path)
        burn_time = (curve[0][0], curve[-1][0])
        if preset_name == "medusa_knsb_a":
            grains_cg = float(motor_cfg["grains_center_of_mass_position"])
        else:
            cg_forward = compute_grain_stack_cg_m(
                grains,
                grain_separation_m=grain_sep,
                propellant_density_kg_m3=prop_density,
                start_offset_m=0.075,
            )
            grains_cg = base_casing.length_m - cg_forward

        preset = MotorPreset(
            name=preset_name,
            motor_asset=ric_asset,
            thrust_curve_asset=eng_asset,
            casing=base_casing,
            grain_separation_m=grain_sep,
            grains_center_of_mass_m=grains_cg,
            nozzle_position_m=nozzle_pos,
            propellant_name=prop_name,
            fallback_grains=grains,
            propellant_density_kg_m3=prop_density,
            nozzle=nozzle,
            burn_time_s=burn_time,
        )
        _validate_motor_preset_fit(preset, curve)
        presets.append(preset)

    # medusa_n3174 only has an .eng asset; derive casing/fallback grains from RASP header.
    n3174_eng = "medusa_n3174.eng"
    n3174_path = asset_store.resolve_asset(AssetCategory.MOTORS, n3174_eng)
    n3174_curve = parse_eng_file(n3174_path)
    diam_m, length_m, prop_mass_kg, total_mass_kg = _read_eng_header_masses_and_dims(n3174_path)
    dry_mass_kg = round(total_mass_kg - prop_mass_kg, 9)
    inner_r = base_casing.inner_radius_m
    wall_t = round((diam_m / 2.0) - inner_r, 9)
    n3174_casing = MotorCasingSpec(
        inner_radius_m=inner_r,
        wall_thickness_m=wall_t,
        length_m=length_m,
        internal_clearance_m=0.04,
        yield_strength_pa=yield_strength_pa,
        dry_mass_kg=dry_mass_kg,
        dry_inertia_kg_m2=compute_motor_casing_dry_inertia_kg_m2(
            dry_mass_kg=dry_mass_kg,
            inner_radius_m=inner_r,
            wall_thickness_m=wall_t,
            length_m=length_m,
        ),
        center_of_dry_mass_m=length_m / 2.0,
    )
    prop_density = 1841.0
    grain_count = 6
    grain_len = 0.18
    grain_outer_r = 0.049345
    grain_inner_r = math.sqrt(
        grain_outer_r**2 - (prop_mass_kg / prop_density) / (math.pi * grain_count * grain_len)
    )
    n3174_grains = tuple(
        GrainSpec(length_m=grain_len, outer_radius_m=grain_outer_r, inner_radius_m=grain_inner_r)
        for _ in range(grain_count)
    )
    n3174_preset = MotorPreset(
        name="medusa_n3174",
        motor_asset=None,
        thrust_curve_asset=n3174_eng,
        casing=n3174_casing,
        grain_separation_m=grain_sep,
        grains_center_of_mass_m=length_m / 2.0,
        nozzle_position_m=nozzle_pos,
        propellant_name="Nakka - KNSB (2)",
        fallback_grains=n3174_grains,
        propellant_density_kg_m3=prop_density,
        nozzle=NozzleSpec(
            throat_radius_m=float(motor_cfg["throat_radius"]),
            exit_radius_m=float(motor_cfg["nozzle_radius"]),
            position_m=nozzle_pos,
            throat_length_m=0.005,
            converging_angle_deg=45.0,
            diverging_angle_deg=15.0,
            efficiency=0.85,
        ),
        burn_time_s=(n3174_curve[0][0], n3174_curve[-1][0]),
    )
    _validate_motor_preset_fit(n3174_preset, n3174_curve)
    presets.append(n3174_preset)

    return tuple(presets)


def _build_site_presets(
    asset_store: AssetStore,
    ambiente: dict[str, Any],
    dicionario_nc: dict[str, str | None],
) -> dict[str, EnvironmentSpec]:
    var_map = NetCdfVariableMap(
        time=str(dicionario_nc["time"]),
        latitude=str(dicionario_nc["latitude"]),
        longitude=str(dicionario_nc["longitude"]),
        level=str(dicionario_nc["level"]),
        temperature=str(dicionario_nc["temperature"]),
        surface_geopotential_height=dicionario_nc["surface_geopotential_height"],
        geopotential_height=dicionario_nc["geopotential_height"],
        geopotential=str(dicionario_nc["geopotential"]),
        u_wind=str(dicionario_nc["u_wind"]),
        v_wind=str(dicionario_nc["v_wind"]),
        ensemble_number="number",
    )
    y, m, d, h = ambiente["date"]
    irec_date = (int(y), int(m), int(d), int(h))
    irec_lat = float(ambiente["latitude"])
    irec_lon = float(ambiente["longitude"])
    irec_elev = float(ambiente["elevation"])

    sites = {
        "irec_oper": EnvironmentSpec(
            name="Spaceport America (IREC)",
            atmosphere_asset="irec_era5_oper.nc",
            dataset_kind=Era5DatasetKind.OPER,
            ensemble_member=None,
            date_utc=irec_date,
            latitude_deg=irec_lat,
            longitude_deg=irec_lon,
            elevation_m=irec_elev,
            variable_map=var_map,
        ),
        "irec_enda": EnvironmentSpec(
            name="Spaceport America (IREC ENDA)",
            atmosphere_asset="irec_era5_enda.nc",
            dataset_kind=Era5DatasetKind.ENDA,
            ensemble_member=0,
            date_utc=irec_date,
            latitude_deg=irec_lat,
            longitude_deg=irec_lon,
            elevation_m=irec_elev,
            variable_map=var_map,
        ),
        "irec_enda_grid": EnvironmentSpec(
            name="Spaceport America (IREC ENDA Grid)",
            atmosphere_asset="irec_era5_enda_grid.nc",
            dataset_kind=Era5DatasetKind.ENDA,
            ensemble_member=0,
            date_utc=irec_date,
            latitude_deg=irec_lat,
            longitude_deg=irec_lon,
            elevation_m=irec_elev,
            variable_map=var_map,
        ),
        "iacanga_lasc_oper": EnvironmentSpec(
            name="Iacanga (LASC)",
            atmosphere_asset="iacanga_lasc_era5_oper.nc",
            dataset_kind=Era5DatasetKind.OPER,
            ensemble_member=None,
            date_utc=(2025, 11, 6, 12),
            latitude_deg=-21.88,
            longitude_deg=-49.02,
            elevation_m=422.0,
            variable_map=var_map,
        ),
        "iacanga_lasc_enda": EnvironmentSpec(
            name="Iacanga (LASC ENDA)",
            atmosphere_asset="iacanga_lasc_era5_enda.nc",
            dataset_kind=Era5DatasetKind.ENDA,
            ensemble_member=0,
            date_utc=(2025, 11, 6, 12),
            latitude_deg=-22.0,
            longitude_deg=-49.0,
            elevation_m=422.0,
            variable_map=var_map,
        ),
    }

    for spec in sites.values():
        asset_store.resolve_asset(AssetCategory.ATMOSPHERE, spec.atmosphere_asset)
    return sites


def migrate_catalog(repo_root: Path | None = None) -> list[Path]:
    """Generate validated data/catalog/{rockets,motors,sites,limits}/*.json files."""
    _ensure_repo_root_on_sys_path()
    from backend.basic import dicionario
    from usuario.limites import LIMITES

    paths = resolve_storage_paths(repo_root)
    asset_store = AssetStore(paths)
    catalog_store = CatalogStore(paths, asset_store=asset_store)

    rocket = _build_rocket_preset(asset_store, dicionario)
    _verify_rocket_dry_mass(rocket, float(dicionario.FOGUETE["mass"]))

    written: list[Path] = []
    written.append(catalog_store.save_limits(_build_safety_limits(LIMITES), preset_id="default"))
    written.append(catalog_store.save_rocket(rocket))
    for motor in _build_motor_presets(asset_store, dicionario.MOTOR, LIMITES):
        written.append(catalog_store.save_motor(motor))
    for site_id, site in _build_site_presets(
        asset_store, dicionario.AMBIENTE, dicionario.DICIONARIO_NC
    ).items():
        written.append(catalog_store.save_site(site, preset_id=site_id))
    return written


def _verify_rocket_dry_mass(rocket: RocketPreset, expected_kg: float) -> None:
    total = sum(
        derive_component_properties(comp, rocket.radius_m).mass_kg
        for comp in rocket.components
    )
    if not math.isclose(total, expected_kg, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"Migrated dry mass {total} != legacy {expected_kg}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Migrate legacy Hefesto presets into data/catalog/*.json"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Optional target repository root (defaults to workspace root)",
    )
    args = parser.parse_args(argv)
    written = migrate_catalog(args.repo_root)
    for path in written:
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
