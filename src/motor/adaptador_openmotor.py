# src/motor/adaptador_openmotor.py
"""Adaptador profundo do OpenMotor (motorlib/uilib) com suporte a overrides em memória.

Isola os efeitos colaterais de import do `uilib` (matplotlib backend,
`sys.excepthook` e logger) atrás de uma única interface `executar_ric()`.
"""
from __future__ import annotations

import contextlib
import copy
import io
import logging
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

from src.especificacoes import GrainSpec

# --- Isola os efeitos colaterais do import do uilib ---
_orig_use = matplotlib.use
_orig_excepthook = sys.excepthook


def _safe_use(backend=None, *args, **kwargs):
    if backend and "qt" in str(backend).lower():
        return
    return _orig_use(backend, *args, **kwargs)


matplotlib.use = _safe_use
warnings.filterwarnings("ignore", category=RuntimeWarning)
logging.getLogger("uilib").setLevel(logging.ERROR)

try:
    with contextlib.redirect_stdout(io.StringIO()):
        import uilib.logger as _uilib_logger
        from motorlib.motor import Motor
        from uilib.fileIO import fileTypes, loadFile

        _uilib_logger.logger._write = lambda level, content: None
finally:
    matplotlib.use = _orig_use
    sys.excepthook = _orig_excepthook


@dataclass(frozen=True)
class ResultadoRic:
    """Geometria efetiva pós-overrides e métricas balísticas da simulação `.ric`."""
    grains: tuple[GrainSpec, ...]
    propellant_density: float
    throat_radius: float
    nozzle_exit_radius: float
    burn_time: tuple[float, float]
    impulso_total: float
    empuxo_max: float
    massa_propelente_inicial: float
    curva_empuxo: tuple[tuple[float, float], ...]
    p0_pico: float
    kn_pico: float
    mass_flux_pico: float
    isp_entregue: float


def _set_path(obj: Any, partes: list[str], valor: Any) -> None:
    """Aplica `valor` em `obj` seguindo `partes` (dot-path com suporte a `*` e índice)."""
    if not partes:
        return

    chave, resto = partes[0], partes[1:]
    is_list_op = chave == "*" or chave.isdigit()

    if not resto:
        if chave == "*":
            if not isinstance(obj, list):
                raise TypeError(f"'*' aplicado em objeto que não é lista: {type(obj)}")
            for i in range(len(obj)):
                obj[i] = valor
            return
        if chave.isdigit():
            if not isinstance(obj, list):
                raise TypeError(f"Índice {chave} aplicado em não-lista: {type(obj)}")
            obj[int(chave)] = valor
            return
        if isinstance(obj, dict) and chave not in obj:
            raise KeyError(f"Chave final '{chave}' não existe no dict. Disponíveis: {list(obj.keys())}")
        obj[chave] = valor
        return

    if is_list_op:
        if not isinstance(obj, list):
            raise TypeError(f"'{chave}' aplicado em objeto que não é lista: {type(obj)}")
        alvos = obj if chave == "*" else [obj[int(chave)]]
        for item in alvos:
            _set_path(item, resto, valor)
        return

    if chave not in obj:
        raise KeyError(f"Chave '{chave}' não existe no dict. Disponíveis: {list(obj.keys())}")
    _set_path(obj[chave], resto, valor)


def _aplicar_overrides(props: dict, overrides: dict[str, Any]) -> dict:
    """Retorna uma cópia de `props` com wildcards aplicados antes de índices específicos."""
    copia = copy.deepcopy(props)
    chaves = sorted(
        overrides.keys(),
        key=lambda k: 1 if any(p.isdigit() for p in k.split(".")) else 0,
    )
    for chave in chaves:
        _set_path(copia, chave.split("."), overrides[chave])
    return copia


def _extrair_geometria(props: dict) -> tuple[tuple[GrainSpec, ...], float, float, float]:
    """Extrai `(grains, propellant_density, throat_radius, nozzle_exit_radius)` de `props`."""
    grains_raw = props.get("grains")
    if not grains_raw:
        raise KeyError("Dicionário 'props' do .ric não contém a lista 'grains'.")

    grains: list[GrainSpec] = []
    for i, g in enumerate(grains_raw):
        p = g.get("properties", {})
        try:
            length = float(p["length"])
            diameter = float(p["diameter"])
            core_diameter = float(p.get("coreDiameter", p.get("core_diameter")))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Propriedades inválidas no grão [{i}] do .ric: {p}") from exc

        grains.append(GrainSpec(length=length, outer_radius=diameter / 2.0, inner_radius=core_diameter / 2.0))

    prop_density = float(props.get("propellant", {})["density"])
    nozzle = props.get("nozzle", {})
    throat_d = float(nozzle.get("throat", nozzle.get("throatDiameter")))
    exit_d = float(nozzle.get("exit", nozzle.get("exitDiameter")))
    return tuple(grains), prop_density, throat_d / 2.0, exit_d / 2.0


def _pico_canal_2d(data) -> float:
    if not len(data):
        return 0.0
    if isinstance(data[0], (list, tuple)):
        return max(float(v) for sub in data for v in sub)
    return max(float(v) for v in data)


def executar_ric(
    ric_path: str | Path,
    overrides: dict[str, Any] | None = None,
    *,
    nome: str | None = None,
) -> ResultadoRic:
    """Carrega um `.ric`, aplica `overrides` em memória, extrai geometria e roda o OpenMotor."""
    path = Path(ric_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo .ric não encontrado: {path}")

    props = loadFile(str(path), fileTypes.MOTOR)
    if overrides:
        props = _aplicar_overrides(props, overrides)

    grains, prop_density, throat_r, exit_r = _extrair_geometria(props)
    sim = Motor(copy.deepcopy(props)).runSimulation()

    if not sim.success:
        alertas = [getattr(a, "message", str(a)) for a in sim.alerts]
        raise RuntimeError(f"Simulação do OpenMotor falhou para '{nome or 'Motor'}'. Alertas: {alertas}")

    ch = sim.channels
    tempo = [float(v) for v in ch["time"].getData()]
    empuxo = [float(v) for v in ch["force"].getData()]
    pressao = [float(v) for v in ch["pressure"].getData()]
    kn = [float(v) for v in ch["kn"].getData()]
    massa_t0 = ch["mass"].getData()[0]
    massa_inicial = float(sum(massa_t0)) if isinstance(massa_t0, (list, tuple)) else float(massa_t0)

    try:
        isp = float(sim.getISP())
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        isp = float("nan")

    return ResultadoRic(
        grains=grains,
        propellant_density=prop_density,
        throat_radius=throat_r,
        nozzle_exit_radius=exit_r,
        burn_time=(tempo[0], tempo[-1]),
        impulso_total=float(np.trapezoid(empuxo, tempo)),
        empuxo_max=max(empuxo),
        massa_propelente_inicial=massa_inicial,
        curva_empuxo=tuple(zip(tempo, empuxo)),
        p0_pico=max(pressao),
        kn_pico=max(kn),
        mass_flux_pico=_pico_canal_2d(ch["massFlux"].getData()),
        isp_entregue=isp,
    )
