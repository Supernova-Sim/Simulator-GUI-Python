#!/usr/bin/env python3
"""Micro-tracer de execucao para o Graph-It-Live (stdlib apenas, Python >= 3.11).

Uso:
    python py_trace.py --workspace <dir> --out <json_path> [--max-calls N] -- <target_args...>

Alvos suportados:
    -- script.py args...            (caminho relativo ao workspace ou absoluto)
    -- -m modulo args...            (executa com runpy.run_module)

O tracer observa chamadas/retornos via sys.setprofile, monta um grafo de
arquivos do workspace (nos = arquivos executados, arestas = chamadas reais
entre arquivos) e grava um JSON de forma atomica ao final.
"""

from __future__ import annotations

import argparse
import atexit
import fnmatch
import json
import os
import runpy
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath
from types import CodeType, FrameType
from typing import Any

# Segmentos de diretorio que nunca entram no grafo.
IGNORED_SEGMENTS = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".graph-it",
    "node_modules",
    ".pytest_cache",
}

_MISSING = object()


# ---------------------------------------------------------------------------
# Escopo: quais arquivos pertencem ao workspace e ao grafo
# ---------------------------------------------------------------------------
class Scope:
    """Resolve (e memoriza) o caminho real de cada objeto de codigo."""

    def __init__(self, workspace: str) -> None:
        self.workspace = workspace.replace("\\", "/")
        self._root_prefix = self.workspace + "/"
        self._patterns = self._load_patterns()
        # Cache O(1): um CodeType representa um unico modulo compilado.
        self.code_cache: dict[CodeType, str | None] = {}

    def _load_patterns(self) -> list[str]:
        path = os.path.join(self.workspace, ".graphitignore")
        try:
            with open(path, encoding="utf-8") as fh:
                return [
                    line.strip()
                    for line in fh
                    if line.strip() and not line.strip().startswith("#")
                ]
        except OSError:
            return []

    def _ignored_rel(self, rel_posix: str) -> bool:
        """Testa o caminho relativo (POSIX) contra os padroes do .graphitignore."""
        pure = PurePosixPath(rel_posix)
        for pat in self._patterns:
            if pure.match(pat) or fnmatch.fnmatch(rel_posix, pat):
                return True
            # `**/paths.py` tambem deve casar `paths.py` na raiz.
            if pat.startswith("**/"):
                bare = pat[3:]
                if pure.match(bare) or fnmatch.fnmatch(rel_posix, bare):
                    return True
        return False

    def resolve(self, code: CodeType) -> str | None:
        """Caminho absoluto normalizado, ou None se fora do escopo."""
        if code not in self.code_cache:
            self.code_cache[code] = self._classify(code)
        return self.code_cache[code]

    def _classify(self, code: CodeType) -> str | None:
        filename = code.co_filename
        if not filename or filename.startswith("<") or not filename.endswith(".py"):
            return None  # ignora <string>, Cython (.pyx) e extensoes nativas
        real = os.path.realpath(filename).replace("\\", "/")
        if not real.startswith(self._root_prefix):
            return None  # stdlib, .venv, C, extensoes nativas...
        rel = real[len(self._root_prefix):]
        for segment in rel.split("/"):
            if segment in IGNORED_SEGMENTS or segment.startswith("<"):
                return None
        if self._ignored_rel(rel):
            return None
        return real


# ---------------------------------------------------------------------------
# Estatisticas do grafo
# ---------------------------------------------------------------------------
@dataclass
class EdgeStats:
    calls: int = 0
    time_ns: int = 0
    funcs: dict[str, int] = field(default_factory=dict)

    def top_func(self) -> str:
        if not self.funcs:
            return ""
        return max(self.funcs.items(), key=lambda item: item[1])[0]


