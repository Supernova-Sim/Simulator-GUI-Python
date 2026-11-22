"""Architectural AST Gate and Phase 0 baseline verification tests."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PACKAGE_ROOT = REPO_ROOT / "src" / "hefesto"
FRONTEND_ROOT = REPO_ROOT / "frontend"

VALID_HEFESTO_LAYERS = frozenset({"domain", "physics", "storage", "adapters", "services"})
FORBIDDEN_SEGMENTS = frozenset({"basic", "utils", "helpers", "misc", "api", "usuario"})
FORBIDDEN_LEGACY_ROOTS = frozenset({"backend", "usuario"})
NO_PRINT_LAYERS = frozenset({"domain", "physics", "services"})
DICT_BASE_NAMES = frozenset({"dict", "Dict", "Mapping", "MutableMapping"})

ALLOWED_LAYER_IMPORTS: dict[str, frozenset[str]] = {
    "root": frozenset(),
    "domain": frozenset({"domain"}),
    "physics": frozenset({"domain", "physics"}),
    "storage": frozenset({"domain", "storage"}),
    "adapters": frozenset({"domain", "adapters"}),
    "services": frozenset({"domain", "physics", "storage", "adapters", "services"}),
    "frontend": frozenset({"domain", "services", "frontend"}),
}

FORBIDDEN_EXTERNAL_IMPORTS: dict[str, frozenset[str]] = {
    "root": frozenset(),
    "domain": frozenset(
        {
            "io",
            "os",
            "pathlib",
            "shutil",
            "subprocess",
            "socket",
            "http",
            "urllib",
            "sqlite3",
            "pickle",
            "tempfile",
            "glob",
            "json",
            "csv",
            "yaml",
            "netCDF4",
            "rocketpy",
            "openmotor",
            "motorlib",
            "uilib",
            "matplotlib",
            "nicegui",
            "plotly",
            "PyQt6",
        }
    ),
    "physics": frozenset(
        {"yaml", "rocketpy", "openmotor", "motorlib", "uilib", "nicegui", "plotly", "PyQt6"}
    ),
    "storage": frozenset(
        {"yaml", "openmotor", "motorlib", "uilib", "rocketpy", "nicegui", "plotly", "PyQt6"}
    ),
    "adapters": frozenset({"rocketpy", "openmotor", "motorlib", "uilib", "nicegui", "plotly"}),
    "services": frozenset(
        {"rocketpy", "openmotor", "motorlib", "uilib", "yaml", "nicegui", "plotly", "PyQt6"}
    ),
    "frontend": frozenset(
        {"rocketpy", "openmotor", "motorlib", "uilib", "yaml", "netCDF4", "PyQt6"}
    ),
}

ADAPTER_SUBPACKAGE_ALLOWED_EXTERNALS: dict[str, frozenset[str]] = {
    "hefesto.adapters.rocketpy": frozenset({"rocketpy"}),
    "hefesto.adapters.openmotor": frozenset({"openmotor", "motorlib", "uilib"}),
}


def _forbidden_externals_for_module(info: ModuleInfo) -> frozenset[str]:
    base = FORBIDDEN_EXTERNAL_IMPORTS[info.layer]
    if info.layer != "adapters":
        return base
    for prefix, allowed in ADAPTER_SUBPACKAGE_ALLOWED_EXTERNALS.items():
        if info.module_name == prefix or info.module_name.startswith(f"{prefix}."):
            return base - allowed
    return base


@dataclass(frozen=True)
class ModuleInfo:
    """Resolved module metadata for a source file under src/hefesto or frontend."""

    rel_path: str
    module_name: str
    layer: str
    is_package: bool


def _classify_file(path: Path, repo_root: Path) -> ModuleInfo:
    src_hefesto = repo_root / "src" / "hefesto"
    frontend_dir = repo_root / "frontend"

    if path.is_relative_to(src_hefesto):
        rel_parts = path.relative_to(src_hefesto).parts
        rel_display = path.relative_to(repo_root).as_posix()
        is_pkg = path.name == "__init__.py"
        if rel_parts == ("__init__.py",):
            return ModuleInfo(rel_display, "hefesto", "root", True)
        top = rel_parts[0]
        if top not in VALID_HEFESTO_LAYERS:
            raise ValueError(f"Invalid top-level hefesto module/package: {rel_display}")
        stem_parts = rel_parts[:-1] if is_pkg else (*rel_parts[:-1], path.stem)
        module_name = ".".join(("hefesto", *stem_parts))
        return ModuleInfo(rel_display, module_name, top, is_pkg)

    if path.is_relative_to(frontend_dir):
        rel_parts = path.relative_to(frontend_dir).parts
        rel_display = path.relative_to(repo_root).as_posix()
        is_pkg = path.name == "__init__.py"
        stem_parts = rel_parts[:-1] if is_pkg else (*rel_parts[:-1], path.stem)
        module_name = ".".join(("frontend", *stem_parts))
        return ModuleInfo(rel_display, module_name, "frontend", is_pkg)

    raise ValueError(f"Path outside audited roots: {path}")


def _resolve_relative_base(current_module: str, is_package: bool, level: int) -> str:
    pkg_parts = current_module.split(".") if is_package else current_module.split(".")[:-1]
    drop = level - 1
    if drop > len(pkg_parts):
        return ""
    return ".".join(pkg_parts[: len(pkg_parts) - drop])


def _extract_imported_modules(
    tree: ast.AST,
    current_module: str,
    is_package: bool,
) -> list[tuple[int, str]]:
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                base = _resolve_relative_base(current_module, is_package, node.level)
                if node.module:
                    target = f"{base}.{node.module}" if base else node.module
                    imports.append((node.lineno, target))
                else:
                    for alias in node.names:
                        target = f"{base}.{alias.name}" if base else alias.name
                        imports.append((node.lineno, target))
            elif node.module:
                imports.append((node.lineno, node.module))
                if node.module in {"hefesto", "frontend"}:
                    for alias in node.names:
                        imports.append((node.lineno, f"{node.module}.{alias.name}"))
    return imports


def _module_to_layer(module_name: str) -> str | None:
    parts = module_name.split(".")
    if parts[0] == "frontend":
        return "frontend"
    if parts[0] == "hefesto":
        if len(parts) == 1:
            return "root"
        if parts[1] in VALID_HEFESTO_LAYERS:
            return parts[1]
        if parts[1] == "frontend":
            return "frontend"
    return None


def _is_dict_any_subscript(node: ast.Subscript) -> bool:
    base_name = ""
    if isinstance(node.value, ast.Name):
        base_name = node.value.id
    elif isinstance(node.value, ast.Attribute):
        base_name = node.value.attr
    if base_name not in DICT_BASE_NAMES:
        return False

    for child in ast.walk(node.slice):
        if isinstance(child, ast.Name) and child.id == "Any":
            return True
        if isinstance(child, ast.Attribute) and child.attr == "Any":
            return True
    return False


def _annotation_has_dict_any(expr: ast.expr | None) -> bool:
    if expr is None:
        return False
    return any(
        isinstance(node, ast.Subscript) and _is_dict_any_subscript(node)
        for node in ast.walk(expr)
    )


def _check_dict_any_annotations(
    tree: ast.Module,
    rel_path: str,
    layer: str,
) -> list[str]:
    violations: list[str] = []
    strict_all = layer in {"domain", "services"}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_public = not node.name.startswith("_")
            if not (strict_all or is_public):
                continue
            args = [
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            ]
            if node.args.vararg is not None:
                args.append(node.args.vararg)
            if node.args.kwarg is not None:
                args.append(node.args.kwarg)
            for arg in args:
                if _annotation_has_dict_any(arg.annotation):
                    violations.append(
                        f"{rel_path}:{node.lineno}: dict[..., Any] forbidden on '{node.name}'"
                    )
            if _annotation_has_dict_any(node.returns):
                violations.append(
                    f"{rel_path}:{node.lineno}: dict[..., Any] forbidden in return of '{node.name}'"
                )
        elif isinstance(node, ast.AnnAssign) and _annotation_has_dict_any(node.annotation):
            if isinstance(node.target, ast.Name):
                is_public = not node.target.id.startswith("_")
                if strict_all or is_public:
                    violations.append(
                        f"{rel_path}:{node.lineno}: dict[..., Any] forbidden on '{node.target.id}'"
                    )
    return violations


def check_source_violations(
    source: str,
    info: ModuleInfo,
) -> tuple[list[str], set[str]]:
    """Inspect one module's AST for architectural violations and internal edges."""
    tree = ast.parse(source, filename=info.rel_path)
    violations: list[str] = []
    internal_edges: set[str] = set()

    allowed_layers = ALLOWED_LAYER_IMPORTS[info.layer]
    forbidden_externals = _forbidden_externals_for_module(info)

    for lineno, mod in _extract_imported_modules(tree, info.module_name, info.is_package):
        root_pkg = mod.split(".")[0]
        if root_pkg in FORBIDDEN_LEGACY_ROOTS:
            violations.append(f"{info.rel_path}:{lineno}: legacy import '{mod}' is forbidden")
            continue

        if root_pkg in forbidden_externals or mod in forbidden_externals:
            violations.append(
                f"{info.rel_path}:{lineno}: external import '{mod}' forbidden in '{info.layer}'"
            )
            continue

        target_layer = _module_to_layer(mod)
        if target_layer is not None:
            if mod != info.module_name:
                internal_edges.add(mod)
            if target_layer not in allowed_layers:
                violations.append(
                    f"{info.rel_path}:{lineno}: layer '{info.layer}' cannot import "
                    f"'{target_layer}' ('{mod}')"
                )

    if info.layer in NO_PRINT_LAYERS:
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                violations.append(
                    f"{info.rel_path}:{node.lineno}: print() forbidden in '{info.layer}'"
                )

    if info.layer == "domain":
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "open"
            ):
                violations.append(f"{info.rel_path}:{node.lineno}: open() forbidden in 'domain'")

    violations.extend(_check_dict_any_annotations(tree, info.rel_path, info.layer))
    return violations, internal_edges


