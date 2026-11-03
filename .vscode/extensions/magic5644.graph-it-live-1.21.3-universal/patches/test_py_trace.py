"""Testes do micro-tracer py_trace.py (execucao real via subprocess)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_candidate = Path(__file__).resolve().parent.parent / "tracer" / "py_trace.py"
TRACER = _candidate if _candidate.exists() else Path(__file__).with_name("py_trace.py")


def run_tracer(
    workspace: Path,
    out: Path,
    target: list[str],
    max_calls: int | None = None,
) -> dict:
    cmd = [
        sys.executable,
        str(TRACER),
        "--workspace",
        str(workspace),
        "--out",
        str(out),
    ]
    if max_calls is not None:
        cmd += ["--max-calls", str(max_calls)]
    cmd += ["--", *target]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert out.exists(), proc.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def edges(data: dict) -> set[tuple[str, str]]:
    return {(e["source"], e["target"]) for e in data["edges"]}


def test_import_puro_nao_gera_aresta(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    write(ws / "mod_b.py", "def calc():\n    return 42\n")
    write(ws / "imp.py", "import mod_b\n")
    write(ws / "caller.py", "import mod_b\n\nmod_b.calc()\n")

    pure = run_tracer(ws, tmp_path / "pure.json", ["imp.py"])
    assert (str(ws / "imp.py"), str(ws / "mod_b.py")) not in edges(pure)
    assert pure["edges"] == []

    called = run_tracer(ws, tmp_path / "called.json", ["caller.py"])
    pair = (str(ws / "caller.py"), str(ws / "mod_b.py"))
    assert pair in edges(called)
    edge = next(e for e in called["edges"] if (e["source"], e["target"]) == pair)
    assert edge["calls"] == 1
    assert edge["top_func"] == "calc"
    assert called["nodes"][0] == str(ws / "caller.py")
    assert called["target_display"] == "caller.py"


def test_callback_atravessa_codigo_fora_do_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    outside = tmp_path / "outside"
    write(outside / "helper.py", "def run_cb(cb):\n    return cb()\n")
    write(ws / "mod_c.py", "def work():\n    return 7\n")
    write(
        ws / "mod_a.py",
        f"import sys\nsys.path.insert(0, {str(outside)!r})\n"
        "import helper\nimport mod_c\n\nhelper.run_cb(mod_c.work)\n",
    )

    data = run_tracer(ws, tmp_path / "cb.json", ["mod_a.py"])
    pair = (str(ws / "mod_a.py"), str(ws / "mod_c.py"))
    assert pair in edges(data), data["edges"]
    edge = next(e for e in data["edges"] if (e["source"], e["target"]) == pair)
    assert edge["calls"] == 1
    assert edge["top_func"] == "work"
    assert not any("helper.py" in node for node in data["nodes"])


@pytest.mark.parametrize("pattern", ["**/paths.py", "paths.py"])
def test_graphitignore_exclui_arquivo(tmp_path: Path, pattern: str) -> None:
    ws = tmp_path / "ws"
    write(ws / "src" / "paths.py", "def get():\n    return 1\n")
    write(
        ws / "src" / "app.py",
        "import os\nimport sys\n"
        "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
        "import paths\n\npaths.get()\n",
    )
    write(ws / ".graphitignore", f"# ignorado\n\n{pattern}\n")

    data = run_tracer(ws, tmp_path / "ignore.json", ["src/app.py"])
    assert data["nodes"], "app.py deveria estar nos nodes"
    assert not any(node.endswith("src/paths.py") for node in data["nodes"])
    assert not any(
        edge["source"].endswith("src/paths.py")
        or edge["target"].endswith("src/paths.py")
        for edge in data["edges"]
    )


def test_max_calls_trunca_sem_quebrar_execucao(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    write(
        ws / "loop.py",
        "def work():\n    return 1\n\nfor _ in range(200):\n    work()\n",
    )

    data = run_tracer(ws, tmp_path / "loop.json", ["loop.py"], max_calls=15)
    assert data["truncated"] is True
    assert data["exit_code"] == 0
    assert data["total_calls"] >= 15
    assert data["version"] == 1
    assert not list(tmp_path.glob("loop.json.*.tmp"))


def test_modo_modulo_preenche_entrypoint(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    write(
        ws / "mod_main.py",
        "def helper():\n    return 3\n\n"
        "def main():\n    return helper()\n\n"
        'if __name__ == "__main__":\n    main()\n',
    )

    data = run_tracer(ws, tmp_path / "mod.json", ["-m", "mod_main"])
    assert data["entrypoint"], data
    assert data["entrypoint"].endswith("mod_main.py")
    assert data["nodes"][0] == data["entrypoint"]
    assert data["target_display"] == "mod_main"
    assert data["exit_code"] == 0


def test_ignora_arquivos_nao_py(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    write(
        ws / "ext.py",
        "src = compile(\n"
        '    "def f():\\n    return 1\\n",\n'
        f"    {str(ws / 'fake.pyx')!r},\n"
        '    "exec",\n'
        ")\n"
        "ns = {}\n"
        "exec(src, ns)\n"
        "ns['f']()\n",
    )

    data = run_tracer(ws, tmp_path / "ext.json", ["ext.py"])
    assert data["nodes"] == [str(ws / "ext.py")], data["nodes"]
    assert not any(node.endswith(".pyx") for node in data["nodes"])
    assert not any(
        edge["source"].endswith(".pyx") or edge["target"].endswith(".pyx")
        for edge in data["edges"]
    )
