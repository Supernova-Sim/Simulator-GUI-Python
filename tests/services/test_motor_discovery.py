"""Service tests: .ric auto-discovery, persistent cache, and upload import."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from hefesto.services import (
    discover_ric_motors,
    get_catalog_overview,
    import_openmotor_ric,
    load_motor_preset,
    load_motor_spec,
    motor_discovery_service,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RIC_SOURCE = REPO_ROOT / "data" / "assets" / "motors" / "m1001voltas.ric"


def _seed_isolated_workspace(tmp_path: Path) -> Path:
    shutil.copytree(REPO_ROOT / "data" / "assets", tmp_path / "data" / "assets")
    shutil.copytree(REPO_ROOT / "data" / "catalog", tmp_path / "data" / "catalog")
    return tmp_path


def test_discovery_lists_ric_assets_without_catalog_preset(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    shutil.copyfile(RIC_SOURCE, root / "data" / "assets" / "motors" / "novo_motor.ric")

    assets = {asset.preset_id: asset for asset in discover_ric_motors(root)}

    assert {"m1001voltas", "novo_motor"}.issubset(assets)
    assert assets["novo_motor"].motor_asset == "novo_motor.ric"
    assert assets["novo_motor"].warnings == ()
    # Motors already represented by a catalog JSON must not appear twice.
    assert "medusa_knsb_a" not in assets
    assert "medusa_n3002_v2" not in assets

    overview = get_catalog_overview(root)
    assert {asset.preset_id for asset in overview.discovered_ric_motors} == set(assets)
    assert "medusa_knsb_a" in overview.motor_presets


def test_discovery_inherits_calibrated_casing_from_identical_catalog_asset(
    tmp_path: Path,
) -> None:
    root = _seed_isolated_workspace(tmp_path)

    assets = {asset.preset_id: asset for asset in discover_ric_motors(root)}
    assert assets["m1001voltas"].warnings == ()

    inherited = load_motor_preset("m1001voltas", repo_root=root)
    template = load_motor_preset("medusa_knsb_a", repo_root=root)

    assert inherited.casing == template.casing
    assert inherited.grain_separation_m == template.grain_separation_m
    assert inherited.nozzle_position_m == template.nozzle_position_m


def test_new_ric_gets_synthesized_casing_with_warning(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    edited = RIC_SOURCE.read_text(encoding="utf-8").replace("length: 0.16", "length: 0.15")
    (root / "data" / "assets" / "motors" / "inesperado.ric").write_text(
        edited, encoding="utf-8"
    )

    assets = {asset.preset_id: asset for asset in discover_ric_motors(root)}
    assert assets["inesperado"].warnings
    assert "sintetizada" in assets["inesperado"].warnings[0]

    synthesized = load_motor_preset("inesperado", repo_root=root)
    template = load_motor_preset("medusa_knsb_a", repo_root=root)
    assert synthesized.casing.dry_mass_kg < template.casing.dry_mass_kg
    assert synthesized.casing.wall_thickness_m == pytest.approx(0.002)


def test_discovery_uses_persistent_cache_instead_of_reconverting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _seed_isolated_workspace(tmp_path)
    first = {asset.preset_id for asset in discover_ric_motors(root)}
    cache_file = root / "data" / "cache" / "motors" / "discovery.json"
    assert cache_file.is_file()

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("cache miss: .ric was converted twice")

    monkeypatch.setattr(motor_discovery_service, "_cache_entry_from_disk", _fail)
    second = {asset.preset_id for asset in discover_ric_motors(root)}

    assert second == first


def test_discovery_reconverts_when_ric_content_changes(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    mutant = root / "data" / "assets" / "motors" / "mutante.ric"
    mutant.write_bytes(RIC_SOURCE.read_bytes())
    assert {asset.preset_id for asset in discover_ric_motors(root)} >= {"mutante"}

    mutant.write_text("data: [corrupt", encoding="utf-8")
    assets = {asset.preset_id: asset for asset in discover_ric_motors(root)}

    assert assets["mutante"].warnings


def test_corrupt_ric_is_reported_without_breaking_the_listing(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    (root / "data" / "assets" / "motors" / "quebrado.ric").write_text(
        "data: [corrupt", encoding="utf-8"
    )

    assets = {asset.preset_id: asset for asset in discover_ric_motors(root)}

    broken = assets["quebrado"]
    assert broken.warnings
    assert "quebrado.ric" in broken.warnings[0]
    assert "\n" not in broken.warnings[0]
    assert "m1001voltas" in assets


def test_import_openmotor_ric_saves_asset_and_catalog_preset(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    raw = RIC_SOURCE.read_bytes()

    preset = import_openmotor_ric("Motor Teste (v2).ric", raw, repo_root=root)

    assert preset.name == "Motor_Teste_v2"
    assert preset.motor_asset == "Motor_Teste_v2.ric"
    assert preset.nozzle is not None
    assert preset.fallback_grains
    assert preset.casing.inner_radius_m > max(
        grain.outer_radius_m for grain in preset.fallback_grains
    )

    asset_path = root / "data" / "assets" / "motors" / "Motor_Teste_v2.ric"
    catalog_path = root / "data" / "catalog" / "motors" / "Motor_Teste_v2.json"
    assert asset_path.read_bytes() == raw
    assert catalog_path.is_file()
    assert load_motor_preset("Motor_Teste_v2", repo_root=root) == preset

    overview = get_catalog_overview(root)
    assert preset.name in overview.motor_presets
    assert preset.name not in {asset.preset_id for asset in overview.discovered_ric_motors}


def test_import_without_catalog_remains_selectable_as_ric_asset(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)

    preset = import_openmotor_ric(
        "avulso.ric",
        RIC_SOURCE.read_bytes(),
        save_to_catalog=False,
        repo_root=root,
    )

    assert not (root / "data" / "catalog" / "motors" / "avulso.json").exists()
    assert "avulso" in {asset.preset_id for asset in discover_ric_motors(root)}

    spec = load_motor_spec("avulso", repo_root=root)
    assert spec.name == preset.name
    assert spec.motor_asset == "avulso.ric"
    assert len(spec.thrust_curve) >= 2


def test_import_rejects_invalid_ric_and_preserves_existing_asset(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    target = root / "data" / "assets" / "motors" / "m1001voltas.ric"
    original = target.read_bytes()

    with pytest.raises(ValueError, match="inválido"):
        import_openmotor_ric("m1001voltas.ric", b"data: [corrupt", repo_root=root)
    with pytest.raises(ValueError, match="vazio"):
        import_openmotor_ric("vazio.ric", b"", repo_root=root)
    with pytest.raises(ValueError, match=r"\.ric"):
        import_openmotor_ric("motor.eng", b"qualquer", repo_root=root)

    assert target.read_bytes() == original
    assert not (root / "data" / "catalog" / "motors" / "m1001voltas.json").exists()


def test_cache_rehashes_ric_even_when_mtime_and_size_are_unchanged(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    mutant = root / "data" / "assets" / "motors" / "mutante.ric"
    original_text = RIC_SOURCE.read_text(encoding="utf-8")
    mutant.write_text(original_text, encoding="utf-8")

    first = load_motor_preset("mutante", repo_root=root)
    assert first.nozzle is not None
    assert first.nozzle.throat_radius_m == pytest.approx(0.034 / 2.0)

    original_stat = mutant.stat()
    mutated_text = original_text.replace("throat: 0.034", "throat: 0.035")
    assert len(mutated_text) == len(original_text)
    mutant.write_text(mutated_text, encoding="utf-8")
    # Defeat the old mtime+size cache heuristic: same byte length, same timestamps.
    os.utime(mutant, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    rewritten_stat = mutant.stat()
    assert rewritten_stat.st_size == original_stat.st_size
    assert rewritten_stat.st_mtime_ns == original_stat.st_mtime_ns

    second = load_motor_preset("mutante", repo_root=root)
    assert second.nozzle is not None
    assert second.nozzle.throat_radius_m == pytest.approx(0.035 / 2.0)


def test_cache_invalidates_when_sibling_eng_is_added_or_removed(tmp_path: Path) -> None:
    root = _seed_isolated_workspace(tmp_path)
    motor_path = root / "data" / "assets" / "motors" / "com_curva.ric"
    eng_path = root / "data" / "assets" / "motors" / "com_curva.eng"
    shutil.copyfile(RIC_SOURCE, motor_path)

    without_eng = load_motor_preset("com_curva", repo_root=root)
    assert without_eng.thrust_curve_asset is None

    shutil.copyfile(root / "data" / "assets" / "motors" / "medusa_knsb_a.eng", eng_path)
    with_eng = load_motor_preset("com_curva", repo_root=root)
    assert with_eng.thrust_curve_asset == "com_curva.eng"

    eng_path.unlink()
    without_eng_again = load_motor_preset("com_curva", repo_root=root)
    assert without_eng_again.thrust_curve_asset is None


def test_cache_invalidates_inherited_casing_when_catalog_template_changes(
    tmp_path: Path,
) -> None:
    root = _seed_isolated_workspace(tmp_path)
    before = load_motor_preset("m1001voltas", repo_root=root)
    assert before.casing.wall_thickness_m == pytest.approx(0.003175)

    motor_json = root / "data" / "catalog" / "motors" / "medusa_knsb_a.json"
    payload = json.loads(motor_json.read_text(encoding="utf-8"))
    payload["casing"]["wall_thickness_m"] = 0.004
    motor_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    after = load_motor_preset("m1001voltas", repo_root=root)
    assert after.casing.wall_thickness_m == pytest.approx(0.004)