class Tracer:
    """Hook de profiling + pilha sombra por thread.

    A pilha sombra guarda apenas frames do workspace. Frames externos
    (stdlib/.venv) sao transparentes: a chamada seguinte do workspace
    conecta-se ao ultimo arquivo ativo do workspace.
    """

    def __init__(self, scope: Scope, max_calls: int) -> None:
        self.scope = scope
        self.max_calls = max_calls
        self.total_calls = 0
        self.truncated = False
        self.executed_nodes: set[str] = set()
        self.edge_stats: dict[tuple[str, str], EdgeStats] = {}
        self.first_ws_file: str | None = None
        self._stacks: dict[int, list[tuple[str, str, int]]] = {}
        self._prev_profiler: Any = None
        self._active = False

    # -- instalacao / remocao ------------------------------------------------
    def install(self) -> None:
        self._prev_profiler = sys.getprofile()
        self._active = True
        sys.setprofile(self._on_event)
        threading.setprofile(self._on_event)

    def stop(self) -> None:
        if not self._active:
            return
        self._active = False
        sys.setprofile(self._prev_profiler)
        threading.setprofile(None)

    # -- hook ---------------------------------------------------------------
    def _on_event(self, frame: FrameType, event: str, arg: Any) -> None:
        # Encadeia um profiler pre-existente (ex.: debugpy) sem quebra-lo.
        prev = self._prev_profiler
        if prev is not None:
            prev(frame, event, arg)
        if event == "call" or event == "return":
            self._handle(frame, event)

    def _stack(self) -> list[tuple[str, str, int]]:
        ident = threading.get_ident()
        stack = self._stacks.get(ident)
        if stack is None:
            stack = self._stacks[ident] = []
        return stack

    def _handle(self, frame: FrameType, event: str) -> None:
        code = frame.f_code
        callee_file = self.scope.resolve(code)
        if callee_file is None:
            return  # frame fora do workspace: transparente

        if event == "call":
            self.total_calls += 1
            if self.total_calls > self.max_calls:
                self.truncated = True
                self.stop()  # corta o custo de profiling imediatamente
                return
            self.executed_nodes.add(callee_file)
            if self.first_ws_file is None:
                self.first_ws_file = callee_file
            func_name = getattr(code, "co_qualname", None) or code.co_name
            stack = self._stack()
            if stack:
                caller_file = stack[-1][0]
                # Ignora import puro (`<module>`): so chamadas reais contam.
                if caller_file != callee_file and code.co_name != "<module>":
                    edge = self.edge_stats.setdefault(
                        (caller_file, callee_file), EdgeStats()
                    )
                    edge.calls += 1
                    edge.funcs[func_name] = edge.funcs.get(func_name, 0) + 1
            stack.append((callee_file, func_name, time.perf_counter_ns()))
            return

        # event == "return"
        stack = self._stack()
        if not stack or stack[-1][0] != callee_file:
            return
        _, _, enter_ns = stack.pop()
        dt_ns = time.perf_counter_ns() - enter_ns
        if not stack or code.co_name == "<module>":
            return
        caller_file = stack[-1][0]
        if caller_file == callee_file:
            return
        # Nao soma tempo de novo se o mesmo par ja esta ativo mais abaixo
        # (recursao entre arquivos contaria em dobro).
        for i in range(len(stack) - 1):
            if stack[i][0] == caller_file and stack[i + 1][0] == callee_file:
                return
        edge = self.edge_stats.setdefault((caller_file, callee_file), EdgeStats())
        edge.time_ns += dt_ns


# ---------------------------------------------------------------------------
# Execucao do alvo
# ---------------------------------------------------------------------------
def _run_target(workspace: str, target: list[str]) -> str | None:
    """Executa o alvo e devolve o entrypoint (script) ou None em modo -m."""
    sys.path.insert(0, workspace)
    if target[:1] == ["-m"]:
        module = target[1]
        sys.argv = [module, *target[2:]]
        os.chdir(workspace)
        runpy.run_module(module, run_name="__main__", alter_sys=True)
        return None

    script = target[0]
    script_abs = script if os.path.isabs(script) else os.path.join(workspace, script)
    script_abs = os.path.realpath(script_abs)
    os.chdir(workspace)
    sys.argv = [script_abs, *target[1:]]
    sys.path.insert(0, os.path.dirname(script_abs))
    runpy.run_path(script_abs, run_name="__main__")
    return script_abs.replace("\\", "/")


def _target_display(workspace: str, target: list[str]) -> str:
    if target[:1] == ["-m"] and len(target) > 1:
        return "pytest" if target[1] == "pytest" else target[1]
    if not target:
        return ""
    raw = target[0]
    joined = raw if os.path.isabs(raw) else os.path.join(workspace, raw)
    script = os.path.realpath(joined).replace("\\", "/")
    root = workspace.replace("\\", "/")
    if script.startswith(root + "/"):
        return script[len(root) + 1:]
    return script