def detect_import_cycles(graph: dict[str, set[str]]) -> list[str]:
    """Return formatted cycle strings if the internal module graph contains cycles."""
    state: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[str] = []

    def dfs(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for neighbor in sorted(graph.get(node, ())):
            if neighbor not in graph:
                continue
            nbr_state = state.get(neighbor, 0)
            if nbr_state == 1:
                idx = stack.index(neighbor)
                cycles.append(" -> ".join([*stack[idx:], neighbor]))
            elif nbr_state == 0:
                dfs(neighbor)
        stack.pop()
        state[node] = 2

    for mod in sorted(graph):
        if state.get(mod, 0) == 0:
            dfs(mod)
    return cycles


def audit_repository(repo_root: Path) -> list[str]:
    """Audit all Python files under src/hefesto and frontend for architectural rules."""
    violations: list[str] = []
    graph: dict[str, set[str]] = {}
    audited_roots = [repo_root / "src" / "hefesto", repo_root / "frontend"]

    for root in audited_roots:
        if not root.exists():
            continue
        for entry in sorted(root.rglob("*")):
            if "__pycache__" in entry.parts:
                continue
            rel_parts = entry.relative_to(root).parts
            for segment in rel_parts:
                name = Path(segment).stem if entry.is_file() and segment == entry.name else segment
                if name.lower() in FORBIDDEN_SEGMENTS:
                    violations.append(
                        f"{entry.relative_to(repo_root).as_posix()}: "
                        f"forbidden segment '{segment}'"
                    )
            if entry.is_file() and entry.suffix == ".py":
                try:
                    info = _classify_file(entry, repo_root)
                except ValueError as exc:
                    violations.append(str(exc))
                    continue
                source = entry.read_text(encoding="utf-8")
                file_violations, edges = check_source_violations(source, info)
                violations.extend(file_violations)
                graph[info.module_name] = edges

    for cycle in detect_import_cycles(graph):
        violations.append(f"Import cycle detected: {cycle}")
    return violations


def test_repository_architecture_has_no_violations() -> None:
    assert SRC_PACKAGE_ROOT.is_dir()
    assert audit_repository(REPO_ROOT) == []


def test_raw_assets_exist_in_data_assets() -> None:
    assets_root = REPO_ROOT / "data" / "assets"
    expected_assets = {
        "motors/medusa_knsb_a.ric",
        "motors/medusa_knsb_a.eng",
        "motors/medusa_n2792_v1.ric",
        "motors/medusa_n2792_v1.eng",
        "motors/medusa_n3002_v2.ric",
        "motors/medusa_n3002_v2.eng",
        "motors/medusa_n3174.eng",
        "drag/power_off.csv",
        "drag/power_on.csv",
        "atmosphere/irec_era5_oper.nc",
        "atmosphere/irec_era5_enda.nc",
        "atmosphere/irec_era5_enda_grid.nc",
        "atmosphere/iacanga_lasc_era5_oper.nc",
        "atmosphere/iacanga_lasc_era5_enda.nc",
    }
    actual_assets = {
        path.relative_to(assets_root).as_posix()
        for path in assets_root.rglob("*")
        if path.is_file()
    }
    assert actual_assets == expected_assets


def test_golden_baseline_exists_and_references_relative_assets() -> None:
    baseline_path = REPO_ROOT / "tests" / "golden" / "hefesto_baseline.json"
    data = json.loads(baseline_path.read_text(encoding="utf-8"))

    assert data["schema_version"] == 1
    assert 18.84 <= data["dry_mass"]["wall_2mm_kg"] <= 18.86
    assert 21.64 <= data["dry_mass"]["wall_3mm_kg"] <= 21.65

    assets_root = REPO_ROOT / "data" / "assets"
    flight_inputs = data["rocketpy_baseline_88deg"]["inputs"]
    flight_metrics = data["rocketpy_baseline_88deg"]["metrics"]
    asset_checks = [
        ("atmosphere", flight_inputs["atmosphere_asset"]),
        ("motors", flight_inputs["thrust_curve_asset"]),
        ("drag", flight_inputs["power_off_drag_asset"]),
        ("drag", flight_inputs["power_on_drag_asset"]),
    ]
    for category, asset_name in asset_checks:
        assert not Path(asset_name).is_absolute()
        assert (assets_root / category / asset_name).exists()

    assert flight_metrics["apogee_agl_m"] > 3500.0
    assert flight_metrics["min_static_margin_calibers"] > 2.0
    assert flight_metrics["total_impulse_ns"] > 11500.0
    assert len(data["safety_baseline_medusa_knsb_a"]["checks"]) == 5


def test_ast_gate_rejects_yaml_in_storage() -> None:
    info = ModuleInfo("src/hefesto/storage/loader.py", "hefesto.storage.loader", "storage", False)
    violations, _ = check_source_violations("import yaml\n", info)
    assert any("yaml" in v for v in violations)


def test_ast_gate_rejects_print_in_domain_physics_services() -> None:
    for layer in ("domain", "physics", "services"):
        info = ModuleInfo(f"src/hefesto/{layer}/mod.py", f"hefesto.{layer}.mod", layer, False)
        violations, _ = check_source_violations('print("debug")\n', info)
        assert any("print()" in v for v in violations)


def test_ast_gate_rejects_reverse_and_sibling_layer_imports() -> None:
    cases = [
        ("domain", "from hefesto.physics import rocket\n"),
        ("physics", "from hefesto.storage import catalog\n"),
        ("storage", "from hefesto.adapters import openmotor\n"),
        ("adapters", "from hefesto.services import runner\n"),
        ("services", "import frontend.app\n"),
        ("frontend", "from hefesto.physics import rocket\n"),
        ("frontend", "from hefesto.storage import catalog\n"),
    ]
    for layer, code in cases:
        prefix = "frontend" if layer == "frontend" else f"src/hefesto/{layer}"
        mod = "frontend.app" if layer == "frontend" else f"hefesto.{layer}.mod"
        info = ModuleInfo(f"{prefix}/mod.py", mod, layer, False)
        violations, _ = check_source_violations(code, info)
        assert violations, f"Expected violation for {layer}: {code}"


def test_ast_gate_rejects_io_and_sim_imports_in_domain() -> None:
    info = ModuleInfo("src/hefesto/domain/models.py", "hefesto.domain.models", "domain", False)
    for snippet in (
        "from pathlib import Path\n",
        "import rocketpy\n",
        "import netCDF4\n",
        "import yaml\n",
        "def f() -> None:\n    open('x')\n",
    ):
        violations, _ = check_source_violations(snippet, info)
        assert violations, f"Expected domain purity violation for: {snippet}"


def test_ast_gate_rejects_dict_str_any_between_layers() -> None:
    info = ModuleInfo("src/hefesto/services/run.py", "hefesto.services.run", "services", False)
    snippet = (
        "from typing import Any\n"
        "def run_sim(payload: dict[str, Any]) -> dict[str, Any]:\n"
        "    return payload\n"
    )
    violations, _ = check_source_violations(snippet, info)
    assert len(violations) == 2


def test_ast_gate_rejects_forbidden_directories_and_legacy_imports(tmp_path: Path) -> None:
    (tmp_path / "src" / "hefesto" / "utils").mkdir(parents=True)
    (tmp_path / "src" / "hefesto" / "utils" / "bad.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "src" / "hefesto" / "domain").mkdir(parents=True)
    (tmp_path / "src" / "hefesto" / "domain" / "bad.py").write_text(
        "from backend.basic import dicionario\n", encoding="utf-8"
    )
    violations = audit_repository(tmp_path)
    assert any("utils" in v for v in violations)
    assert any("backend.basic" in v for v in violations)


def test_ast_gate_rejects_import_cycles() -> None:
    cycles = detect_import_cycles(
        {
            "hefesto.domain.a": {"hefesto.domain.b"},
            "hefesto.domain.b": {"hefesto.domain.a"},
        }
    )
    assert cycles == ["hefesto.domain.a -> hefesto.domain.b -> hefesto.domain.a"]


def test_ast_gate_isolates_rocketpy_and_openmotor_to_their_adapter_subpackages() -> None:
    rocketpy_mod = ModuleInfo(
        "src/hefesto/adapters/rocketpy/motor_builder.py",
        "hefesto.adapters.rocketpy.motor_builder",
        "adapters",
        False,
    )
    assert check_source_violations("from rocketpy import SolidMotor\n", rocketpy_mod)[0] == []
    assert check_source_violations("import motorlib\n", rocketpy_mod)[0]
    assert check_source_violations("import uilib\n", rocketpy_mod)[0]

    openmotor_mod = ModuleInfo(
        "src/hefesto/adapters/openmotor/runner.py",
        "hefesto.adapters.openmotor.runner",
        "adapters",
        False,
    )
    assert check_source_violations("import motorlib\nimport uilib\n", openmotor_mod)[0] == []
    assert check_source_violations("import rocketpy\n", openmotor_mod)[0]

    for layer, rel_path, mod_name in (
        ("domain", "src/hefesto/domain/motor.py", "hefesto.domain.motor"),
        ("physics", "src/hefesto/physics/propulsion.py", "hefesto.physics.propulsion"),
        ("storage", "src/hefesto/storage/asset_store.py", "hefesto.storage.asset_store"),
        ("services", "src/hefesto/services/sim.py", "hefesto.services.sim"),
        ("frontend", "frontend/app.py", "frontend.app"),
        ("adapters", "src/hefesto/adapters/__init__.py", "hefesto.adapters"),
        (
            "adapters",
            "src/hefesto/adapters/aerodynamics/database_drag.py",
            "hefesto.adapters.aerodynamics.database_drag",
        ),
    ):
        info = ModuleInfo(rel_path, mod_name, layer, mod_name == "hefesto.adapters")
        violations, _ = check_source_violations("import rocketpy\n", info)
        assert any("rocketpy" in v for v in violations), f"Expected rocketpy block for {mod_name}"