# ---------------------------------------------------------------------------
# Saida JSON atomica
# ---------------------------------------------------------------------------
def _ensure_git_exclude(workspace: str) -> None:
    """Garante .graph-it/ em info/exclude (repos normais e git worktrees)."""
    dot_git = os.path.join(workspace, ".git")
    git_dir = dot_git
    try:
        if os.path.isfile(dot_git):
            raw = open(dot_git, encoding="utf-8").read().strip()
            if raw.startswith("gitdir:"):
                gd = raw[7:].strip()
                git_dir = gd if os.path.isabs(gd) else os.path.normpath(os.path.join(workspace, gd))
                commondir_file = os.path.join(git_dir, "commondir")
                if os.path.isfile(commondir_file):
                    cd = open(commondir_file, encoding="utf-8").read().strip()
                    git_dir = cd if os.path.isabs(cd) else os.path.normpath(os.path.join(git_dir, cd))
        info_dir = os.path.join(git_dir, "info")
        if os.path.isdir(info_dir):
            ex_path = os.path.join(info_dir, "exclude")
            txt = open(ex_path, encoding="utf-8").read() if os.path.isfile(ex_path) else ""
            if ".graph-it" not in txt:
                sep = "" if (not txt or txt.endswith("\n")) else "\n"
                with open(ex_path, "a", encoding="utf-8") as fh:
                    fh.write(f"{sep}.graph-it/\n")
    except OSError:
        pass


def _write_json(out: str, payload: dict[str, Any]) -> None:
    if payload.get("workspace"):
        _ensure_git_exclude(str(payload["workspace"]))
    out_abs = os.path.abspath(out)
    parent = os.path.dirname(out_abs)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = f"{out_abs}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    os.replace(tmp, out_abs)


def _normalize(path: str) -> str:
    return os.path.realpath(path).replace("\\", "/")


def _build_payload(
    workspace: str,
    tracer: Tracer,
    entrypoint: str | None,
    exit_code: int,
    duration_ms: float,
    target_display: str,
) -> dict[str, Any]:
    nodes = sorted(tracer.executed_nodes)
    # Em modo -m nao ha script: o entrypoint e o primeiro arquivo do
    # workspace executado (ex.: conftest/primeiro teste do pytest).
    entrypoint = entrypoint or tracer.first_ws_file
    if entrypoint:
        entrypoint = _normalize(entrypoint)
        if entrypoint in nodes:
            nodes.remove(entrypoint)
        nodes.insert(0, entrypoint)
    edges = [
        {
            "source": source,
            "target": target,
            "calls": stats.calls,
            "time_ms": round(stats.time_ns / 1_000_000, 2),
            "top_func": stats.top_func(),
            "funcs": stats.funcs,
        }
        for (source, target), stats in sorted(
            tracer.edge_stats.items(), key=lambda item: (-item[1].calls, item[0])
        )
    ]
    return {
        "version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workspace": _normalize(workspace),
        "entrypoint": entrypoint,
        "target_display": target_display,
        "duration_ms": round(duration_ms, 2),
        "total_calls": tracer.total_calls,
        "truncated": tracer.truncated,
        "exit_code": exit_code,
        "nodes": nodes,
        "edges": edges,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    # Separa "-- alvo..." antes do argparse (preserva flags do alvo, como -m).
    if "--" in raw:
        cut = raw.index("--")
        own_args, target = raw[:cut], raw[cut + 1:]
    else:
        own_args, target = raw, []

    parser = argparse.ArgumentParser(description="Micro-tracer de execucao Python.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-calls", type=int, default=5_000_000)
    ns = parser.parse_args(own_args)
    if not target:
        parser.error("informe o alvo apos `--` (script ou -m modulo)")

    workspace = os.path.realpath(ns.workspace)
    display = _target_display(workspace, target)
    tracer = Tracer(Scope(workspace), ns.max_calls)

    started = time.perf_counter()
    exit_code = 0
    entrypoint: str | None = None
    written = False

    def write_once() -> None:
        nonlocal written
        if written:
            return
        written = True
        tracer.stop()
        duration = (time.perf_counter() - started) * 1000.0
        payload = _build_payload(
            workspace, tracer, entrypoint, exit_code, duration, display
        )
        _write_json(ns.out, payload)

    atexit.register(write_once)
    tracer.install()
    try:
        entrypoint = _run_target(workspace, target)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            exit_code = 0
        elif isinstance(code, int):
            exit_code = code
        else:
            exit_code = 1
    except BaseException:
        exit_code = 1
        raise
    finally:
        write_once()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
